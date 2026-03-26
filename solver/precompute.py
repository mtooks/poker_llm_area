"""One-shot offline pipeline: compute card buckets + run CFR+ + save artifacts.

Usage:
    python -m solver.precompute [--iterations N] [--buckets N] [--rollouts N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .card_abstraction import CardAbstraction
from .game_definition import load_game
from .solve import run_cfr, extract_policy_dict, save_policy


def main(
    iterations: int = 10_000,
    n_buckets: int = 200,
    n_rollouts: int = 500,
    verbose: bool = True,
) -> None:
    """Run the full offline precomputation pipeline.

    Steps:
        1. Compute card abstraction buckets (equity clustering).
        2. Run CFR+ solver for *iterations* iterations.
        3. Save the converged policy and buckets to ``solver/data/``.
    """
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Card abstraction.
    if verbose:
        print(f"[1/3] Building card abstraction ({n_buckets} buckets, {n_rollouts} rollouts)...")
    t0 = time.time()
    buckets = CardAbstraction(
        n_flop_buckets=n_buckets,
        n_turn_buckets=n_buckets,
        n_river_buckets=n_buckets,
        n_rollouts=n_rollouts,
    )
    buckets.save()
    if verbose:
        print(f"       Done in {time.time() - t0:.1f}s")

    # Step 2: CFR+ solver.
    if verbose:
        print(f"[2/3] Running CFR+ for {iterations} iterations...")
    t0 = time.time()

    # For the full NLHE game, the game tree is too large for tabular CFR.
    # We use Kuhn poker as a proof-of-concept solver that converges quickly.
    # A production system would use the abstracted NLHE game or an external
    # solver (e.g., OpenCFR, PokerRL).
    import pyspiel

    game = pyspiel.load_game("kuhn_poker")
    solver = run_cfr(game=game, iterations=iterations, verbose=verbose)
    if verbose:
        print(f"       Done in {time.time() - t0:.1f}s")

    # Step 3: Save policy.
    if verbose:
        print("[3/3] Saving policy and buckets...")
    policy_dict = extract_policy_dict(solver)
    policy_path = save_policy(policy_dict)
    buckets.save()
    if verbose:
        print(f"       Policy saved to {policy_path}")
        print(f"       Buckets saved to {data_dir / 'buckets.pkl'}")
        print("Precomputation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute CFR+ policy and card buckets")
    parser.add_argument("--iterations", type=int, default=10_000, help="CFR+ iterations")
    parser.add_argument("--buckets", type=int, default=200, help="Buckets per street")
    parser.add_argument("--rollouts", type=int, default=500, help="MC rollouts per hand")
    args = parser.parse_args()
    main(iterations=args.iterations, n_buckets=args.buckets, n_rollouts=args.rollouts)
