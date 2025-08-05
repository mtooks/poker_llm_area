# Zero Stack Fix for All-In Players

## Problem Description

When players go all-in and lose, their stack becomes 0 chips. However, the game validation logic incorrectly treated 0 as an "invalid" stack size, causing the error:

```
ValueError: Invalid stack size: 0. Must be non-negative.
```

This prevented the game from continuing after an all-in hand, even though having 0 chips is a perfectly valid state in poker (it means the player is "busted" or eliminated).

## Root Cause

The issue was in the `_make_state()` method in both `main.py` and `test.py`:

```python
# BEFORE (incorrect)
for i in stacks:
    if i <= 0:  # This incorrectly rejects 0
        raise ValueError(f"Invalid stack size: {i}. Must be non-negative.")
```

The validation logic used `<= 0` instead of `< 0`, which incorrectly rejected valid zero-stack scenarios.

## Solution

### 1. Fixed Stack Validation

Changed the validation logic to only reject negative stacks:

```python
# AFTER (correct)
for i in stacks:
    if i < 0:  # Only reject negative stacks
        raise ValueError(f"Invalid stack size: {i}. Must be non-negative.")
```

### 2. Added Busted Player Detection

Added logic to detect and handle players with 0 chips:

```python
# Check if any player is busted (has 0 chips)
busted_players = [i for i, stack in enumerate(stacks) if stack == 0]
if busted_players:
    busted_names = [self.get_players_in_position_order()[i].name for i in busted_players]
    print(f"Warning: Players with 0 chips detected: {busted_names}")
    # For now, we'll continue but this could be enhanced to handle elimination
```

### 3. Added Game Termination Logic

Added logic to end the game early when players are eliminated:

```python
# Check if any player is eliminated before starting the hand
active_players = [p for p in self.players if p.stack > 0]
if len(active_players) < 2:
    eliminated_players = [p.name for p in self.players if p.stack == 0]
    print(f"\nGame ended early: Players eliminated: {eliminated_players}")
    print(f"Remaining hands skipped: {self.hands - h}")
    break
```

## Files Modified

1. **`main.py`** - Fixed validation in `_make_state()` and added elimination logic in `run()`
2. **`test.py`** - Fixed validation in `_make_state()` and added elimination logic in `run()`

## Testing

Created test files to verify the fix:

1. **`test_zero_stack_fix.py`** - Tests the validation logic with zero stacks
2. **`example_all_in_game.py`** - Demonstrates All-In player behavior with elimination

## Example Scenario

### Before Fix
```
Hand 1: All-In player goes all-in and loses
Player stack: 0 chips
Error: ValueError: Invalid stack size: 0. Must be non-negative.
Game crashes
```

### After Fix
```
Hand 1: All-In player goes all-in and loses
Player stack: 0 chips
Warning: Players with 0 chips detected: ['AllInBot']
Game continues or ends appropriately
```

## Benefits

1. **All-In Players Work**: All-In players can now go all-in without causing crashes
2. **Proper Game Flow**: Games can continue or end appropriately when players are eliminated
3. **Realistic Poker**: Zero-stack scenarios are now handled correctly
4. **Better Error Handling**: Clear warnings when players are busted

## Usage

The fix is automatically applied when using the All-In player:

```python
# This now works without errors
all_in_player = Player("AllInBot", "all-in", "all-in-bot", initial_stack=400)
regular_player = Player("RegularBot", "anthropic", "claude-3-5-haiku-latest", initial_stack=400)

# Game will handle all-in scenarios correctly
orch = Orchestrator(hands=10)
orch.players = [all_in_player, regular_player]
asyncio.run(orch.run())
```

## Future Enhancements

The current fix provides basic handling of zero-stack scenarios. Future enhancements could include:

1. **Tournament Mode**: Proper elimination and re-buy logic
2. **Multi-Table Support**: Handle players eliminated from one table
3. **Re-buy Options**: Allow players to re-buy when busted
4. **Side Pots**: Handle complex all-in scenarios with multiple players

## Verification

Run the test files to verify the fix:

```bash
python test_zero_stack_fix.py
python example_all_in_game.py
```

Both should run without errors and demonstrate proper handling of zero-stack scenarios. 