"""Step 10: Validate solver — unit tests with Kuhn/Leduc exact equilibria.

These tests prove that CFR+ converges to Nash equilibrium on games with
known analytical solutions.  If they fail, nothing downstream can be
trusted.

Known reference values (from OpenSpiel's ``exploitability_test.py``):
  - Kuhn poker  uniform random → NashConv ≈ 11/12 ≈ 0.9167
  - Kuhn poker  Nash equilibrium → NashConv = 0.0
  - Leduc poker uniform random → NashConv ≈ 4.7472
"""

from __future__ import annotations

import pytest
import pyspiel
from open_spiel.python.algorithms import cfr, exploitability


# ------------------------------------------------------------------
# Kuhn poker tests
# ------------------------------------------------------------------


class TestKuhnPokerConvergence:
    """Verify CFR+ converges to Nash on Kuhn poker (3 cards, 2 players)."""

    def test_uniform_random_is_exploitable(self):
        """Uniform random play should have NashConv ≈ 0.458 (per-player)."""
        game = pyspiel.load_game("kuhn_poker")
        policy = pyspiel.UniformRandomPolicy(game)
        exploit = exploitability.exploitability(game, policy)
        # OpenSpiel reports per-player exploitability ≈ 0.458
        assert exploit > 0.4, f"Uniform random NashConv {exploit} unexpectedly low"

    def test_cfr_plus_converges(self):
        """CFR+ should converge to near-zero exploitability on Kuhn poker."""
        game = pyspiel.load_game("kuhn_poker")
        solver = cfr.CFRPlusSolver(game)

        for _ in range(10_000):
            solver.evaluate_and_update_policy()

        policy = solver.average_policy()
        exploit = exploitability.exploitability(game, policy)
        assert exploit < 1e-4, (
            f"Kuhn exploitability {exploit} too high (expected ~0)"
        )

    def test_exploitability_decreases_overall(self):
        """Exploitability should be lower after many iterations than after few."""
        game = pyspiel.load_game("kuhn_poker")
        solver = cfr.CFRPlusSolver(game)

        for _ in range(100):
            solver.evaluate_and_update_policy()
        policy_early = solver.average_policy()
        exploit_early = exploitability.exploitability(game, policy_early)

        for _ in range(4900):
            solver.evaluate_and_update_policy()
        policy_late = solver.average_policy()
        exploit_late = exploitability.exploitability(game, policy_late)

        assert exploit_late < exploit_early, (
            f"Exploitability did not decrease: {exploit_late} >= {exploit_early}"
        )


# ------------------------------------------------------------------
# Leduc poker tests
# ------------------------------------------------------------------


class TestLeducPokerConvergence:
    """Verify CFR+ converges on Leduc poker (6 cards, 2 players)."""

    def test_uniform_random_is_exploitable(self):
        """Uniform random play on Leduc should have high NashConv."""
        game = pyspiel.load_game("leduc_poker")
        policy = pyspiel.UniformRandomPolicy(game)
        exploit = exploitability.exploitability(game, policy)
        # OpenSpiel reports per-player exploitability ≈ 2.37
        assert exploit > 2.0, f"Leduc uniform random NashConv {exploit} unexpectedly low"

    def test_cfr_plus_converges(self):
        """CFR+ should achieve low exploitability on Leduc poker."""
        game = pyspiel.load_game("leduc_poker")
        solver = cfr.CFRPlusSolver(game)

        for _ in range(3_000):
            solver.evaluate_and_update_policy()

        policy = solver.average_policy()
        exploit = exploitability.exploitability(game, policy)
        assert exploit < 0.2, (
            f"Leduc exploitability {exploit} too high (expected < 0.2)"
        )

    def test_exploitability_decreases_overall(self):
        """Exploitability should be lower after many iterations than after few."""
        game = pyspiel.load_game("leduc_poker")
        solver = cfr.CFRPlusSolver(game)

        for _ in range(200):
            solver.evaluate_and_update_policy()
        policy_early = solver.average_policy()
        exploit_early = exploitability.exploitability(game, policy_early)

        for _ in range(2800):
            solver.evaluate_and_update_policy()
        policy_late = solver.average_policy()
        exploit_late = exploitability.exploitability(game, policy_late)

        assert exploit_late < exploit_early, (
            f"Leduc exploitability did not decrease: {exploit_late} >= {exploit_early}"
        )


# ------------------------------------------------------------------
# Solver module integration tests
# ------------------------------------------------------------------


class TestSolverModule:
    """Test the solver.solve module functions."""

    def test_run_cfr_returns_solver(self):
        """run_cfr should return a CFRPlusSolver with a valid average_policy."""
        from solver.solve import run_cfr

        game = pyspiel.load_game("kuhn_poker")
        solver = run_cfr(game=game, iterations=100, verbose=False)
        policy = solver.average_policy()
        assert policy is not None

    def test_extract_policy_dict(self):
        """extract_policy_dict should return a non-empty dict."""
        from solver.solve import run_cfr, extract_policy_dict

        game = pyspiel.load_game("kuhn_poker")
        solver = run_cfr(game=game, iterations=100, verbose=False)
        policy_dict = extract_policy_dict(solver)
        assert isinstance(policy_dict, dict)
        assert len(policy_dict) > 0

    def test_save_and_load_policy(self, tmp_path):
        """Policies should round-trip through save/load."""
        from solver.solve import run_cfr, extract_policy_dict, save_policy, load_policy

        game = pyspiel.load_game("kuhn_poker")
        solver = run_cfr(game=game, iterations=100, verbose=False)
        policy_dict = extract_policy_dict(solver)

        path = str(tmp_path / "test_policy.pkl")
        save_policy(policy_dict, path)
        loaded = load_policy(path)

        assert loaded.keys() == policy_dict.keys()


# ------------------------------------------------------------------
# Card abstraction tests
# ------------------------------------------------------------------


class TestCardAbstraction:
    """Test equity-based card bucketing."""

    def test_preflop_bucket_deterministic(self):
        """Same hand should always get the same preflop bucket."""
        from solver.card_abstraction import CardAbstraction

        ca = CardAbstraction()
        b1 = ca.get_bucket(["As", "Kh"], [], "preflop")
        b2 = ca.get_bucket(["As", "Kh"], [], "preflop")
        assert b1 == b2

    def test_preflop_pair_vs_offsuit(self):
        """Pocket aces should get a different bucket than 7-2 offsuit."""
        from solver.card_abstraction import CardAbstraction

        ca = CardAbstraction()
        aces = ca.get_bucket(["As", "Ah"], [], "preflop")
        seven_two = ca.get_bucket(["7s", "2h"], [], "preflop")
        assert aces != seven_two

    def test_postflop_bucket_range(self):
        """Post-flop bucket should be in [0, n_buckets)."""
        from solver.card_abstraction import CardAbstraction

        ca = CardAbstraction(n_flop_buckets=50, n_rollouts=100)
        bucket = ca.get_bucket(["As", "Kh"], ["7d", "2c", "Ah"], "flop")
        assert 0 <= bucket < 50

    def test_postflop_equity_ordering(self):
        """Stronger hands should generally get higher buckets."""
        from solver.card_abstraction import CardAbstraction

        ca = CardAbstraction(n_flop_buckets=100, n_rollouts=200)
        # Top pair top kicker vs no pair
        strong = ca.get_bucket(["As", "Kh"], ["Ah", "7d", "2c"], "flop")
        weak = ca.get_bucket(["3s", "4h"], ["Kd", "Qc", "Jh"], "flop")
        assert strong >= weak

    def test_save_and_load(self, tmp_path):
        """Bucket cache should round-trip through save/load."""
        from solver.card_abstraction import CardAbstraction

        ca = CardAbstraction(n_flop_buckets=50, n_rollouts=50)
        _ = ca.get_bucket(["As", "Kh"], ["7d", "2c", "Ah"], "flop")

        path = str(tmp_path / "test_buckets.pkl")
        ca.save(path)

        ca2 = CardAbstraction()
        ca2.load(path)
        assert ca2.n_flop_buckets == 50


# ------------------------------------------------------------------
# Format translator tests
# ------------------------------------------------------------------


class TestFormatTranslator:
    """Test arena ↔ ACPC format translation."""

    def test_arena_to_acpc_basic(self):
        """Basic betting sequence should translate correctly."""
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        history = [
            "Player 1 posts blind: 1",
            "Player 2 posts blind: 2",
            "Player 1 raises to 6",
            "Player 2 calls 4",
        ]
        result = ft.arena_history_to_acpc(history)
        assert result == "r6c"

    def test_arena_to_acpc_with_board(self):
        """Board deal should insert '/' separator."""
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        history = [
            "Player 1 posts blind: 1",
            "Player 2 posts blind: 2",
            "Player 1 raises to 6",
            "Player 2 calls 4",
            "Board dealt: 7d, 2c, Ah",
            "Player 2 bets 100",
        ]
        result = ft.arena_history_to_acpc(history)
        assert result == "r6c/r100"

    def test_abstract_action_to_arena_fold(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        assert ft.abstract_action_to_arena("f", ["fold", "call"], 100, 500) == "fold"

    def test_abstract_action_to_arena_check(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        assert ft.abstract_action_to_arena("c", ["check", "raise_to: 4 to 1000"], 100, 500) == "check"

    def test_abstract_action_to_arena_call(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        assert ft.abstract_action_to_arena("c", ["fold", "call", "raise_to: 4 to 1000"], 100, 500) == "call"

    def test_abstract_action_to_arena_raise(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        result = ft.abstract_action_to_arena("r150", ["fold", "call", "raise_to: 4 to 1000"], 100, 500)
        assert result == "raise_to: 150"

    def test_abstract_action_to_arena_raise_clamped(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        result = ft.abstract_action_to_arena("r2000", ["fold", "call", "raise_to: 4 to 1000"], 100, 500)
        assert result == "raise_to: 1000"

    def test_snap_to_abstract_bet(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        # 73% of 100 pot should snap to 67%
        result = ft.snap_to_abstract_bet(73, 100)
        assert result == "r67"

    def test_default_strategy(self):
        from solver.format_translator import FormatTranslator

        ft = FormatTranslator()
        strat = ft.default_strategy()
        assert "c" in strat
        assert sum(strat.values()) == pytest.approx(1.0)


# ------------------------------------------------------------------
# State mapper tests
# ------------------------------------------------------------------


class TestStateMapper:
    """Test the StateMapper orchestration layer."""

    def test_get_strategy_returns_distribution(self):
        """get_strategy should return a valid probability distribution."""
        from solver.state_mapper import StateMapper

        # Use empty policy — will hit fallback.
        mapper = StateMapper(policy={})
        strategy = mapper.get_strategy(
            hole_cards=["As", "Kh"],
            board=[],
            street="preflop",
            pot=3,
            stack=500,
            history=[],
        )
        assert isinstance(strategy, dict)
        assert len(strategy) > 0
        assert sum(strategy.values()) == pytest.approx(1.0)

    def test_choose_arena_action(self):
        """choose_arena_action should return a legal arena action string."""
        from solver.state_mapper import StateMapper

        mapper = StateMapper(policy={})
        strategy = {"c": 0.5, "f": 0.3, "r": 0.2}
        legal = ["check", "fold", "raise_to: 4 to 1000"]
        action = mapper.choose_arena_action(strategy, legal, 100, 500)
        # Should be one of the legal actions.
        assert any(
            action.startswith(prefix)
            for prefix in ("check", "fold", "call", "raise_to")
        )
