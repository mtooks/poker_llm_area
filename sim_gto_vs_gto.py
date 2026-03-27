"""Quick head-to-head simulation: CFR-GTO vs CFR-GTO and heuristic GTO vs GTO."""

import asyncio
import sys
import os

# Patch game_config before importing main
import game_config

# --- Simulation 1: Heuristic GTO vs Heuristic GTO ---
def run_heuristic_gto_vs_gto(n_hands=100):
    """Run heuristic GTO vs heuristic GTO."""
    game_config.GAME_CONFIG = {
        "hands": n_hands,
        "blinds": (1, 2),
        "initial_stack": 1000,
        "rng_seed": 42,
        "see_model_monologue": False,
        "min_bet": 2,
        "ante_amount": 0,
        "enable_reflection": False,
    }
    game_config.PLAYER_CONFIGS = [
        {"name": "GTO-Heuristic-A", "provider": "gto", "model": "gto-bot", "enable_reflection": False},
        {"name": "GTO-Heuristic-B", "provider": "gto", "model": "gto-bot", "enable_reflection": False},
    ]

    from main import GameOrchestrator
    game = GameOrchestrator(hands=n_hands)
    asyncio.run(game.run())
    return game


# --- Simulation 2: CFR-GTO vs CFR-GTO ---
def run_cfr_gto_vs_cfr_gto(n_hands=100):
    """Run CFR-GTO vs CFR-GTO."""
    game_config.GAME_CONFIG = {
        "hands": n_hands,
        "blinds": (1, 2),
        "initial_stack": 1000,
        "rng_seed": 42,
        "see_model_monologue": False,
        "min_bet": 2,
        "ante_amount": 0,
        "enable_reflection": False,
    }
    game_config.PLAYER_CONFIGS = [
        {"name": "CFR-GTO-A", "provider": "cfr-gto", "model": "cfr-gto", "enable_reflection": False},
        {"name": "CFR-GTO-B", "provider": "cfr-gto", "model": "cfr-gto", "enable_reflection": False},
    ]

    # Need to reimport to pick up new config
    # Clear cached modules so GameOrchestrator re-reads config
    if 'main' in sys.modules:
        del sys.modules['main']
    from main import GameOrchestrator
    game = GameOrchestrator(hands=n_hands)
    asyncio.run(game.run())
    return game


# --- Simulation 3: CFR-GTO vs Heuristic GTO ---
def run_cfr_vs_heuristic(n_hands=100):
    """Run CFR-GTO vs Heuristic GTO."""
    game_config.GAME_CONFIG = {
        "hands": n_hands,
        "blinds": (1, 2),
        "initial_stack": 1000,
        "rng_seed": 42,
        "see_model_monologue": False,
        "min_bet": 2,
        "ante_amount": 0,
        "enable_reflection": False,
    }
    game_config.PLAYER_CONFIGS = [
        {"name": "CFR-GTO", "provider": "cfr-gto", "model": "cfr-gto", "enable_reflection": False},
        {"name": "Heuristic-GTO", "provider": "gto", "model": "gto-bot", "enable_reflection": False},
    ]

    if 'main' in sys.modules:
        del sys.modules['main']
    from main import GameOrchestrator
    game = GameOrchestrator(hands=n_hands)
    asyncio.run(game.run())
    return game


if __name__ == "__main__":
    N = 50  # hands per matchup

    print("=" * 60)
    print("  MATCHUP 1: Heuristic GTO vs Heuristic GTO")
    print("=" * 60)
    g1 = run_heuristic_gto_vs_gto(N)

    print("\n" + "=" * 60)
    print("  MATCHUP 2: CFR-GTO vs CFR-GTO")
    print("=" * 60)
    g2 = run_cfr_gto_vs_cfr_gto(N)

    print("\n" + "=" * 60)
    print("  MATCHUP 3: CFR-GTO vs Heuristic GTO")
    print("=" * 60)
    g3 = run_cfr_vs_heuristic(N)

    # Summary
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    for label, game in [("Heuristic vs Heuristic", g1), ("CFR vs CFR", g2), ("CFR vs Heuristic", g3)]:
        print(f"\n{label}:")
        for p in game.players:
            profit = p.stack - p.initial_stack
            print(f"  {p.name}: stack={p.stack}, profit={profit:+d}")
