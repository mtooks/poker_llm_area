"""Configuration file for the poker game."""

# Game settings
GAME_CONFIG = {
    "hands": 10,           # Number of hands to play
    "blinds": (50, 100),   # Small blind, big blind
    "initial_stack": 10000,  # Starting stack for each player
    "rng_seed": 42,        # Random seed for reproducibility
    "see_model_monologue": True,  # Toggle player commentary on/off
    "min_bet": 2,          # Minimum bet amount
    "ante_amount": 0,      # Ante amount per player (0 for no ante)
}

# Player configurations - easy to modify
PLAYER_CONFIGS = [
    {
        "name": "SamAltman",
        "provider": "openai", 
        "model": "gpt-4o-mini",  # Can be "gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"
    },
    {
        "name": "Grok",
        "provider": "grok",
        "model": "grok-3",  # Can be "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
    },
    # {
    #     "name": "Claude",
    #     "provider": "anthropic",
    #     "model": "claude-3-5-haiku-latest",  # Can be "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
    # },
    # {
    #     "name": "sonnet",
    #     "provider": "anthropic",
    #     "model": "claude-3-7-sonnet-latest",  # Can be "claude-3-sonnet", "claude-3-haiku", "claude-3-opus"
    # },
    # {
    #     "name": "Chamath",
    #     "provider": "all-in",
    #     "model": "all-in-bot",
    # }
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