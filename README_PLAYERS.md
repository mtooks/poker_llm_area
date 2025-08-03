# Poker Players - Refactored Structure

This document describes the new modular player structure for the Poker RL agents.

## Overview

The player system has been refactored to separate different LLM providers into their own files while maintaining backward compatibility. The new structure provides:

- **Modularity**: Each LLM provider has its own implementation
- **Factory Pattern**: Easy creation of players with validation
- **Backward Compatibility**: Existing code continues to work
- **Model Flexibility**: Easy specification of different models

## Structure

```
poker_llm_area/
├── players/
│   ├── __init__.py              # Package exports
│   ├── base_player.py           # Abstract base class with common functionality
│   ├── openai_player.py         # OpenAI-specific implementation
│   ├── gemini_player.py         # Gemini-specific implementation
│   ├── anthropic_player.py      # Anthropic-specific implementation
│   └── player_factory.py        # Factory for creating players
├── player.py                    # Main entry point (backward compatible)
└── example_usage.py             # Usage examples
```

## Usage

### Method 1: Using the Factory (Recommended)

```python
from players.player_factory import PlayerFactory

# Create players with default models
player1 = PlayerFactory.create_player("Alice", "openai")  # Uses gpt-4
player2 = PlayerFactory.create_player("Bob", "gemini")    # Uses gemini-pro
player3 = PlayerFactory.create_player("Charlie", "anthropic")  # Uses claude-3-sonnet

# Specify exact models
player4 = PlayerFactory.create_player("David", "openai", "gpt-3.5-turbo")
player5 = PlayerFactory.create_player("Eve", "gemini", "gemini-pro-vision")
```

### Method 2: Using Convenience Methods

```python
# Convenience methods for each provider
openai_player = PlayerFactory.create_openai_player("Frank", "gpt-4")
gemini_player = PlayerFactory.create_gemini_player("Grace", "gemini-pro")
anthropic_player = PlayerFactory.create_anthropic_player("Henry", "claude-3-haiku")
```

### Method 3: Backward Compatibility

```python
from player import Player

# Old way still works
legacy_player = Player("Ivy", "openai", "gpt-4")
```

## Supported Models

### OpenAI
- `gpt-4` (default)
- `gpt-3.5-turbo`
- `gpt-4-turbo`

### Gemini
- `gemini-pro` (default)
- `gemini-pro-vision`

### Anthropic
- `claude-3-sonnet` (default)
- `claude-3-haiku`
- `claude-3-opus`

## Factory Benefits

1. **Validation**: Automatically validates provider/model combinations
2. **Defaults**: Uses sensible defaults when no model is specified
3. **Error Handling**: Clear error messages for invalid configurations
4. **Extensibility**: Easy to add new providers or models
5. **Centralized Logic**: All player creation logic in one place

## Adding New Models

To add new models, update the `SUPPORTED_MODELS` dictionary in `players/player_factory.py`:

```python
SUPPORTED_MODELS = {
    "openai": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo", "new-model"],
    "gemini": ["gemini-pro", "gemini-pro-vision", "new-gemini-model"],
    "anthropic": ["claude-3-sonnet", "claude-3-haiku", "claude-3-opus", "new-claude-model"]
}
```

## Adding New Providers

To add a new provider:

1. Create a new file `players/new_provider_player.py`
2. Inherit from `BasePlayer` and implement the `_chat` method
3. Add the provider to the factory's `SUPPORTED_MODELS`
4. Update the factory's `create_player` method

## Environment Variables

Make sure to set the appropriate API keys in your `.env` file:

```
OPENAI_KEY=your_openai_api_key
GEMINI_KEY=your_gemini_api_key
ANTHROPIC_KEY=your_anthropic_api_key
```

## Example

Run the example script to see the new system in action:

```bash
python example_usage.py
```

This will demonstrate all the different ways to create players and show the supported models for each provider. 