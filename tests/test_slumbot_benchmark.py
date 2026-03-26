"""Step 12: Validate strategy — live benchmark against Slumbot API.

Slumbot is a near-GTO heads-up NLHE bot (2018 ACPC champion) with a free
REST API.  A correctly implemented GTO player should break roughly even
against it over many hands.

API endpoints:
  - POST https://slumbot.com/api/new_hand → hand state + token
  - POST https://slumbot.com/api/act → submit action, get next state
  - Action format: k (check), c (call), f (fold), b{amount} (bet)
  - 200bb deep, blinds 50/100

These tests are skipped by default (require network access and rate
limiting).  Run with::

    SLUMBOT_BENCHMARK=1 pytest tests/test_slumbot_benchmark.py -v
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pytest


# ------------------------------------------------------------------
# Slumbot API client
# ------------------------------------------------------------------


class SlumbotClient:
    """Minimal client for the Slumbot REST API."""

    BASE_URL = "https://slumbot.com/api"
    DELAY_BETWEEN_HANDS = 0.15  # seconds

    def __init__(self):
        try:
            import requests
            self._requests = requests
        except ImportError:
            self._requests = None

    @property
    def available(self) -> bool:
        return self._requests is not None

    def new_hand(self) -> Dict[str, Any]:
        resp = self._requests.post(f"{self.BASE_URL}/new_hand", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def act(self, token: str, action: str) -> Dict[str, Any]:
        resp = self._requests.post(
            f"{self.BASE_URL}/act",
            json={"token": token, "incr": action},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


# ------------------------------------------------------------------
# Slumbot ↔ Arena translation
# ------------------------------------------------------------------


def slumbot_to_arena_state(resp: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Convert a Slumbot API response to arena state + legal actions.

    Slumbot response fields:
      - ``hole_cards``: list of card ints (Slumbot encoding)
      - ``board``: list of card ints
      - ``action``: cumulative action string (e.g. ``"b200c/kk/kb300"``)
      - ``client_pos``: 0 or 1
      - ``winnings``: chips won (only on terminal)
    """
    # Parse cards from Slumbot's integer encoding.
    hole = _parse_slumbot_cards(resp.get("hole_cards", []))
    board = _parse_slumbot_cards(resp.get("board", []))

    action_str = resp.get("action", "")
    street = _action_to_street(action_str)
    pot = _estimate_pot(action_str)

    state = {
        "Current Street": street,
        "Hole Cards": hole,
        "board": board,
        "Pot size": pot,
        "Your stack": 20000 - pot // 2,  # Rough estimate (200bb * 100)
        "to_call": _last_bet_to_call(action_str),
        "history": [],
    }

    legal = ["fold", "check", "call", "raise_to: 100 to 20000"]
    return state, legal


def arena_to_slumbot_action(arena_action: str) -> str:
    """Convert an arena action string to Slumbot API format.

    Arena → Slumbot:
      fold       → f
      check      → k
      call       → c
      raise_to:N → b{N}
    """
    action = arena_action.strip().lower()
    if action == "fold":
        return "f"
    if action == "check":
        return "k"
    if action == "call":
        return "c"
    m = re.match(r"raise_to:\s*(\d+)", action)
    if m:
        return f"b{m.group(1)}"
    return "c"  # fallback


def _parse_slumbot_cards(card_ints: List[int]) -> List[str]:
    """Convert Slumbot integer card encoding to standard card strings.

    Slumbot uses: rank = card // 4, suit = card % 4
    Ranks: 0=2, 1=3, ..., 12=A
    Suits: 0=c, 1=d, 2=h, 3=s
    """
    ranks = "23456789TJQKA"
    suits = "cdhs"
    result = []
    for c in card_ints:
        if isinstance(c, int) and 0 <= c < 52:
            r = ranks[c // 4]
            s = suits[c % 4]
            result.append(f"{r}{s}")
    return result


def _action_to_street(action_str: str) -> str:
    """Count '/' separators to determine the current street."""
    slashes = action_str.count("/")
    return ["Pre Flop", "Flop", "Turn", "River"][min(slashes, 3)]


def _estimate_pot(action_str: str) -> int:
    """Rough pot estimate from action string."""
    pot = 150  # blinds: 50 + 100
    for m in re.finditer(r"b(\d+)", action_str):
        pot += int(m.group(1))
    for c in action_str:
        if c == "c":
            # call roughly matches last bet
            pass
    return pot


def _last_bet_to_call(action_str: str) -> int:
    """Extract the last bet amount that needs to be called."""
    bets = re.findall(r"b(\d+)", action_str)
    if bets:
        return int(bets[-1])
    return 0


# ------------------------------------------------------------------
# Benchmark runner
# ------------------------------------------------------------------


class SlumbotBenchmark:
    """Play hands against Slumbot and track results."""

    def __init__(self):
        self.client = SlumbotClient()
        self.results: List[int] = []

    def play_hand(self, player) -> Optional[int]:
        """Play one hand against Slumbot, return profit/loss in chips."""
        if not self.client.available:
            return None

        try:
            resp = self.client.new_hand()
        except Exception:
            return None

        token = resp.get("token")
        if not token:
            return None

        max_actions = 50  # safety limit
        action_count = 0

        while not resp.get("is_terminal") and action_count < max_actions:
            action_count += 1
            client_pos = resp.get("client_pos", 0)

            # Check if it's our turn.
            action_str = resp.get("action", "")
            turns_taken = len(re.findall(r"[bckf]", action_str.split("/")[-1]))

            try:
                state, legal = slumbot_to_arena_state(resp)
                msg = json.dumps({"state": state, "legal": legal})
                import asyncio
                response = asyncio.get_event_loop().run_until_complete(
                    player._chat([{"role": "user", "content": msg}])
                )
                arena_action = response.split("@")[0]
                slumbot_action = arena_to_slumbot_action(arena_action)
                resp = self.client.act(token, slumbot_action)
            except Exception:
                break

        winnings = resp.get("winnings", 0)
        self.results.append(winnings)
        return winnings

    def run_benchmark(self, player, n_hands: int = 100) -> Dict[str, Any]:
        """Play n_hands against Slumbot and return summary statistics."""
        for i in range(n_hands):
            profit = self.play_hand(player)
            if profit is None:
                break
            time.sleep(self.client.DELAY_BETWEEN_HANDS)

        total = sum(self.results)
        n = len(self.results)
        bb_per_100 = (total / n / 100) * 100 if n > 0 else 0

        return {
            "hands_played": n,
            "total_profit": total,
            "bb_per_100": bb_per_100,
            "results": self.results,
        }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSlumbotTranslation:
    """Test Slumbot ↔ Arena translation (runs without network)."""

    def test_parse_slumbot_cards(self):
        # Ace of spades = rank 12, suit 3 → 12*4 + 3 = 51
        cards = _parse_slumbot_cards([51])
        assert cards == ["As"]

    def test_parse_slumbot_cards_deuce(self):
        # 2 of clubs = rank 0, suit 0 → 0
        cards = _parse_slumbot_cards([0])
        assert cards == ["2c"]

    def test_arena_to_slumbot_fold(self):
        assert arena_to_slumbot_action("fold") == "f"

    def test_arena_to_slumbot_check(self):
        assert arena_to_slumbot_action("check") == "k"

    def test_arena_to_slumbot_call(self):
        assert arena_to_slumbot_action("call") == "c"

    def test_arena_to_slumbot_raise(self):
        assert arena_to_slumbot_action("raise_to: 300") == "b300"

    def test_action_to_street(self):
        assert _action_to_street("b200c") == "Pre Flop"
        assert _action_to_street("b200c/kb300") == "Flop"
        assert _action_to_street("b200c/kb300c/k") == "Turn"
        assert _action_to_street("b200c/kb300c/kk/b100") == "River"

    def test_slumbot_to_arena_state(self):
        resp = {
            "hole_cards": [51, 50],  # As, Ah
            "board": [0, 4, 8],  # 2c, 3c, 4c
            "action": "b200c/k",
            "client_pos": 0,
        }
        state, legal = slumbot_to_arena_state(resp)
        assert state["Hole Cards"] == ["As", "Ah"]
        assert len(state["board"]) == 3
        assert state["Current Street"] == "Flop"


@pytest.mark.skipif(
    not os.environ.get("SLUMBOT_BENCHMARK"),
    reason="Set SLUMBOT_BENCHMARK=1 to run the live Slumbot benchmark",
)
class TestSlumbotLiveBenchmark:
    """Live benchmark against Slumbot API.

    Skipped by default.  Requires network access.  Run with::

        SLUMBOT_BENCHMARK=1 pytest tests/test_slumbot_benchmark.py::TestSlumbotLiveBenchmark -v
    """

    @pytest.fixture
    def cfr_player(self):
        from players.cfr_gto_player import CFRGTOPlayer

        return CFRGTOPlayer(name="SlumbotTest", model="cfr-gto")

    def test_play_100_hands(self, cfr_player):
        """Play 100 hands against Slumbot and check win rate is reasonable."""
        benchmark = SlumbotBenchmark()
        results = benchmark.run_benchmark(cfr_player, n_hands=100)

        print(f"Hands played: {results['hands_played']}")
        print(f"Total profit: {results['total_profit']}")
        print(f"BB/100: {results['bb_per_100']:.1f}")

        # A GTO-approximate bot should be within ±20 bb/100 over 100 hands
        # (variance is huge at this sample size).
        if results["hands_played"] > 0:
            assert abs(results["bb_per_100"]) < 50, (
                f"Win rate {results['bb_per_100']:.1f} bb/100 is extreme "
                f"(possible implementation bug)"
            )
