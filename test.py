# poker_llm_orchestrator.py
"""
TODO: Fix the Order of logging and output display.


The script is deliberately minimal: no fancy logging, retry policy, cost
tracking or multi‑table scheduler. Those are left for you to flesh out once the
core loop behaves.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence
from pathlib import Path

# Remove dotenv loading since Player handles API keys internally
from pokerkit import Automation, Mode, NoLimitTexasHoldem
from pokerkit.state import HoleCardsShowingOrMucking, BetCollection, BlindOrStraddlePosting, CardBurning, HoleDealing, ChipsPulling

from player import Player  # Import the new Player class

############################################################
# ───────────────────  CONFIG  ─────────────────────────────
############################################################

OPENAI_MODEL = "gpt-4o-mini"      # cheap; swap to gpt-4o for stronger play
GEMINI_MODEL = "gemini-1.5-flash"
ANTHROPIC_MODEL = "claude-3-5-haiku-latest"

# Load API keys from environment variables
GEMINI_KEY = os.getenv("GEMINI_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_KEY", "")

BLINDS = (50, 100)  # SB, BB
MIN_BET = BLINDS[1]

RAISE_SIZES = (
    lambda s: s.min_completion_betting_or_raising_amount,                      # min‑raise
    lambda s: max(2 * s.min_completion_betting_or_raising_amount, s.total_pot_amount),
)  # pot‑ish raise slot

RNG_SEED = 42
LEGAL_TOKEN_RE = re.compile(r"^(fold|check|call|raise_to:\s*\d+)$")

############################################################
# ───────────────  PROMPT ADAPTER  ─────────────────────────
############################################################

class PromptAdapter:
    """Helpers for state → prompt and token → state transition."""
    @staticmethod
    def visible_state(st, player: int) -> Dict[str, Any]:
        def card_str_list(cards):
            return [str(card) for card in cards]

        def action_str(op):
        # Typical PokerKit operation classes: Folding, CheckingOrCalling, CompletionBettingOrRaisingTo, etc.
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

        # --- Position logic ---
        # We need to know the dealer position and the mapping from state index to actual player
        # We'll assume the orchestrator sets: st.dealer_position and st.players (if not, fallback to heads-up default)
        try:
            dealer_position = st.dealer_position
            player_count = len(st.stacks)
            # Map state player index to actual player index
            actual_player_idx = (player + dealer_position) % player_count
            # For heads-up: player 0 is Button (SB), player 1 is BB
            if player_count == 2:
                position = "Button" if player == 0 else "Big Blind"
            else:
                # For more players, you can expand this mapping as needed
                pos_names = ["Button", "Small Blind", "Big Blind", "UTG", "Hijack", "Cutoff"]
                position = pos_names[player % len(pos_names)]
        except Exception:
            # Fallback for robustness
            position = "Button" if player == 0 else "Big Blind"

        return {
        "Current Street": street_name,
        "Position": position,
            # "button": st.button_index,  # Only include if you track button_index elsewhere
        # "actor": player,
        "board": card_str_list(st.get_board_cards(0)),
        "Hole Cards": card_str_list(st.hole_cards[player]),
        "Your stack": st.stacks[player],
        "Opponent stack": st.stacks[1 - player],
        "Pot size": st.total_pot_amount,
        "to_call": st.checking_or_calling_amount if st.can_check_or_call() else 0,
        "min_raise_to": (min_raise),
        "history": [action_str(op) for op in st.operations if action_str(op)  is not None]
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
# ─────────────────  ORCHESTRATOR  ─────────────────────────
############################################################

class Orchestrator:
    """Runs one table for `hands` hands."""

    def __init__(self, hands: int = 1):
        self.hands = hands
        self.rng = random.Random(RNG_SEED)
        # Replace LLMThread with Player instances
        self.players = [
            Player("Mr.Altman", "openai", OPENAI_MODEL, initial_stack=400),
            Player("Mr.Claude", "anthropic", ANTHROPIC_MODEL, initial_stack=400),
        ]
        # Add dealer position tracking (0 = first player is dealer)
        self.dealer_position = 0

    # Build a fresh Poker‑Kit state
        # Use the dealer position to determine order of play
    def _make_state(self):
        stacks = tuple(player.stack for player in self.get_players_in_position_order())
        for i in stacks:
            if i <= 0:
                #TODO: handle someone busting
                raise ValueError(f"Invalid stack size: {i}. Must be non-negative.")
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
            ),           # 1. automations
                False,       # 2. ante_trimming_status
                {0: 0},   # 3. raw_antes
                (1, 2),  # 4. raw_blinds_or_straddles
                2,         # 5. min_bet
                stacks,      # 6. raw_starting_stacks
                2,           # 7. player_count
                mode=Mode.CASH_GAME,  # 8. mode (keyword-only)
        )
    
    def get_players_in_position_order(self):
        """Return players in their current position order based on dealer position."""
        # In heads-up play, dealer is SB and acts first preflop, second postflop
        # So we rotate the players array based on dealer position
        return [self.players[(i + self.dealer_position) % len(self.players)] 
                for i in range(len(self.players))]
    
    def get_player_index_in_game_state(self, player_idx):
        """Convert real player index to index in the current game state."""
        # This converts the actual player index to their position in this hand
        return (player_idx - self.dealer_position) % len(self.players)

    def card_to_emoji(self, card_str):
        """Convert a card string like 'AS' or 'Td' to an emoji."""
        suit_map = {
            'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'
        }

        if not isinstance(card_str, str):
            card_str = str(card_str)
        # Card string comes in like 'EIGHT OF CLUBS (8c)'
        if '(' in card_str and ')' in card_str:
            # Extract the shorthand notation from inside parentheses
            card_str = card_str.split('(')[1].split(')')[0]
            rank, suit = card_str[:-1], card_str[-1]
            suit = suit.upper()  # Ensure suit is uppercase
            return f"{rank}{suit_map[suit]}"

   

    async def _play_hand(self, hand_no: int):
        st = self._make_state()
        last_board = []
        last_stacks = list(st.stacks)
        last_history_len = 0
        print(f"\n=== Hand {hand_no} ===")
        
        # Get players in position order for this hand
        players_in_position = self.get_players_in_position_order()
        print(f"Button: {players_in_position[0].name} (SB), BB: {players_in_position[1].name}")
        
        # Track hand data to provide to players after completion
        hand_data = {
            "hand_id": hand_no,
            "starting_stacks": last_stacks.copy(),
            "actions": [],
            "final_board": [],
            "dealer_position": self.dealer_position,
            "result": {}
        }
       
        # Display hole cards at the beginning of the hand
        for i in st.player_indices:
            # Map state player index to actual player index
            actual_player_idx = (i + self.dealer_position) % len(self.players)
            print(f"P{i}, aka {self.players[actual_player_idx].name} hole cards:", 
                  [self.card_to_emoji(card) for card in list(st.hole_cards[i])])
        
        # Betting loop ------------------------------------------------------
        while st.status:
            plr_idx = st.actor_index
            if plr_idx is None:
                break
                
            # Map state player index to actual player index
            actual_player_idx = (plr_idx + self.dealer_position) % len(self.players)
            player_name = self.players[actual_player_idx].name
            legal = PromptAdapter.legal_tokens(st)
            game_state = PromptAdapter.visible_state(st, plr_idx)
            
            # Use the player's make_decision method
            rsp = await self.players[actual_player_idx].make_decision(game_state, legal)
            
            # Track action in hand history
            try:
                rsp, commentary = rsp.split('@')[0].strip(), rsp.split('@')[1]
                print(player_name +": "+ commentary)
                hand_data["actions"].append({
                    "player": actual_player_idx,
                    "action": rsp,
                    "commentary": commentary
                })
            except ValueError:
                # Handle case where response doesn't contain the @ symbol
                rsp = rsp.strip()
                hand_data["actions"].append({
                    "player": actual_player_idx,
                    "action": rsp,
                    "commentary": ""
                })
                
            # Validate. TODO: eliminate regex and actually use the values in legal
            if not LEGAL_TOKEN_RE.match(rsp):
                print(f'!!!!!!!!!!!!!!ILLEGAL MOVE!!!!!!!: {rsp}') # auto‑punish illegal output
                rsp = "fold" 
                hand_data["actions"][-1]["action"] = "fold"  # Update to actual action               
            try:               
                PromptAdapter.apply_token(st, rsp)
                # Print only new developments:
                # 1. New board cards
                board = [str(card) for card in st.get_board_cards(0)]
                if board != last_board:
                    print(f"Board: {[self.card_to_emoji(card) for card in board]}")
                    last_board = board.copy()
                    hand_data["final_board"] = board.copy()
                    
                # 2. New actions
                if len(st.operations) > last_history_len:
                    # Define operations to filter out in a tuple
                    filtered_ops = (BetCollection, CardBurning, HoleDealing, ChipsPulling, BlindOrStraddlePosting)                    
                    for op in st.operations[last_history_len:]:
                        # Display hole cards with emojis when they're shown
                        if isinstance(op, HoleCardsShowingOrMucking) and op.hole_cards:
                            cards_str = [str(card) for card in op.hole_cards]
                            emoji_cards = [self.card_to_emoji(card) for card in cards_str]
                            actual_player = (op.player_index + self.dealer_position) % len(self.players)
                            print(f"Player {self.players[actual_player].name} shows: {emoji_cards}")
                        # Filter out specific operation types when printing
                        if not isinstance(op, filtered_ops):
                            print(f"Action: {op}")
                last_history_len = len(st.operations)
                    
                # 3. Stack changes
                if list(st.stacks) != last_stacks:
                    # Map positions back to player names for clarity
                    players_in_position = self.get_players_in_position_order()
                    print(f"Stacks: {players_in_position[0].name}={st.stacks[0]}, {players_in_position[1].name}={st.stacks[1]}")
                    last_stacks = list(st.stacks)

            except Exception as e:
                print(f"Error occurred while processing hand {hand_no}: {e}")
                st.fold()
                

        # Showdown & settle pots -------------------------------------------
        # Map positions back to player names for the final result
        players_in_position = self.get_players_in_position_order()
        print(
            f"Hand {hand_no} result → stacks: {players_in_position[0].name}={st.stacks[0]} | {players_in_position[1].name}={st.stacks[1]}",
            flush=True,
        )
        
        # Update hand result data
        hand_data["result"] = {
            "final_stacks": list(st.stacks),
            "profit_p0": st.stacks[0] - hand_data["starting_stacks"][0],
            "profit_p1": st.stacks[1] - hand_data["starting_stacks"][1],
        }
        
        # Update player stacks and memory
        for idx, player in enumerate(players_in_position):
            player.update_stack(st.stacks[idx])
            player.update_memory(hand_data)
            
        # Rotate dealer position for next hand
        self.dealer_position = (self.dealer_position + 1) % len(self.players)

    async def run(self):
        for h in range(1, self.hands + 1):
            await self._play_hand(h)
        
        # Print overall performance
        print("\n=== Overall Performance ===")
        total_profit = 0  # To verify zero-sum property
        
        # Calculate VPIP and PFR stats
        vpip_counts = [0] * len(self.players)
        pfr_counts = [0] * len(self.players)
        hand_counts = [0] * len(self.players)
        
        # Count total hands each player was dealt
        for player_idx, player in enumerate(self.players):
            hand_counts[player_idx] = len(player.hand_history)
        
        # Reset and properly calculate VPIP and PFR by tracking each player correctly
        for idx, player in enumerate(self.players):
            # Each player gets one VPIP count per hand where they voluntarily put in money
            vpip_per_hand = set()  # Track hands where this player voluntarily put in
            pfr_per_hand = set()   # Track hands where this player raised preflop
            
            for hand in player.hand_history:
                hand_id = hand["hand_id"]
                dealer_pos = hand.get("dealer_position", 0)
                
                # Track preflop actions only
                is_preflop_action = True
                
                for action in hand["actions"]:
                    player_idx = action["player"]
                    action_type = action["action"]
                    
                    # Skip actions by other players
                    if player_idx != idx:
                        continue
                        
                    # Check if we're still in preflop
                    if not is_preflop_action:
                        continue
                        
                    # Check if this is where flop is dealt (end of preflop)
                    if "Dealt cards=" in action_type:
                        is_preflop_action = False
                        continue
                    
                    # Only count voluntary actions (not blinds/checks)
                    if action_type not in ["fold", "check"]:
                        vpip_per_hand.add(hand_id)
                    
                    # Count raises specifically
                    if action_type.startswith("raise_to:"):
                        pfr_per_hand.add(hand_id)
                
                # After processing actions, check if flop was dealt
                for action in hand["actions"]:
                    if "Dealt cards=" in action.get("action", ""):
                        is_preflop_action = False
                        break
            
            # Now count unique hands where player took these actions
            vpip_counts[idx] = len(vpip_per_hand)
            pfr_counts[idx] = len(pfr_per_hand)
        
        # Print performance stats
        for idx, player in enumerate(self.players):
            # Bug fix: The profit calculation was using the wrong key format
            # We need to track which position the player was in for each hand
            wins = 0
            for hand in player.hand_history:
                # Find which position (p0 or p1) this player was in for this hand
                dealer_pos = hand.get("dealer_position", 0)
                # In this hand, player was in position:
                player_position = (idx - dealer_pos) % len(self.players)
                # Now check if that position had positive profit
                if hand["result"].get(f"profit_p{player_position}", 0) > 0:
                    wins += 1
            
            # Calculate profit as the difference between final stack and initial stack
            profit = player.stack - player.initial_stack
            total_profit += profit
            
            # Calculate VPIP and PFR as percentages (ensuring they can't exceed 100%)
            vpip_pct = min(100, (vpip_counts[idx] / hand_counts[idx] * 100)) if hand_counts[idx] > 0 else 0
            pfr_pct = min(100, (pfr_counts[idx] / hand_counts[idx] * 100)) if hand_counts[idx] > 0 else 0
            
            print(f"Player {player.name}: {wins}/{self.hands} hands won, Total profit: {profit}")
            print(f"  VPIP: {vpip_pct:.1f}% (voluntarily put money in {vpip_counts[idx]}/{hand_counts[idx]} hands)")
            print(f"  PFR: {pfr_pct:.1f}% (raised preflop in {pfr_counts[idx]}/{hand_counts[idx]} hands)")
        
        # Verify zero-sum property
        if total_profit != 0:
            print(f"Warning: Total profit ({total_profit}) should be zero in a zero-sum game")

#######################################################################
# ─────────────────────  CLI ENTRY POINT  ─────────────────────────────
#######################################################################

if __name__ == "__main__":
    hands_to_play = 3 
    orch = Orchestrator(hands=hands_to_play)
    asyncio.run(orch.run())

