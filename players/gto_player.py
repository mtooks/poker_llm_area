"""Deterministic GTO-inspired player for benchmarking LLM bots."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_player import BasePlayer


class GTOPlayer(BasePlayer):
    """Rule-based player that approximates GTO lines without LLM calls."""

    RANKS = "23456789TJQKA"
    RANK_TO_VALUE = {rank: idx + 2 for idx, rank in enumerate(RANKS)}

    def __init__(
        self,
        name: str,
        model: str = "gto-bot",
        initial_stack: int = 400,
        system_prompt: Optional[str] = None,
        enable_reflection: bool = False,
        aggression: float = 1.0,
        tightness: float = 0.0,
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=False,
        )
        self.aggression = aggression
        self.tightness = tightness

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        state, legal = self._extract_state_and_legal(messages)
        if not state:
            return "check@No readable state; defaulting to check"

        if state.get("decision_type") == "show_or_muck" or "show" in legal or "muck" in legal:
            return "show@Always show to claim the pot"

        action, reason = self._decide_action(state, legal)
        return f"{action}@{reason}"

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

    def _decide_action(self, state: Dict[str, Any], legal_actions: List[str]) -> Tuple[str, str]:
        hole_cards = state.get("Hole Cards", [])
        board_cards = state.get("board", [])
        street = (state.get("Current Street") or "").lower()
        to_call = state.get("to_call", 0) or 0
        pot = state.get("Pot size", 0) or 0
        stack = state.get("Your stack", self.stack)
        position = state.get("Position", "")

        min_raise, max_raise = self._parse_raise_bounds(legal_actions)
        can_raise = min_raise is not None

        if street == "pre flop":
            strength = self._preflop_strength(hole_cards)
        else:
            strength = self._postflop_strength(hole_cards, board_cards)

        if position == "Button":
            strength += 0.03
        elif position == "Big Blind" and to_call > 0:
            strength -= 0.02

        strength *= 1 + 0.15 * (self.aggression - 1.0)
        strength -= 0.05 * self.tightness
        strength = self._clamp(strength)

        pot_odds = to_call / (pot + to_call) if to_call else 0

        if to_call == 0:
            if can_raise and strength > (0.55 - 0.05 * self.tightness):
                amount = self._select_raise_amount(min_raise, max_raise, pot, stack, strength, to_call)
                return f"raise_to: {amount}", "Taking initiative with a strong opening range"
            if "check" in legal_actions:
                return "check", "Checking range to realize equity"
            return "call", "Calling as safest zero-cost option"

        if strength + 0.05 < pot_odds and "fold" in legal_actions:
            return "fold", f"Folding; equity estimate {strength:.2f} behind pot odds {pot_odds:.2f}"

        raise_gate = max(pot_odds + 0.12, 0.62 - 0.05 * self.tightness)
        if can_raise and strength > raise_gate:
            amount = self._select_raise_amount(min_raise, max_raise, pot, stack, strength, to_call)
            return f"raise_to: {amount}", "Applying pressure with value-heavy range"

        if "call" in legal_actions:
            return "call", "Defending with sufficient equity versus price"
        if "check" in legal_actions:
            return "check", "Taking the free card when possible"
        if can_raise:
            return f"raise_to: {min_raise}", "Only legal aggressive option remains"
        return "fold", "No safe legal option available"

    def _select_raise_amount(
        self,
        min_raise: int,
        max_raise: Optional[int],
        pot: int,
        stack: int,
        strength: float,
        to_call: int,
    ) -> int:
        """Choose a raise size anchored to pot and hand strength."""
        max_raise = max_raise or stack
        pot_factor = 0.7 + 0.6 * strength
        base = (pot + to_call) * pot_factor

        if to_call == 0 and pot == 0:
            base = min_raise * (1.3 + 0.6 * max(strength - 0.5, 0))

        target = int(base) if base > 0 else min_raise
        target = max(min_raise, target)
        target = min(target, max_raise, stack)
        return target

    def _preflop_strength(self, hole_cards: List[str]) -> float:
        parsed = self._parse_cards(hole_cards)
        if len(parsed) < 2:
            return 0.5

        (r1, s1), (r2, s2) = parsed[:2]
        suited = s1 == s2
        pair = r1 == r2
        gap = abs(r1 - r2)
        high, low = max(r1, r2), min(r1, r2)

        score = (high + low) / 28.0
        if pair:
            score = 0.55 + (high - 2) / 20.0
        if suited:
            score += 0.04
        if gap == 1:
            score += 0.04
        elif gap == 2:
            score += 0.02
        elif gap >= 4:
            score -= 0.05
        if high >= 13 and low >= 10:
            score += 0.05
        elif high >= 11 and low >= 9:
            score += 0.03
        return self._clamp(score)

    def _postflop_strength(self, hole_cards: List[str], board_cards: List[str]) -> float:
        cards = self._parse_cards(hole_cards + board_cards)
        if len(cards) < 2:
            return 0.45

        category, high = self._categorize_hand(cards)
        category_score = {
            "high_card": 0.4,
            "pair": 0.52,
            "two_pair": 0.6,
            "three_kind": 0.7,
            "straight": 0.8,
            "flush": 0.82,
            "full_house": 0.9,
            "four_kind": 0.95,
            "straight_flush": 1.0,
        }.get(category, 0.5)

        kicker_boost = (high - 2) / 12 * 0.1 if high else 0
        suits = [s for _, s in cards]
        values = [v for v, _ in cards]
        flush_draw = self._has_flush_draw(suits)
        straight_draw = self._has_straight_draw(values)

        score = category_score + kicker_boost
        if flush_draw and category_score < 0.8:
            score += 0.07
        if straight_draw and category_score < 0.8:
            score += 0.05
        if category in {"high_card", "pair"} and len(board_cards) >= 4:
            score -= 0.05

        return self._clamp(score)

    def _categorize_hand(self, cards: List[Tuple[int, str]]) -> Tuple[str, int]:
        values = [v for v, _ in cards]
        suits = [s for _, s in cards]
        counts = Counter(values)

        flush_suit, flush_values = self._flush_info(cards)
        straight_high = self._straight_high(values)

        if flush_suit:
            sf_high = self._straight_high([v for v, s in cards if s == flush_suit])
            if sf_high:
                return "straight_flush", sf_high

        if 4 in counts.values():
            four_rank = max(v for v, c in counts.items() if c == 4)
            return "four_kind", four_rank

        triples = [v for v, c in counts.items() if c == 3]
        pairs = [v for v, c in counts.items() if c == 2]
        if triples and (pairs or len(triples) > 1):
            return "full_house", max(triples)

        if flush_suit:
            return "flush", max(flush_values)

        if straight_high:
            return "straight", straight_high

        if triples:
            return "three_kind", max(triples)

        if len(pairs) >= 2:
            return "two_pair", max(pairs)

        if pairs:
            return "pair", pairs[0]

        return "high_card", max(values)

    def _flush_info(self, cards: List[Tuple[int, str]]) -> Tuple[Optional[str], List[int]]:
        suits = [s for _, s in cards]
        suit_counts = Counter(suits)
        for suit, count in suit_counts.items():
            if count >= 5:
                suited_values = [v for v, s in cards if s == suit]
                return suit, suited_values
        return None, []

    def _straight_high(self, values: List[int]) -> Optional[int]:
        uniq = sorted(set(values))
        if 14 in uniq:
            uniq.insert(0, 1)

        run = 1
        best = None
        for i in range(1, len(uniq)):
            if uniq[i] == uniq[i - 1] + 1:
                run += 1
                if run >= 5:
                    best = uniq[i]
            else:
                run = 1
        return best

    def _has_straight_draw(self, values: List[int]) -> bool:
        uniq = sorted(set(values))
        if 14 in uniq:
            uniq.insert(0, 1)
        for i in range(len(uniq) - 3):
            window = uniq[i : i + 4]
            if window[-1] - window[0] <= 4:
                return True
        return False

    def _has_flush_draw(self, suits: List[str]) -> bool:
        return max(Counter(suits).values(), default=0) == 4

    def _parse_raise_bounds(self, legal_actions: List[str]) -> Tuple[Optional[int], Optional[int]]:
        for action in legal_actions:
            if not action.lower().startswith("raise_to"):
                continue
            match = re.search(r"raise_to\s*:\s*(\d+)(?:\s+to\s+(\d+))?", action.lower())
            if not match:
                continue
            min_raise = int(match.group(1))
            max_raise = int(match.group(2)) if match.group(2) else None
            return min_raise, max_raise
        return None, None

    def _parse_cards(self, cards: List[str]) -> List[Tuple[int, str]]:
        parsed: List[Tuple[int, str]] = []
        for card in cards:
            if not card:
                continue
            text = str(card).strip().upper()
            if not text:
                continue
            if text.startswith("10"):
                rank_char = "T"
                suit = text[-1]
            else:
                rank_char, suit = text[0], text[-1]
            if rank_char not in self.RANK_TO_VALUE:
                continue
            parsed.append((self.RANK_TO_VALUE[rank_char], suit))
        return parsed

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))
