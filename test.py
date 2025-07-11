# poker_llm_orchestrator.py
"""Skeleton driver for heads‑up NLHE matches between two LLMs (ChatGPT &
Gemini) using **Poker‑Kit** as the authoritative rules engine.

Key components
==============
* **LLMThread** – isolated chat session wrapper (OpenAI or Gemini).
* **PromptAdapter** – converts Poker‑Kit `State` → player‑specific JSON prompt
  and validates the returned token.
* **Orchestrator** – runs one table for _n_ hands.  Deterministic if you freeze
  RNG, model versions and config.

The script is deliberately minimal: no fancy logging, retry policy, cost
tracking or multi‑table scheduler. Those are left for you to flesh out once the
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
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

import openai  # type: ignore
from google import genai # type: ignore  # ← new pkg name replaces deprecated `google.generativeai`
from pokerkit import Automation, Mode, NoLimitTexasHoldem
from pokerkit.state import HoleCardsShowingOrMucking

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
# ───────────────  LLM THREAD WRAPPER  ─────────────────────
############################################################

@dataclass
class LLMThread:
    """Isolated chat thread for one player."""

    name: str                 # "P0" / "P1"
    provider: str             # "openai" | "gemini"
    model: str

    async def _chat_openai(self, messages: Sequence[Dict[str, str]]) -> str:
        client = openai.AsyncOpenAI(api_key=OPENAI_KEY)  # relies on $OPENAI_API_KEY
        rsp = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        # print(rsp)
        return rsp.choices[0].message.content.strip()

    async def _chat_gemini(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send the prompt to Gemini via the *google‑genai* client.

        The library does not yet support full role‑based chat; we pack our JSON
        into a single user message and rely on the system prompt to condition
        behaviour.  Gemini 1.5 handles short prompts well.
        """
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel(self.model)
        user_content = messages[-1]["content"]  # single user JSON string
        sys_prompt = messages[0]["content"]
        # Gemini expects the system prompt as a prefix in the text content.
        full_prompt = f"<system>\n{sys_prompt}\n</system>\n<user>\n{user_content}\n</user>"
        resp = model.generate_content(full_prompt)
        return resp.text.strip()

    async def ask(self, messages: Sequence[Dict[str, str]]) -> str:
        if self.provider == "openai":
            return await self._chat_openai(messages)
        if self.provider == "gemini":
            return await self._chat_gemini(messages)
        raise ValueError(self.provider)

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
        self.players = [
            LLMThread("P0", "openai", OPENAI_MODEL),
            LLMThread("P1", "openai", OPENAI_MODEL),
        ]
        self.stacks = (400, 400)  # Initial stacks

    # Build a fresh Poker‑Kit state
    def _make_state(self, stacks=None):
        # Use provided stacks or default
        stacks = stacks if stacks is not None else (400, 400)
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
        rank_map = {
            'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J',
            'T': '10', '9': '9', '8': '8', '7': '7', '6': '6',
            '5': '5', '4': '4', '3': '3', '2': '2'
        }
        suit_map = {
            's': '♠️', 'h': '♥️', 'd': '♦️', 'c': '♣️',
            'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️'
        }
        # Card string is like 'As', 'Td', etc.
        if len(card_str) == 2:
            rank, suit = card_str[0], card_str[1]
        else:
            rank, suit = card_str[:-1], card_str[-1]
        return f"{rank_map.get(rank, rank)}{suit_map.get(suit, suit)}"

    def hole_cards_to_emoji(self, cards):
        """Convert a list of card strings to emoji representation."""
        return ' '.join([self.card_to_emoji(card) for card in cards])

    def board_to_emoji(self, board):
        return [self.card_to_emoji(card) for card in board]

    async def _play_hand(self, hand_no: int):
        st = self._make_state(self.stacks)
        last_board = []
        last_stacks = list(st.stacks)
        last_history_len = 0
        print(f"\n=== Hand {hand_no} ===")
        # Betting loop ------------------------------------------------------
        # while not st.can_push_chips():
        while st.status:
            plr = st.actor_index
            legal = PromptAdapter.legal_tokens(st)
            prompt_json = json.dumps(
                {
                    "state": PromptAdapter.visible_state(st, plr),
                    "legal": legal,
                },
                separators=(',', ':'),
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        """You are an autonomous No limit TEXAS HOLDEM poker agent, evaluating the current game state and making the 
                        decision to fold, check, call, or raise that maximizes your expected value.
                        Return EXACTLY one token from the user's 'legal' list. If you want to
                        raise, use the format 'raise_to:<amount>'. Amount is a singular integers that has to be within the range provided.
                        The range of valid bet sizes is provided to you. A response like 'raise_to:6900 to 500' is not allowed. 
                        You are also provided with your hole cards, the current street, and the past board history.\n"
                        Justify your decision  but separate it from the token with the '@' symbol"""
                    ),
                },
                {"role": "user", "content": prompt_json},
            ]
            rsp = await self.players[plr].ask(messages)
            rsp, commentary = rsp.split('@')[0], rsp.split('@')[1]
            print(commentary)
            # TODO: validate rsp (raise to) against legal tokens
            # if not LEGAL_TOKEN_RE.match(rsp) or rsp not in legal:
            if not LEGAL_TOKEN_RE.match(rsp):
                print(f'Bad Move: {rsp}') # auto‑punish illegal output
                rsp = "fold" 
            try:
                PromptAdapter.apply_token(st, rsp)
                # Print only new developments:
                # 1. New board cards
                board = [str(card) for card in st.get_board_cards(0)]
                if board != last_board:
                    print(f"Board: {' '.join(self.board_to_emoji(board))}")
                    last_board = board.copy()
                # 2. New actions
                if len(st.operations) > last_history_len:
                    for op in st.operations[last_history_len:]:
                        # Display hole cards with emojis when they're shown
                        if isinstance(op, HoleCardsShowingOrMucking) and op.hole_cards:
                            cards_str = [str(card) for card in op.hole_cards]
                            emoji_cards = self.hole_cards_to_emoji(cards_str)
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

        # Showdown & settle pots -------------------------------------------
        # st.push_chips()
        print(
            f"Hand {hand_no} result → stacks: P0={st.stacks[0]} | P1={st.stacks[1]}",
            flush=True,
        )
        # Save stacks for next hand
        self.stacks = tuple(st.stacks)

    async def run(self):
        for h in range(1, self.hands + 1):
            await self._play_hand(h)

#######################################################################
# ─────────────────────  CLI ENTRY POINT  ─────────────────────────────
#######################################################################

if __name__ == "__main__":
    hands_to_play = int(os.getenv("NUM_HANDS", "1"))
    orch = Orchestrator(hands=hands_to_play)
    asyncio.run(orch.run())
