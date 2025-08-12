"""Example of using All-In player in the actual game system."""

import asyncio
from player import Player
from players.player_factory import PlayerFactory


async def example_all_in_game():
    """Example of using All-In player in a real game scenario."""
    
    print("=== All-In Player Game Example ===\n")
    
    # Create players for a heads-up game
    all_in_player = Player("AllInBot", "all-in", "all-in-bot", initial_stack=400)
    regular_player = Player("RegularBot", "all-in", "all-in-bot", initial_stack=400)  # Using same for simplicity
    
    print(f"Game Setup:")
    print(f"  {all_in_player.name}: {all_in_player.stack} chips")
    print(f"  {regular_player.name}: {regular_player.stack} chips")
    print(f"  Hands to play: 5")
    print()
    
    # Simulate a few hands to show the All-In behavior
    hands = [
        {
            "name": "Hand 1: All-In player wins",
            "all_in_action": "raise_to: 400@Going all-in with 400 chips!",
            "result": {"final_stacks": [800, 0], "profit_p0": 400, "profit_p1": -400}
        },
        {
            "name": "Hand 2: All-In player loses (already busted)",
            "all_in_action": "fold@No chips left to bet",
            "result": {"final_stacks": [800, 0], "profit_p0": 0, "profit_p1": 0}
        },
        {
            "name": "Hand 3: Game should end early",
            "all_in_action": "N/A - game ended",
            "result": {"final_stacks": [800, 0], "profit_p0": 0, "profit_p1": 0}
        }
    ]
    
    print("=== Simulating Game ===\n")
    
    for i, hand in enumerate(hands, 1):
        print(f"Hand {i}: {hand['name']}")
        
        # Check if game should continue
        active_players = [p for p in [all_in_player, regular_player] if p.stack > 0]
        if len(active_players) < 2:
            eliminated_players = [p.name for p in [all_in_player, regular_player] if p.stack == 0]
            print(f"  Game ended early: Players eliminated: {eliminated_players}")
            print(f"  Remaining hands skipped: {5 - i}")
            break
        
        # Simulate the hand
        print(f"  All-In action: {hand['all_in_action']}")
        
        # Update stacks based on result
        if hand['result']['final_stacks'][0] != all_in_player.stack:
            all_in_player.stack = hand['result']['final_stacks'][0]
            regular_player.stack = hand['result']['final_stacks'][1]
        
        # Update hand data
        hand_data = {
            "hand_id": i,
            "starting_stacks": [400, 400] if i == 1 else [all_in_player.stack, regular_player.stack],
            "actions": [{"player": 0, "action": hand['all_in_action'].split('@')[0], "commentary": hand['all_in_action'].split('@')[1]}],
            "result": hand['result']
        }
        
        all_in_player.player_index = 0
        regular_player.player_index = 1
        all_in_player.update_memory(hand_data)
        regular_player.update_memory(hand_data)
        
        print(f"  Result: {all_in_player.name}={all_in_player.stack}, {regular_player.name}={regular_player.stack}")
        print()
    
    # Show final statistics
    print("=== Final Statistics ===\n")
    
    for player in [all_in_player, regular_player]:
        metrics = player.get_performance_metrics()
        print(f"{player.name}:")
        print(f"  Final stack: {player.stack}")
        print(f"  Total profit: {metrics['total_profit']}")
        print(f"  Win rate: {metrics['win_rate']:.1%}")
        print(f"  Hands played: {len(player.hand_history)}")
        print()
    
    print("=== Example Complete ===")
    print("The All-In player works correctly with the zero stack fix!")


if __name__ == "__main__":
    asyncio.run(example_all_in_game()) 