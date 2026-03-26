"""Orchestrate translation + card bucketing + policy lookup.

This is the main interface that the CFR-GTO player calls to convert a
PokerKit arena game state into a solver lookup and return a sampled action.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from .card_abstraction import CardAbstraction
from .format_translator import FormatTranslator


class StateMapper:
    """Map arena game states to precomputed Nash equilibrium strategies."""

    def __init__(
        self,
        policy: dict,
        card_buckets: Optional[CardAbstraction] = None,
        translator: Optional[FormatTranslator] = None,
    ):
        self.policy = policy
        self.card_buckets = card_buckets or CardAbstraction()
        self.translator = translator or FormatTranslator()

    # ------------------------------------------------------------------
    # Strategy lookup
    # ------------------------------------------------------------------

    def get_strategy(
        self,
        hole_cards: List[str],
        board: List[str],
        street: str,
        pot: int,
        stack: int,
        history: List[str],
        legal_actions: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """Return the action probability distribution for this game state.

        Parameters
        ----------
        hole_cards:
            Player's two hole cards, e.g. ``["As", "Kh"]``.
        board:
            Community cards dealt so far.
        street:
            Current street name (``"preflop"``, ``"flop"``, etc.).
        pot:
            Current pot size in chips.
        stack:
            Player's remaining stack.
        history:
            Arena betting history (list of human-readable action strings).
        legal_actions:
            Legal arena actions (used for fallback only).

        Returns
        -------
        dict
            Mapping from abstract action (``"f"``, ``"c"``, ``"r<N>"``) to
            probability.
        """
        # 1. Translate arena history → ACPC action sequence.
        acpc_history = self.translator.arena_history_to_acpc(history)
        abstract_history = self.translator.snap_all_bets_to_abstract(acpc_history, pot)

        # 2. Get the card bucket for this hand + board.
        bucket = self.card_buckets.get_bucket(hole_cards, board, street)

        # 3. Build a lookup key combining bucket + history.
        info_state = self._build_info_state_key(bucket, abstract_history, street)

        # 4. Look up in policy (with off-tree fallback).
        strategy = self.translator.handle_off_tree(
            acpc_history, info_state, self.policy
        )

        # If the policy stores integer action IDs, remap to ACPC letters.
        return self._normalize_strategy(strategy)

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def choose_arena_action(
        self,
        strategy: Dict[str, float],
        legal_actions: List[str],
        pot: int,
        stack: int,
    ) -> str:
        """Sample from *strategy* and return an arena-formatted action.

        Parameters
        ----------
        strategy:
            Mapping from abstract action to probability.
        legal_actions:
            Legal arena actions.
        pot:
            Current pot size.
        stack:
            Player's remaining stack.

        Returns
        -------
        str
            Arena-formatted action string.
        """
        actions = list(strategy.keys())
        weights = list(strategy.values())

        # Ensure weights sum to > 0.
        total = sum(weights)
        if total <= 0:
            return self.translator.abstract_action_to_arena("c", legal_actions, pot, stack)

        abstract_action = random.choices(actions, weights=weights, k=1)[0]

        # Handle integer action IDs from OpenSpiel policy.
        if isinstance(abstract_action, int):
            action_map = {0: "f", 1: "c", 2: "r"}
            abstract_action = action_map.get(abstract_action, "c")

        return self.translator.abstract_action_to_arena(
            str(abstract_action), legal_actions, pot, stack
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_info_state_key(
        self, bucket: int, abstract_history: str, street: str
    ) -> str:
        """Construct a lookup key for the policy dict."""
        return f"bucket_{bucket}|{street}|{abstract_history}"

    @staticmethod
    def _normalize_strategy(strategy: Dict[Any, float]) -> Dict[str, float]:
        """Ensure strategy keys are strings and values sum to 1."""
        total = sum(strategy.values())
        if total <= 0:
            return {"c": 1.0}
        return {str(k): v / total for k, v in strategy.items()}
