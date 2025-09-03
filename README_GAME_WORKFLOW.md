# Poker LLM Game Workflow

## Overview

This project implements a poker game simulation where AI language models (LLMs) from different providers compete against each other in Texas Hold'em poker. The system uses a modular architecture with a player factory pattern to easily add new AI providers and models.

## Architecture Overview

### Core Components

1. **Game Orchestrator** (`main.py`): Manages the overall game flow and state
2. **Player Factory** (`players/player_factory.py`): Creates players with different LLM providers
3. **Base Player** (`players/base_player.py`): Abstract base class for all poker players
4. **Action Converter** (`utils/action_converter.py`): Translates between LLM responses and game actions
5. **Game Configuration** (`game_config.py`): Centralized configuration for game settings

## Game Workflow

### 1. Initialization Phase

```python
# Players are created based on configuration
PLAYER_CONFIGS = [
    {"name": "SamAltman", "provider": "openai", "model": "gpt-4o-mini"},
    {"name": "Callbox", "provider": "callbox", "model": "callbox-bot"}
]

# Game settings are loaded
GAME_CONFIG = {
    "hands": 30,              # Number of hands to play
    "blinds": (50, 100),      # Small blind, big blind
    "initial_stack": 10000,   # Starting chips per player
    "see_model_monologue": True  # Show AI reasoning
}
```

### 2. Player Creation

The `PlayerFactory` creates player instances based on the configuration:

```python
# Example of player creation
players = []
for config in PLAYER_CONFIGS:
    player = PlayerFactory.create_player(
        name=config["name"],
        provider=config["provider"],
        model=config["model"],
        initial_stack=GAME_CONFIG["initial_stack"]
    )
    players.append(player)
```

### 3. Hand Setup

For each hand:

1. **Dealer Position Rotation**: Button moves to the next player
2. **Blinds Posting**: Small blind and big blind are posted
3. **Card Dealing**: Hole cards are dealt to each player
4. **Position Assignment**: Players get positions (Button, Small Blind, Big Blind, etc.)

### 4. Betting Rounds

Each hand goes through up to 4 betting rounds:

#### Pre-Flop Round
- Players receive their hole cards
- Action starts from player left of big blind
- Small blind and big blind have already posted

#### Flop Round
- Three community cards are dealt
- Betting starts from player left of dealer

#### Turn Round
- Fourth community card is dealt
- Another round of betting

#### River Round
- Fifth and final community card
- Final betting round

### 5. Player Decision Making Process

For each player's turn:

1. **State Preparation**: Game state is formatted for the player
```json
{
  "Current Street": "Flop",
  "Position": "Button",
  "board": ["Ah", "7d", "2c"],
  "Hole Cards": ["As", "Kh"],
  "Your stack": 8500,
  "Opponent stacks": [9200, 7800],
  "Pot size": 300,
  "to_call": 100,
  "min_raise_to": 200,
  "history": ["Player 1 calls 100", "Player 2 raises to 300"]
}
```

2. **Legal Actions Generation**: Available actions are calculated
```python
legal_actions = [
    "fold",
    "call",
    "raise_to: 300 to 8500"  // min_raise to max_stack
]
```

3. **LLM Query**: Player sends formatted prompt to their LLM
4. **Response Processing**: LLM returns action in format: `action@reasoning`
5. **Action Validation**: Response is validated against legal actions
6. **Action Execution**: Valid action is applied to game state

### 6. Conversation History Management

Each player maintains conversation history that includes:

- **System Prompt**: Poker strategy instructions
- **Hand Summaries**: Results from previous hands
- **Game State History**: Previous decisions and outcomes
- **Player Notes**: Self-maintained observations about opponents

### 7. Hand Resolution

When betting is complete:

1. **Showdown**: Remaining players reveal cards
2. **Winner Determination**: Best poker hand wins
3. **Pot Distribution**: Chips are awarded to winner(s)
4. **Stack Updates**: Player chip counts are updated
5. **Memory Update**: Hand results are stored in player memory

### 8. Performance Tracking

After each hand, the system tracks:

- **Win/Loss Record**: Hands won vs total hands
- **Profit/Loss**: Net chip gain/loss
- **Decision Times**: How long each player takes to decide
- **Illegal Moves**: Invalid actions that were auto-corrected
- **Position Statistics**: Performance by table position

## Supported LLM Providers

### OpenAI
- **Models**: GPT-4o-mini, GPT-4, GPT-3.5-turbo
- **Features**: Most reliable, good poker understanding

### Anthropic (Claude)
- **Models**: Claude-3-7-sonnet-latest, Claude-3-5-haiku-latest
- **Features**: Strong reasoning, good at strategic thinking

### Google Gemini
- **Models**: Gemini-pro, Gemini-pro-vision
- **Features**: Fast responses, good pattern recognition

### xAI (Grok)
- **Models**: Grok-4, Grok-3, Grok-3-mini
- **Features**: Creative strategies, humorous commentary

### Specialized Players
- **All-In Player**: Always goes all-in (for testing)
- **Callbox Player**: Custom poker-focused AI

## Key Features

### 1. Modular Architecture
- Easy to add new LLM providers
- Factory pattern for player creation
- Extensible action processing

### 2. Comprehensive Logging
- Full hand history tracking
- Player decision reasoning
- Performance metrics

### 3. Configurable Game Settings
- Adjustable blinds and stacks
- Variable number of hands
- Tournament vs cash game modes

### 4. Memory and Learning
- Players maintain conversation history
- Self-updating notes about opponents
- Performance analysis across hands

## Running the Game

```bash
# Install dependencies
pip install -r requirements.txt

# Configure players in game_config.py
# Run the game
python main.py
```

## Output and Analysis

The game provides:

1. **Real-time Commentary**: Player reasoning and actions
2. **Hand-by-Hand Results**: Detailed breakdown of each hand
3. **Final Performance Summary**: Win rates, profits, and statistics
4. **Conversation Logs**: Full decision-making history for analysis

## Future Enhancements

- Multi-table tournaments
- More sophisticated position handling
- Advanced statistics tracking
- Player elimination and re-buying
- Side pot handling
- Custom betting structures
