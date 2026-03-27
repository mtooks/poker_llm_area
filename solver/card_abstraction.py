"""Card abstraction via equity-based bucketing.

Hands are grouped into buckets by estimated equity so that the CFR solver
sees a tractable number of information states.  Preflop hands use the 169
canonical hand classes directly (no abstraction needed).  Post-flop hands
are clustered by Monte-Carlo equity into configurable bucket counts.
"""

from __future__ import annotations

import hashlib
import itertools
import os
import pickle
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from treys import Card, Deck, Evaluator

# Persistent cache directory.
_DATA_DIR = Path(__file__).resolve().parent / "data"


class CardAbstraction:
    """Equity-based card bucketing for each street."""

    def __init__(
        self,
        n_flop_buckets: int = 200,
        n_turn_buckets: int = 200,
        n_river_buckets: int = 200,
        n_rollouts: int = 500,
        seed: int = 42,
    ):
        self.n_flop_buckets = n_flop_buckets
        self.n_turn_buckets = n_turn_buckets
        self.n_river_buckets = n_river_buckets
        self.n_rollouts = n_rollouts
        self.seed = seed
        self._evaluator = Evaluator()
        self._preflop_buckets: Optional[Dict[str, int]] = None
        self._postflop_cache: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bucket(
        self,
        hole_cards: List[str],
        board: List[str],
        street: str,
    ) -> int:
        """Return the abstract bucket index for a hand + board on a given street.

        Parameters
        ----------
        hole_cards:
            Two-element list of card strings, e.g. ``["As", "Kh"]``.
        board:
            Board cards (0 for preflop, 3 for flop, 4 for turn, 5 for river).
        street:
            One of ``"pre flop"``, ``"preflop"``, ``"flop"``, ``"turn"``, ``"river"``.
        """
        street_lower = street.lower().strip()
        if street_lower in ("pre flop", "preflop"):
            return self._preflop_bucket(hole_cards)
        return self._postflop_bucket(hole_cards, board, street_lower)

    # ------------------------------------------------------------------
    # Preflop bucketing (169 canonical hands)
    # ------------------------------------------------------------------

    def _preflop_bucket(self, hole_cards: List[str]) -> int:
        """Map a preflop hand to one of 169 canonical hand classes."""
        if len(hole_cards) < 2:
            return 0
        r1, s1 = self._rank_suit(hole_cards[0])
        r2, s2 = self._rank_suit(hole_cards[1])
        high, low = max(r1, r2), min(r1, r2)
        suited = s1 == s2
        if high == low:
            # Pair — index 0..12
            return high
        if suited:
            return 13 + high * 13 + low
        else:
            return 13 + 13 * 13 + high * 13 + low

    # ------------------------------------------------------------------
    # Post-flop bucketing (equity-based)
    # ------------------------------------------------------------------

    def _postflop_bucket(
        self, hole_cards: List[str], board: List[str], street: str
    ) -> int:
        """Estimate hand equity via Monte-Carlo rollouts and map to a bucket."""
        cache_key = self._cache_key(hole_cards, board)
        if cache_key in self._postflop_cache:
            return self._postflop_cache[cache_key]

        equity = self._estimate_equity(hole_cards, board)

        if street == "flop":
            n_buckets = self.n_flop_buckets
        elif street == "turn":
            n_buckets = self.n_turn_buckets
        else:
            n_buckets = self.n_river_buckets

        bucket = min(int(equity * n_buckets), n_buckets - 1)
        self._postflop_cache[cache_key] = bucket
        return bucket

    def _estimate_equity(self, hole_cards: List[str], board: List[str]) -> float:
        """Estimate equity of *hole_cards* on *board* via Monte-Carlo rollout."""
        try:
            hand = [Card.new(c) for c in hole_cards]
            board_cards = [Card.new(c) for c in board]
        except (KeyError, ValueError):
            return 0.5  # fallback for unparseable cards

        # Build the remaining deck.
        full_deck = Deck.GetFullDeck()
        dead = set(hand) | set(board_cards)
        remaining = [c for c in full_deck if c not in dead]

        cards_to_deal = 5 - len(board_cards)  # complete the board
        if cards_to_deal < 0:
            cards_to_deal = 0

        rng = random.Random(self.seed)
        wins = 0
        ties = 0
        total = 0

        for _ in range(self.n_rollouts):
            rng.shuffle(remaining)
            # Deal remaining board cards + 2 opponent hole cards.
            needed = cards_to_deal + 2
            if len(remaining) < needed:
                break
            sampled = remaining[:needed]
            sim_board = board_cards + sampled[:cards_to_deal]
            opp_hand = sampled[cards_to_deal : cards_to_deal + 2]

            try:
                my_score = self._evaluator.evaluate(sim_board, hand)
                opp_score = self._evaluator.evaluate(sim_board, opp_hand)
            except Exception:
                continue

            # Lower score = better hand in treys.
            if my_score < opp_score:
                wins += 1
            elif my_score == opp_score:
                ties += 1
            total += 1

        if total == 0:
            return 0.5
        return (wins + 0.5 * ties) / total

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> None:
        """Persist the post-flop bucket cache to disk."""
        path = path or str(_DATA_DIR / "buckets.pkl")
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "postflop_cache": self._postflop_cache,
                    "n_flop_buckets": self.n_flop_buckets,
                    "n_turn_buckets": self.n_turn_buckets,
                    "n_river_buckets": self.n_river_buckets,
                },
                f,
            )

    def load(self, path: Optional[str] = None) -> None:
        """Load a previously saved bucket cache from disk."""
        path = path or str(_DATA_DIR / "buckets.pkl")
        if not os.path.exists(path):
            return
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._postflop_cache = data.get("postflop_cache", {})
        self.n_flop_buckets = data.get("n_flop_buckets", self.n_flop_buckets)
        self.n_turn_buckets = data.get("n_turn_buckets", self.n_turn_buckets)
        self.n_river_buckets = data.get("n_river_buckets", self.n_river_buckets)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rank_suit(card: str) -> Tuple[int, str]:
        """Parse a card string like ``'As'`` into (rank_index, suit_char)."""
        ranks = "23456789TJQKA"
        card = card.strip()
        if card.upper().startswith("10"):
            rank_char = "T"
            suit = card[-1].lower()
        else:
            rank_char = card[0].upper()
            suit = card[-1].lower()
        return ranks.index(rank_char) if rank_char in ranks else 0, suit

    @staticmethod
    def _cache_key(hole_cards: List[str], board: List[str]) -> str:
        """Deterministic cache key for a hand + board combination."""
        key = "|".join(sorted(hole_cards)) + "||" + "|".join(sorted(board))
        return key
