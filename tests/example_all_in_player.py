"""Example usage of the All-In player in a poker game."""

import asyncio
from player import Player
from players.player_factory import PlayerFactory


async def example_all_in_game():
    """Example of using All-In player in a game scenario."""
    
    print("=== All-In Player Example ===\n")
    
    # Create players using different methods
    print("Creating players...")
    
    # Method 1: Direct creation
    all_in_player = Player("AllInBot", "all-in", "all-in-bot", initial_stack=400)
    print(f"✓ Created All-In player: {all_in_player.name} with stack {all_in_player.stack}")
    
    # Method 2: Using factory
    factory_all_in = PlayerFactory.create_all_in_player("FactoryAllIn", initial_stack=400)
    print(f"✓ Created factory All-In player: {factory_all_in.name} with stack {factory_all_in.stack}")
    
    # Method 3: Using factory with generic method
    generic_all_in = PlayerFactory.create_player("GenericAllIn", "all-in", initial_stack=400)
    print(f"✓ Created generic All-In player: {generic_all_in.name} with stack {generic_all_in.stack}")
    
    print("\n=== Testing All-In Behavior ===\n")
    
    # Test different game scenarios
    test_scenarios = [
        {
            "name": "Pre-flop with raise opportunity",
            "game_state": {
                "Your stack": 400,
                "min_raise_to": 100,
                "to_call": 0,
                "Current Street": "Pre flop",
                "Position": "Button",
                "board": [],
                "Hole Cards": ["AS", "KH"],
                "Opponent stack": 400,
                "Pot size": 150,
                "history": []
            },
            "legal_actions": ["fold", "call", "raise_to: 100 to 400"]
        },
        {
            "name": "Facing a bet (call only)",
            "game_state": {
                "Your stack": 400,
                "min_raise_to": "Cannot Raise",
                "to_call": 200,
                "Current Street": "Flop",
                "Position": "Big Blind",
                "board": ["AS", "KH", "QD"],
                "Hole Cards": ["JC", "TC"],
                "Opponent stack": 200,
                "Pot size": 600,
                "history": ["CompletionBettingOrRaisingTo(player=0, amount=200)"]
            },
            "legal_actions": ["fold", "call"]
        },
        {
            "name": "Check opportunity",
            "game_state": {
                "Your stack": 400,
                "min_raise_to": "Cannot Raise",
                "to_call": 0,
                "Current Street": "Turn",
                "Position": "Button",
                "board": ["AS", "KH", "QD", "JC"],
                "Hole Cards": ["TC", "9C"],
                "Opponent stack": 400,
                "Pot size": 800,
                "history": []
            },
            "legal_actions": ["fold", "check"]
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"Scenario {i}: {scenario['name']}")
        print(f"  Game State: Stack={scenario['game_state']['Your stack']}, "
              f"Min Raise={scenario['game_state']['min_raise_to']}, "
              f"To Call={scenario['game_state']['to_call']}")
        print(f"  Legal Actions: {scenario['legal_actions']}")
        
        # Get decision from All-In player
        decision = await all_in_player.make_decision(scenario['game_state'], scenario['legal_actions'])
        print(f"  All-In Decision: {decision}")
        print()
    
    print("=== Testing Player Factory ===\n")
    
    # Test factory methods
    print("Supported providers:", PlayerFactory.get_supported_providers())
    print("All-In models:", PlayerFactory.get_supported_models("all-in"))
    
    # Test validation
    try:
        PlayerFactory.create_player("Valid", "all-in")
        print("✓ Valid all-in player creation successful")
    except Exception as e:
        print(f"✗ Valid creation failed: {e}")
    
    try:
        PlayerFactory.create_player("Invalid", "all-in", "invalid-model")
        print("✗ Invalid model creation should have failed")
    except ValueError:
        print("✓ Invalid model creation properly rejected")
    
    print("\n=== All-In Player Features ===\n")
    
    # Test that All-In player has all the features of a regular player
    print("Testing player features...")
    
    # Test stack updates
    all_in_player.update_stack(300)
    print(f"✓ Stack updated: {all_in_player.stack}")
    
    # Test memory updates
    all_in_player.player_index = 0  # Set player index for memory updates
    hand_data = {
        "hand_id": 1,
        "starting_stacks": [400, 400],
        "actions": [{"player": 0, "action": "raise_to: 400", "commentary": "All-in!"}],
        "result": {"final_stacks": [300, 500], "profit_p0": -100, "profit_p1": 100}
    }
    all_in_player.update_memory(hand_data)
    print(f"✓ Memory updated: {len(all_in_player.hand_history)} hands recorded")
    
    # Test notes
    all_in_player.notes = "Always go all-in, no matter what!"
    print(f"✓ Notes set: {all_in_player.notes}")
    
    # Test performance metrics
    metrics = all_in_player.get_performance_metrics()
    print(f"✓ Performance metrics available: {type(metrics)}")
    
    print("\n=== Example Complete ===")
    print("The All-In player is ready to use in your poker games!")


if __name__ == "__main__":
    asyncio.run(example_all_in_game()) 