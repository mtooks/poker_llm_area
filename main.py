"""Simplified poker game using the new player factory."""

import asyncio
import json
import random
import re
from typing import Any, Dict, List

from pokerkit import Automation, Mode, NoLimitTexasHoldem
from pokerkit.state import HoleCardsShowingOrMucking, BetCollection, BlindOrStraddlePosting, CardBurning, HoleDealing, ChipsPulling

from players.player_factory import PlayerFactory

############################################################
# ───────────────────  CONFIG  ─────────────────────────────
############################################################

from game_config import GAME_CONFIG, PLAYER_CONFIGS

# Game configuration
BLINDS = GAME_CONFIG["blinds"]
MIN_BET = BLINDS[1]
RNG_SEED = GAME_CONFIG["rng_seed"]
LEGAL_TOKEN_RE = re.compile(r"^(fold|check|call|raise_to:\s*\d+)$")

############################################################
# ───────────────  PROMPT ADAPTER  ─────────────────────────
############################################################

class PromptAdapter:
    """Helpers for state → prompt and token → state transition."""
    
    @staticmethod
    def visible_state(st, player: int) -> Dict[str, Any]:
        def card_str_list(cards):
            return [str(card) for card in cards]

        def action_str(op):
            cls = type(op).__name__
            if cls == 'BoardDealing':
                return f"Dealt cards={op.cards}"
            if hasattr(op, "player_index") and hasattr(op, "amount"):
                return f"{cls}(player={op.player_index}, amount={getattr(op, 'amount', None)})"
            else:
                return None

        street_map = {0: "Pre flop", 1: "Flop", 2: "Turn", 3: "River"}
        street_name = street_map.get(st.street_index, "Unknown")

        if st.can_complete_bet_or_raise_to(st.min_completion_betting_or_raising_to_amount):
            min_raise = st.min_completion_betting_or_raising_to_amount
        else:
            min_raise = 'Cannot Raise'

        # Position logic for multiple players
        player_count = len(st.stacks)
        if player_count == 2:
            # Heads-up play
            position = "Button" if player == 0 else "Big Blind"
        else:
            # Multi-player positions
            positions = ["Button", "Small Blind", "Big Blind", "UTG", "Hijack", "Cutoff"]
            position = positions[player % len(positions)]

        # Get opponent stacks (all other players)
        opponent_stacks = [st.stacks[i] for i in range(len(st.stacks)) if i != player]

        return {
            "Current Street": street_name,
            "Position": position,
            "board": card_str_list(st.get_board_cards(0)),
            "Hole Cards": card_str_list(st.hole_cards[player]),
            "Your stack": st.stacks[player],
            "Opponent stacks": opponent_stacks,
            "Pot size": st.total_pot_amount,
            "to_call": st.checking_or_calling_amount if st.can_check_or_call() else 0,
            "min_raise_to": min_raise,
            "history": [action_str(op) for op in st.operations if action_str(op) is not None]
        }

    @staticmethod
    def legal_tokens(st):
        tokens = []
        if st.can_fold():              
            tokens.append("fold")
        if st.can_check_or_call():
            if st.checking_or_calling_amount == 0:
                tok = "check"
            else:
                tok = f"call"
            tokens.append(tok)

        min_raise = st.min_completion_betting_or_raising_to_amount
        tokens.append(f"raise_to: {min_raise} to {st.stacks[st.actor_index]}")

        return tokens

    @staticmethod
    def apply_token(st, tok: str):
        if tok == "fold":
            st.fold()
        elif tok.startswith("check") or tok.startswith("call"):
            st.check_or_call()
        elif tok.startswith("raise_to"):
            st.complete_bet_or_raise_to(int(tok.split(":")[1].strip()))
        else:
            raise ValueError(tok)

############################################################
# ─────────────────  GAME ORCHESTRATOR  ───────────────────
############################################################

class GameOrchestrator:
    """Simplified game orchestrator using the player factory."""

    def __init__(self, hands: int = 1):
        self.hands = hands
        self.rng = random.Random(RNG_SEED)
        
        # Create players using the factory
        self.players = []
        for config in PLAYER_CONFIGS:
            player = PlayerFactory.create_player(
                name=config["name"],
                provider=config["provider"],
                model=config.get("model"),  # Use None to get default model
                initial_stack=GAME_CONFIG["initial_stack"]
            )
            self.players.append(player)
        
        self.dealer_position = 0

    def _make_state(self):
        """Create a fresh PokerKit state."""
        stacks = tuple(player.stack for player in self.get_players_in_position_order())
        for i in stacks:
            if i <= 0:
                raise ValueError(f"Invalid stack size: {i}. Must be non-negative.")
        
        player_count = len(self.players)
        return NoLimitTexasHoldem.create_state(
            (
                Automation.ANTE_POSTING,
                Automation.BET_COLLECTION,
                Automation.BLIND_OR_STRADDLE_POSTING,
                Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
                Automation.BOARD_DEALING,
                Automation.CARD_BURNING,
                Automation.HOLE_DEALING,
                Automation.HAND_KILLING,
                Automation.CARD_BURNING,
                Automation.CHIPS_PUSHING,
                Automation.CHIPS_PULLING,
            ),
            False,       # ante_trimming_status
            {0: 0},      # raw_antes
            (1, 2),      # raw_blinds_or_straddles
            2,           # min_bet
            stacks,      # raw_starting_stacks
            player_count,  # player_count - now dynamic
            mode=Mode.CASH_GAME,
        )
    
    def get_players_in_position_order(self):
        """Return players in their current position order based on dealer position."""
        return [self.players[(i + self.dealer_position) % len(self.players)] 
                for i in range(len(self.players))]
    
    def card_to_emoji(self, card_str):
        """Convert a card string to an emoji."""
        suit_map = {
            'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'
        }

        if not isinstance(card_str, str):
            card_str = str(card_str)
        
        if '(' in card_str and ')' in card_str:
            card_str = card_str.split('(')[1].split(')')[0]
            rank, suit = card_str[:-1], card_str[-1]
            suit = suit.upper()
            return f"{rank}{suit_map[suit]}"
        return card_str

    async def _play_hand(self, hand_no: int):
        """Play a single hand."""
        st = self._make_state()
        last_board = []
        last_stacks = list(st.stacks)
        last_history_len = 0
        
        print(f"\n=== Hand {hand_no} ===")
        
        # Get players in position order for this hand
        players_in_position = self.get_players_in_position_order()
        if len(players_in_position) == 2:
            print(f"Button: {players_in_position[0].name} (SB), BB: {players_in_position[1].name}")
        else:
            print(f"Button: {players_in_position[0].name}, SB: {players_in_position[1].name}, BB: {players_in_position[2].name}")
            if len(players_in_position) > 3:
                for i in range(3, len(players_in_position)):
                    print(f"  Player {i}: {players_in_position[i].name}")
        
        # Track hand data
        hand_data = {
            "hand_id": hand_no,
            "starting_stacks": last_stacks.copy(),
            "actions": [],
            "final_board": [],
            "dealer_position": self.dealer_position,
            "result": {}
        }
       
        # Display hole cards
        for i in st.player_indices:
            actual_player_idx = (i + self.dealer_position) % len(self.players)
            print(f"P{i}, aka {self.players[actual_player_idx].name} hole cards:", 
                  [self.card_to_emoji(card) for card in list(st.hole_cards[i])])
        
        # Betting loop
        while st.status:
            plr_idx = st.actor_index
            if plr_idx is None:
                break
                
            actual_player_idx = (plr_idx + self.dealer_position) % len(self.players)
            player_name = self.players[actual_player_idx].name
            legal = PromptAdapter.legal_tokens(st)
            game_state = PromptAdapter.visible_state(st, plr_idx)
            
            # Get player decision
            rsp = await self.players[actual_player_idx].make_decision(game_state, legal)
            
            # Parse response
            try:
                rsp, commentary = rsp.split('@')[0].strip(), rsp.split('@')[1]
                print(f"{player_name}: {commentary}")
                hand_data["actions"].append({
                    "player": actual_player_idx,
                    "action": rsp,
                    "commentary": commentary
                })
            except ValueError:
                rsp = rsp.strip()
                hand_data["actions"].append({
                    "player": actual_player_idx,
                    "action": rsp,
                    "commentary": ""
                })
                
            # Validate move
            if not LEGAL_TOKEN_RE.match(rsp):
                print(f'ILLEGAL MOVE: {rsp} - auto-folding')
                rsp = "fold" 
                hand_data["actions"][-1]["action"] = "fold"
                
            try:               
                PromptAdapter.apply_token(st, rsp)
                
                # Print new developments
                board = [str(card) for card in st.get_board_cards(0)]
                if board != last_board:
                    print(f"Board: {[self.card_to_emoji(card) for card in board]}")
                    last_board = board.copy()
                    hand_data["final_board"] = board.copy()
                    
                # Print new actions
                if len(st.operations) > last_history_len:
                    filtered_ops = (BetCollection, CardBurning, HoleDealing, ChipsPulling, BlindOrStraddlePosting)                    
                    for op in st.operations[last_history_len:]:
                        if isinstance(op, HoleCardsShowingOrMucking) and op.hole_cards:
                            cards_str = [str(card) for card in op.hole_cards]
                            emoji_cards = [self.card_to_emoji(card) for card in cards_str]
                            actual_player = (op.player_index + self.dealer_position) % len(self.players)
                            print(f"Player {self.players[actual_player].name} shows: {emoji_cards}")
                        if not isinstance(op, filtered_ops):
                            print(f"Action: {op}")
                last_history_len = len(st.operations)
                    
                # Print stack changes
                if list(st.stacks) != last_stacks:
                    players_in_position = self.get_players_in_position_order()
                    stack_str = ", ".join([f"{players_in_position[i].name}={st.stacks[i]}" for i in range(len(st.stacks))])
                    print(f"Stacks: {stack_str}")
                    last_stacks = list(st.stacks)

            except Exception as e:
                print(f"Error in hand {hand_no}: {e}")
                st.fold()

        # Showdown & settle pots
        players_in_position = self.get_players_in_position_order()
        result_str = " | ".join([f"{players_in_position[i].name}={st.stacks[i]}" for i in range(len(st.stacks))])
        print(f"Hand {hand_no} result → stacks: {result_str}")
        
        # Update hand result data
        hand_data["result"] = {
            "final_stacks": list(st.stacks),
        }
        # Add profit for each player
        for i in range(len(st.stacks)):
            hand_data["result"][f"profit_p{i}"] = st.stacks[i] - hand_data["starting_stacks"][i]
        
        # Update player stacks and memory
        for idx, player in enumerate(players_in_position):
            player.update_stack(st.stacks[idx])
            player.update_memory(hand_data)
            
        # Rotate dealer position
        self.dealer_position = (self.dealer_position + 1) % len(self.players)

    async def run(self):
        """Run the complete game."""
        illegal_moves_count = 0
        
        for h in range(self.hands):
            await self._play_hand(h)
        
        # Print performance summary
        print("\n=== Performance Summary ===")
        print(f"Illegal moves: {illegal_moves_count}")
        
        for idx, player in enumerate(self.players):
            wins = 0
            for hand in player.hand_history:
                dealer_pos = hand.get("dealer_position", 0)
                player_position = (idx - dealer_pos) % len(self.players)
                if hand["result"].get(f"profit_p{player_position}", 0) > 0:
                    wins += 1
            
            profit = player.stack - player.initial_stack
            win_rate = (wins / self.hands * 100) if self.hands > 0 else 0
            
            print(f"{player.name}: {wins}/{self.hands} wins ({win_rate:.1f}%), Profit: {profit}")
            if player.notes:
                print(f"  Notes: {player.notes[:100]}...")

############################################################
# ─────────────────────  MAIN  ─────────────────────────────
############################################################

async def main():
    """Main entry point."""
    print("=== Poker Game with Player Factory ===")
    print(f"Players: {[config['name'] for config in PLAYER_CONFIGS]}")
    print(f"Hands to play: {GAME_CONFIG['hands']}")
    
    game = GameOrchestrator(hands=GAME_CONFIG['hands'])
    await game.run()

if __name__ == "__main__":
    asyncio.run(main()) 