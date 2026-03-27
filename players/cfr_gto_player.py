"""GTO player backed by precomputed CFR+ Nash equilibrium strategy."""

from __future__ import annotations

import json
import os
import random
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_player import BasePlayer


class CFRGTOPlayer(BasePlayer):
    """GTO player that uses precomputed CFR+ Nash equilibrium strategies.

    Instead of rule-based heuristics, this player looks up the equilibrium
    mixed strategy for each game state and *samples* from it.  This means it
    will sometimes bluff, sometimes check-raise, sometimes fold strong hands
    — all at theoretically correct frequencies.

    Requires precomputed solver artifacts.  Run ``python -m solver.precompute``
    to generate them before using this player.
    """

    def __init__(
        self,
        name: str,
        model: str = "cfr-gto",
        initial_stack: int = 400,
        system_prompt: Optional[str] = None,
        enable_reflection: bool = False,
        policy_path: Optional[str] = None,
        buckets_path: Optional[str] = None,
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=False,
        )
        self._mapper = None
        self._policy_path = policy_path
        self._buckets_path = buckets_path
        self._init_failed = False
        self._load_solver()

    def _load_solver(self) -> None:
        """Lazily load the precomputed policy and card buckets."""
        if self._mapper is not None:
            return
        try:
            from solver.state_mapper import StateMapper
            from solver.card_abstraction import CardAbstraction
            from solver.solve import load_policy

            policy = load_policy(self._policy_path)
            buckets = CardAbstraction()
            buckets.load(self._buckets_path)
            self._mapper = StateMapper(policy=policy, card_buckets=buckets)
        except FileNotFoundError:
            # Policy not precomputed — fall back to heuristic mode.
            self._init_failed = True
        except Exception as e:
            self._init_failed = True

    # ------------------------------------------------------------------
    # BasePlayer interface
    # ------------------------------------------------------------------

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        state, legal = self._extract_state_and_legal(messages)
        if not state:
            return "check@No readable state; defaulting to check"

        # Show/muck decisions — always show.
        if (
            state.get("decision_type") == "show_or_muck"
            or "show" in legal
            or "muck" in legal
        ):
            return "show@Always show to claim the pot"

        action, reason = self._decide(state, legal)
        return f"{action}@{reason}"

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def _decide(
        self, state: Dict[str, Any], legal_actions: List[str]
    ) -> Tuple[str, str]:
        """Pick an action using the precomputed Nash strategy (or fallback)."""
        if self._init_failed or self._mapper is None:
            return self._heuristic_decide(state, legal_actions)

        hole_cards = state.get("Hole Cards", [])
        board = state.get("board", [])
        street = state.get("Current Street", "preflop")
        pot = state.get("Pot size", 0) or 0
        stack = state.get("Your stack", self.stack)
        history = state.get("history", [])
        # Also accept 'betting_history' key
        if not history:
            history = state.get("betting_history", [])

        strategy = self._mapper.get_strategy(
            hole_cards=hole_cards,
            board=board,
            street=street,
            pot=pot,
            stack=stack,
            history=history,
            legal_actions=legal_actions,
        )

        arena_action = self._mapper.choose_arena_action(
            strategy, legal_actions, pot, stack
        )

        return arena_action, "GTO equilibrium play (CFR+)"

    # ------------------------------------------------------------------
    # Heuristic fallback (mirrors GTOPlayer logic for when solver data
    # is not available)
    # ------------------------------------------------------------------

    def _heuristic_decide(
        self, state: Dict[str, Any], legal_actions: List[str]
    ) -> Tuple[str, str]:
        """Simple heuristic fallback when solver data is unavailable."""
        to_call = state.get("to_call", 0) or 0
        pot = state.get("Pot size", 0) or 0

        if to_call == 0:
            if "check" in legal_actions:
                return "check", "Heuristic fallback: checking (no solver data)"
            return "call", "Heuristic fallback: calling"

        pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0
        if pot_odds > 0.4 and "fold" in legal_actions:
            return "fold", "Heuristic fallback: folding on poor odds"
        if "call" in legal_actions:
            return "call", "Heuristic fallback: calling with adequate odds"
        if "check" in legal_actions:
            return "check", "Heuristic fallback: checking"
        return "fold", "Heuristic fallback: no safe option"

    # ------------------------------------------------------------------
    # Helpers (shared with GTOPlayer)
    # ------------------------------------------------------------------

    def _extract_state_and_legal(
        self, messages: Sequence[Dict[str, str]]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Pull state and legal moves from the latest user message."""
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            try:
                payload = json.loads(msg.get("content", "{}"))
            except json.JSONDecodeError:
                continue
            return payload.get("state", {}), payload.get("legal", [])
        return {}, []
