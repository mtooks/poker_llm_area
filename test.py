# poker_llm_orchestrator.py
"""Skeleton driver for heads‑up NLHE matches between two LLMs (ChatGPT &
Gemini) using **Poker‑Kit** as the authoritative rules engine.

Key components
==============
* **Player** – encapsulates LLM session, stack tracking, and decision making.
* **PromptAdapter** – converts Poker‑Kit `State` → player‑specific JSON prompt
  and validates the returned token.
* **Orchestrator** – runs one table for _n_ hands.  Deterministic if you freeze
  RNG, model versions and config.

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
from pokerkit.state import HoleCardsShowingOrMucking

from player import Player  # Import the new Player class

############################################################
# ───────────────────  CONFIG  ─────────────────────────────
############################################################

OPENAI_MODEL = "gpt-4o-mini"      # cheap; swap to gpt-4o for stronger play
GEMINI_MODEL = "gemini-1.5-flash"

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
LEGAL_TOKEN_RE = re.compile(r"^(fold|check|call:\d+|raise_to:\s*\d+)$")

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
        if st.street_index == 0:
            street_name = "Pre flop"
        elif st.street_index == 1:
            street_name = "Flop"
        elif st.street_index == 2:
            street_name = "Turn"
        elif st.street_index == 3:
            street_name = "River"

        if st.can_complete_bet_or_raise_to(st.min_completion_betting_or_raising_to_amount):
            min_raise = st.min_completion_betting_or_raising_to_amount
        else:
            min_raise = 'Cannot Raise'

        return {
        "Current Street": street_name,
            # "button": st.button_index,  # Only include if you track button_index elsewhere
        # "actor": player,
        "board": card_str_list(st.get_board_cards(0)),
        "hole": card_str_list(st.hole_cards[player]),
        "your stack": st.stacks[player],
        "opponent stack": st.stacks[1 - player],
        # "stacks": list(st.stacks),
        "pot": st.total_pot_amount,
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
                tok = f"call:{st.checking_or_calling_amount}"
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
            Player("P0", "openai", OPENAI_MODEL, initial_stack=400),
            Player("P1", "openai", OPENAI_MODEL, initial_stack=400),
        ]

    # Build a fresh Poker‑Kit state
    def _make_state(self):
        stacks = (self.players[0].stack, self.players[1].stack)
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

    def card_to_emoji(self, card_str):
        """Convert a card string like 'AS' or 'Td' to an emoji."""

        suit_map = {
            'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'
        }
        # Card string comes in like 'EIGHT OF CLUBS (8c)'
        if '(' in card_str and ')' in card_str:
            # Extract the shorthand notation from inside parentheses
            card_str = card_str.split('(')[1].split(')')[0]
            rank, suit = card_str[:-1], card_str[-1]
        elif len(card_str) == 2: 

   

    async def _play_hand(self, hand_no: int):
        st = self._make_state()
        last_board = []
        last_stacks = list(st.stacks)
        last_history_len = 0
        print(f"\n=== Hand {hand_no} ===")
        
        # Track hand data to provide to players after completion
        hand_data = {
            "hand_id": hand_no,
            "starting_stacks": last_stacks.copy(),
            "actions": [],
            "final_board": [],
            "result": {}
        }
        
        # Betting loop ------------------------------------------------------
        while st.status:
            plr_idx = st.actor_index
            legal = PromptAdapter.legal_tokens(st)
            game_state = PromptAdapter.visible_state(st, plr_idx)
            
            # Use the player's make_decision method
            rsp = await self.players[plr_idx].make_decision(game_state, legal)
            
            # Track action in hand history
            try:
                rsp, commentary = rsp.split('@')[0].strip(), rsp.split('@')[1]
                print(commentary)
                hand_data["actions"].append({
                    "player": plr_idx,
                    "action": rsp,
                    "commentary": commentary
                })
            except ValueError:
                # Handle case where response doesn't contain the @ symbol
                rsp = rsp.strip()
                hand_data["actions"].append({
                    "player": plr_idx,
                    "action": rsp,
                    "commentary": "No commentary provided"
                })
                
            # Validate and apply token
            if not LEGAL_TOKEN_RE.match(rsp):
                print(f'Bad Move: {rsp}') # auto‑punish illegal output
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
                    for op in st.operations[last_history_len:]:
                        # Display hole cards with emojis when they're shown
                        if isinstance(op, HoleCardsShowingOrMucking) and op.hole_cards:
                            cards_str = [str(card) for card in op.hole_cards]
                            emoji_cards = [self.card_to_emoji(card) for card in cards_str]
                            print(f"Player {op.player_index} shows: {emoji_cards}")
                        print(f"Action: {op}")
                    last_history_len = len(st.operations)
                    
                # 3. Stack changes
                if list(st.stacks) != last_stacks:
                    print(f"Stacks: P0={st.stacks[0]}, P1={st.stacks[1]}")
                    last_stacks = list(st.stacks)
            except Exception:
                st.fold()
                print("Forced fold due to error.")
                hand_data["actions"][-1]["action"] = "fold"  # Update to actual action

        # Showdown & settle pots -------------------------------------------
        print(
            f"Hand {hand_no} result → stacks: P0={st.stacks[0]} | P1={st.stacks[1]}",
            flush=True,
        )
        
        # Update hand result data
        hand_data["result"] = {
            "final_stacks": list(st.stacks),
            "profit_p0": st.stacks[0] - hand_data["starting_stacks"][0],
            "profit_p1": st.stacks[1] - hand_data["starting_stacks"][1],
        }
        
        # Update player stacks and memory
        for idx, player in enumerate(self.players):
            player.update_stack(st.stacks[idx])
            player.update_memory(hand_data)

    async def run(self):
        for h in range(1, self.hands + 1):
            await self._play_hand(h)
        
        # Print overall performance
        print("\n=== Overall Performance ===")
        for idx, player in enumerate(self.players):
            wins = sum(1 for hand in player.hand_history if hand["result"][f"profit_p{idx}"] > 0)
            profit = sum(hand["result"][f"profit_p{idx}"] for hand in player.hand_history)
            print(f"Player {player.name}: {wins}/{self.hands} hands won, Total profit: {profit}")

#######################################################################
# ─────────────────────  CLI ENTRY POINT  ─────────────────────────────
#######################################################################

if __name__ == "__main__":
    hands_to_play = int(os.getenv("NUM_HANDS", "3"))
    orch = Orchestrator(hands=hands_to_play)
    asyncio.run(orch.run())
    # self.stacks = tuple(st.stacks)

    async def run(self):
        for h in range(1, self.hands + 1):
            await self._play_hand(h)

