# Simplified Poker Game - main.py

This is a simplified version of the poker game that uses the new player factory system. It has the same game mechanics as `test.py` but is much cleaner and easier to modify.

## Features

- **Player Factory Integration**: Uses the new modular player system
- **Easy Configuration**: Simple config file to change players and settings
- **Multi-Player Support**: Supports 2+ players (heads-up and multi-table)
- **Same Game Logic**: Identical poker mechanics to the original
- **Clean Code**: Much simpler and more maintainable

## Quick Start

1. **Set up your API keys** in a `.env` file:
   ```
   OPENAI_KEY=your_openai_api_key
   GEMINI_KEY=your_gemini_api_key
   ANTHROPIC_KEY=your_anthropic_api_key
   ```

2. **Configure players** in `game_config.py`:
   ```python
   PLAYER_CONFIGS = [
       {"name": "GPT-4", "provider": "openai", "model": "gpt-4"},
       {"name": "Claude", "provider": "anthropic", "model": "claude-3-sonnet"},
   ]
   ```

3. **Run the game**:
   ```bash
   python main.py
   ```

## Configuration Options

### Game Settings (`game_config.py`)

```python
GAME_CONFIG = {
    "hands": 10,           # Number of hands to play
    "blinds": (50, 100),   # Small blind, big blind
    "initial_stack": 400,  # Starting stack for each player
    "rng_seed": 42,        # Random seed for reproducibility
}
```

### Player Configurations

**Option 1: Specify exact models**
```python
PLAYER_CONFIGS = [
    {"name": "GPT-4", "provider": "openai", "model": "gpt-4"},
    {"name": "Claude", "provider": "anthropic", "model": "claude-3-haiku"},
]
```

**Option 2: Use default models (factory picks first available)**
```python
PLAYER_CONFIGS = [
    {"name": "OpenAI Player", "provider": "openai"},  # Uses gpt-4
    {"name": "Gemini Player", "provider": "gemini"},  # Uses gemini-pro
    {"name": "Claude Player", "provider": "anthropic"},  # Uses claude-3-sonnet
]
```

**Option 3: Multi-player game**
```python
PLAYER_CONFIGS = [
    {"name": "GPT-4", "provider": "openai", "model": "gpt-4o-mini"},
    {"name": "Claude", "provider": "anthropic", "model": "claude-3-5-haiku-latest"},
    {"name": "Claude2", "provider": "anthropic", "model": "claude-3-5-haiku-latest"},
    {"name": "Gemini", "provider": "gemini", "model": "gemini-pro"},
]
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

## Key Differences from test.py

1. **Simplified Structure**: Removed complex VPIP/PFR calculations
2. **Factory Integration**: Uses the new player factory instead of direct Player instantiation
3. **Configuration File**: Easy to modify settings without touching main code
4. **Cleaner Output**: Simplified performance summary
5. **Better Error Handling**: More robust error handling for illegal moves

## Example Output

### Heads-up Game (2 players)
```
=== Poker Game with Player Factory ===
Players: ['GPT-4', 'Claude']
Hands to play: 10

=== Hand 1 ===
Button: GPT-4 (SB), BB: Claude
P0, aka GPT-4 hole cards: ['A♠️', 'K♥️']
P1, aka Claude hole cards: ['Q♦️', 'J♣️']
GPT-4: I have AK suited, strong starting hand. Raising for value.
Board: ['T♠️', '7♥️', '2♦️']
Claude: I have QJ, missed the flop. Folding to the bet.
Hand 1 result → stacks: GPT-4=450 | Claude=350
```

### Multi-player Game (3+ players)
```
=== Poker Game with Player Factory ===
Players: ['GPT-4', 'Claude', 'Claude2']
Hands to play: 10

=== Hand 1 ===
Button: GPT-4, SB: Claude, BB: Claude2
P0, aka GPT-4 hole cards: ['A♠️', 'K♥️']
P1, aka Claude hole cards: ['Q♦️', 'J♣️']
P2, aka Claude2 hole cards: ['T♠️', '9♣️']
GPT-4: I have AK suited, strong starting hand. Raising for value.
Claude: I have QJ, calling the raise.
Claude2: I have T9, folding to the aggression.
Board: ['T♠️', '7♥️', '2♦️']
Hand 1 result → stacks: GPT-4=450 | Claude=350 | Claude2=200
```

=== Performance Summary ===
Illegal moves: 0
GPT-4: 6/10 wins (60.0%), Profit: 50
Claude: 3/10 wins (30.0%), Profit: -50
Claude2: 1/10 wins (10.0%), Profit: -200
```

## Adding New Players

To add a new player, simply add them to the `PLAYER_CONFIGS` list in `game_config.py`:

```python
PLAYER_CONFIGS = [
    {"name": "GPT-4", "provider": "openai", "model": "gpt-4"},
    {"name": "Claude", "provider": "anthropic", "model": "claude-3-sonnet"},
    {"name": "New Player", "provider": "gemini", "model": "gemini-pro"},  # New player
]
```

The game will automatically handle the new player without any code changes! 