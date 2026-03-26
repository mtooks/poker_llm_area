"""Run the CFR+ solver on the abstracted NLHE game and serialize the policy."""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Dict, Optional

import pyspiel
from open_spiel.python.algorithms import cfr, exploitability

from .game_definition import load_game

_DATA_DIR = Path(__file__).resolve().parent / "data"


def run_cfr(
    game: Optional[pyspiel.Game] = None,
    iterations: int = 100_000,
    log_interval: int = 10_000,
    verbose: bool = True,
) -> cfr.CFRPlusSolver:
    """Run CFR+ on *game* for *iterations* and return the solver.

    Parameters
    ----------
    game:
        An OpenSpiel game object.  Defaults to the abstracted NLHE game.
    iterations:
        Number of CFR+ iterations to run.
    log_interval:
        How often to print progress (0 to disable).
    verbose:
        Whether to print progress messages.

    Returns
    -------
    cfr.CFRPlusSolver
        The solver object whose ``average_policy()`` is the Nash approximation.
    """
    if game is None:
        game = load_game()

    solver = cfr.CFRPlusSolver(game)

    for i in range(iterations):
        solver.evaluate_and_update_policy()
        if verbose and log_interval and (i + 1) % log_interval == 0:
            policy = solver.average_policy()
            try:
                exploit = exploitability.exploitability(game, policy)
                print(f"Iteration {i + 1}: exploitability = {exploit:.6f}")
            except Exception:
                print(f"Iteration {i + 1}: complete")

    return solver


def extract_policy_dict(solver: cfr.CFRPlusSolver) -> Dict[str, Dict[str, float]]:
    """Convert the solver's average policy to a plain dict.

    Returns
    -------
    dict
        Mapping from information-state string to action-probability dict.
        Example: ``{"[some_info_state]": {0: 0.6, 1: 0.4}}``.
    """
    policy = solver.average_policy()
    result: Dict[str, Dict[str, float]] = {}
    policy_dict = policy.to_dict()
    for info_state, action_probs_list in policy_dict.items():
        result[info_state] = {action: float(prob) for action, prob in action_probs_list}
    return result


def save_policy(policy_dict: dict, path: Optional[str] = None) -> str:
    """Pickle a policy dict to disk."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = path or str(_DATA_DIR / "policy.pkl")
    with open(path, "wb") as f:
        pickle.dump(policy_dict, f)
    return path


def load_policy(path: Optional[str] = None) -> dict:
    """Load a previously saved policy dict."""
    path = path or str(_DATA_DIR / "policy.pkl")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No precomputed policy found at {path}. "
            "Run `python -m solver.precompute` to generate it."
        )
    with open(path, "rb") as f:
        return pickle.load(f)
