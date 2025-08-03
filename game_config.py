"""Configuration file for the poker game."""

# Game settings
GAME_CONFIG = {
    "hands": 2,           # Number of hands to play
    "blinds": (50, 100),   # Small blind, big blind
    "initial_stack": 400,  # Starting stack for each player
    "rng_seed": 42,        # Random seed for reproducibility
}

# Player configurations - easy to modify
PLAYER_CONFIGS = [
    {
        "name": "GPT-4",
        "provider": "openai", 
        "model": "gpt-4o-mini",  # Can be "gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"
    },
    {
        "name": "Claude",
        "provider": "anthropic",
        "model": "claude-3-5-haiku-latest",  # Can be "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
    },
    # {
    #     "name": "Claude2",
    #     "provider": "anthropic",
    #     "model": "claude-3-5-haiku-latest",  # Can be "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
    # },
]

# Alternative configurations you can use:

# Example 1: Different models
# PLAYER_CONFIGS = [
#     {"name": "GPT-3.5", "provider": "openai", "model": "gpt-3.5-turbo"},
#     {"name": "Claude-Haiku", "provider": "anthropic", "model": "claude-3-haiku"},
# ]

# Example 2: Add Gemini
# PLAYER_CONFIGS = [
#     {"name": "GPT-4", "provider": "openai", "model": "gpt-4"},
#     {"name": "Gemini", "provider": "gemini", "model": "gemini-pro"},
#     {"name": "Claude", "provider": "anthropic", "model": "claude-3-sonnet"},
# ]

# Example 3: Use default models (factory will pick first available)
# PLAYER_CONFIGS = [
#     {"name": "OpenAI Player", "provider": "openai"},  # Will use gpt-4
#     {"name": "Gemini Player", "provider": "gemini"},  # Will use gemini-pro
#     {"name": "Claude Player", "provider": "anthropic"},  # Will use claude-3-sonnet
# ] 