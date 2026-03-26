"""Translate between PokerKit arena state and OpenSpiel/ACPC formats."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple


class FormatTranslator:
    """Bridges the PokerKit arena representation and OpenSpiel ACPC format.

    The arena sends game state as a JSON dict with human-readable history
    entries.  The CFR solver indexes policies by ACPC-style action strings.
    This class converts between the two worlds.
    """

    # Abstract bet sizes as fractions of pot.
    # ``inf`` represents an all-in shove.
    ABSTRACT_SIZES = [0.33, 0.67, 1.0, float("inf")]

    # Street names in the arena mapped to ACPC round indices.
    STREET_TO_ROUND = {
        "pre flop": 0,
        "preflop": 0,
        "flop": 1,
        "turn": 2,
        "river": 3,
    }

    # ------------------------------------------------------------------
    # Arena → ACPC
    # ------------------------------------------------------------------

    def arena_history_to_acpc(
        self,
        history: List[str],
        street_boundaries: Optional[List[int]] = None,
    ) -> str:
        """Convert an arena betting history list to an ACPC action string.

        Blinds / antes / board-deal entries are skipped (they are implicit in
        the GAMEDEF).  Street separators (``/``) are inserted when the street
        changes.

        Parameters
        ----------
        history:
            List of human-readable action strings from the arena, e.g.
            ``["Player 1 posts blind: 1", "Player 2 posts blind: 2",
              "Player 1 raises to 6", "Player 2 calls 4",
              "Board dealt: 7d, 2c, Ah", "Player 2 bets 100"]``
        street_boundaries:
            Optional list of indices where new streets begin.  If ``None``,
            boundaries are inferred from ``"Board dealt"`` entries.

        Returns
        -------
        str
            ACPC action string, e.g. ``"r6c/r100"``.
        """
        acpc_actions: List[str] = []
        current_round = 0

        for entry in history:
            lower = entry.lower()

            # Skip non-action entries.
            if any(
                kw in lower
                for kw in ("posts blind", "posts ante", "dealt hole", "wins", "shows", "mucks")
            ):
                continue

            # Street change marker.
            if "board dealt" in lower or "board:" in lower:
                current_round += 1
                acpc_actions.append("/")
                continue

            if "folds" in lower or "fold" in lower:
                acpc_actions.append("f")
            elif "checks" in lower or "check" in lower:
                acpc_actions.append("c")
            elif "calls" in lower or "call" in lower:
                acpc_actions.append("c")
            elif "raises to" in lower or "raise" in lower or "bets" in lower or "bet" in lower:
                amount = self._parse_amount(entry)
                if amount is not None:
                    acpc_actions.append(f"r{amount}")
                else:
                    acpc_actions.append("c")  # fallback

        return "".join(acpc_actions)

    # ------------------------------------------------------------------
    # Bet snapping
    # ------------------------------------------------------------------

    def snap_to_abstract_bet(self, actual_bet: int, pot: int) -> str:
        """Snap a concrete bet amount to the nearest abstract bet size.

        Parameters
        ----------
        actual_bet:
            The actual bet amount in chips.
        pot:
            The current pot size in chips.

        Returns
        -------
        str
            An ACPC-formatted action, e.g. ``"r150"`` or ``"all-in"``.
        """
        if pot <= 0:
            return f"r{actual_bet}"

        ratio = actual_bet / pot
        nearest = min(self.ABSTRACT_SIZES, key=lambda x: abs(x - ratio))
        if nearest == float("inf"):
            return "all-in"
        abstract_amount = int(pot * nearest)
        return f"r{max(abstract_amount, 1)}"

    def snap_all_bets_to_abstract(self, acpc_history: str, pot: int) -> str:
        """Re-write every raise in *acpc_history* to the nearest abstract size."""
        parts: List[str] = []
        running_pot = pot
        i = 0
        while i < len(acpc_history):
            ch = acpc_history[i]
            if ch == "r":
                j = i + 1
                while j < len(acpc_history) and acpc_history[j].isdigit():
                    j += 1
                amount = int(acpc_history[i + 1 : j]) if j > i + 1 else 0
                snapped = self.snap_to_abstract_bet(amount, running_pot)
                parts.append(snapped)
                running_pot += amount
                i = j
            else:
                parts.append(ch)
                i += 1
        return "".join(parts)

    # ------------------------------------------------------------------
    # Abstract → Arena (outbound)
    # ------------------------------------------------------------------

    def abstract_action_to_arena(
        self,
        action: str,
        legal_actions: List[str],
        pot: int,
        stack: int,
    ) -> str:
        """Convert an ACPC abstract action to an arena-formatted action string.

        Parameters
        ----------
        action:
            ACPC action, one of ``"f"``, ``"c"``, or ``"r{amount}"``.
        legal_actions:
            List of legal arena actions, e.g. ``["fold", "call", "raise_to: 4 to 1000"]``.
        pot:
            Current pot size.
        stack:
            Player's remaining stack.

        Returns
        -------
        str
            Arena-formatted action, e.g. ``"raise_to: 150"``.
        """
        if action == "f":
            if "fold" in legal_actions:
                return "fold"
            return "check" if "check" in legal_actions else "call"

        if action == "c":
            if "check" in legal_actions:
                return "check"
            if "call" in legal_actions:
                return "call"
            return "check"

        # Raise actions.
        if action.startswith("r") or action == "all-in":
            min_raise, max_raise = self._parse_raise_bounds(legal_actions)
            if min_raise is None:
                # Cannot raise — fall back to call/check.
                if "call" in legal_actions:
                    return "call"
                return "check" if "check" in legal_actions else "fold"

            if action == "all-in":
                target = max_raise or stack
            else:
                target = int(action[1:]) if len(action) > 1 else min_raise

            clamped = max(min_raise, min(target, max_raise or stack))
            return f"raise_to: {clamped}"

        # Unknown action — safe fallback.
        if "check" in legal_actions:
            return "check"
        if "call" in legal_actions:
            return "call"
        return "fold"

    # ------------------------------------------------------------------
    # Off-tree handling
    # ------------------------------------------------------------------

    def handle_off_tree(
        self,
        actual_history: str,
        abstract_history: str,
        policy: dict,
    ) -> Dict[str, float]:
        """Look up the strategy for *abstract_history*, with off-tree fallback.

        When the actual game diverges from the abstract game tree (e.g. an
        opponent uses a bet size that doesn't exist in the abstraction), we
        snap to the nearest existing node.

        Returns a dict mapping abstract actions to probabilities.
        """
        # Exact match.
        if abstract_history in policy:
            return policy[abstract_history]

        # Try snapping the last action.
        snapped = self._snap_last_action(abstract_history)
        if snapped in policy:
            return policy[snapped]

        # Fallback: default strategy (check/call if possible).
        return self.default_strategy()

    def default_strategy(self) -> Dict[str, float]:
        """Return a conservative default strategy when off-tree."""
        return {"c": 0.7, "f": 0.3}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_amount(entry: str) -> Optional[int]:
        """Extract a numeric chip amount from a history entry string."""
        # Match patterns like "raises to 600", "bets 100", "calls 50"
        m = re.search(r"(?:raises?\s+to|bets?|calls?)\s+(\d+)", entry, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # Fallback: last number in the string
        nums = re.findall(r"\d+", entry)
        return int(nums[-1]) if nums else None

    @staticmethod
    def _parse_raise_bounds(legal_actions: List[str]) -> Tuple[Optional[int], Optional[int]]:
        """Extract min and max raise amounts from the legal actions list."""
        for action in legal_actions:
            if not action.lower().startswith("raise_to"):
                continue
            m = re.search(r"raise_to\s*:\s*(\d+)(?:\s+to\s+(\d+))?", action, re.IGNORECASE)
            if m:
                min_r = int(m.group(1))
                max_r = int(m.group(2)) if m.group(2) else None
                return min_r, max_r
        return None, None

    @staticmethod
    def _snap_last_action(history: str) -> str:
        """Remove or simplify the last action in an ACPC history string."""
        if not history:
            return history
        # Drop last character / action token and retry.
        if history[-1] in ("f", "c", "/"):
            return history[:-1]
        # Drop trailing raise "r<digits>".
        m = re.search(r"r\d+$", history)
        if m:
            return history[: m.start()]
        return history[:-1]
