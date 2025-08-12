"""Simple test runner for All-In player functionality."""

import asyncio
import sys
from player import Player
from players.player_factory import PlayerFactory
from players.all_in_player import AllInPlayer


def test_basic_functionality():
    """Test basic All-In player functionality."""
    print("Testing basic functionality...")
    
    # Test direct creation
    player = AllInPlayer("TestPlayer", initial_stack=1000)
    assert player.name == "TestPlayer"
    assert player.stack == 1000
    print("✓ Direct creation works")
    
    # Test factory creation
    factory_player = PlayerFactory.create_all_in_player("FactoryPlayer", initial_stack=500)
    assert isinstance(factory_player, AllInPlayer)
    assert factory_player.name == "FactoryPlayer"
    print("✓ Factory creation works")
    
    # Test Player wrapper
    wrapper_player = Player("WrapperPlayer", "all-in", "all-in-bot", initial_stack=750)
    assert wrapper_player.name == "WrapperPlayer"
    assert wrapper_player.stack == 750
    print("✓ Player wrapper works")


def test_response_generation():
    """Test response generation for different scenarios."""
    print("\nTesting response generation...")
    
    player = AllInPlayer("TestPlayer", initial_stack=1000)
    
    # Test raise scenario
    game_state = {"Your stack": 1000, "min_raise_to": 200, "to_call": 0}
    response = player._generate_all_in_response(game_state)
    assert "raise_to: 1000" in response
    assert "Going all-in" in response
    print("✓ Raise response correct")
    
    # Test call scenario
    game_state = {"Your stack": 1000, "min_raise_to": "Cannot Raise", "to_call": 500}
    response = player._generate_all_in_response(game_state)
    assert "call" in response
    assert "500" in response
    print("✓ Call response correct")
    
    # Test check scenario
    game_state = {"Your stack": 1000, "min_raise_to": "Cannot Raise", "to_call": 0}
    response = player._generate_all_in_response(game_state)
    assert "check" in response
    print("✓ Check response correct")


async def test_async_functionality():
    """Test async functionality."""
    print("\nTesting async functionality...")
    
    player = AllInPlayer("TestPlayer", initial_stack=1000)
    
    game_state = {
        "Your stack": 1000,
        "min_raise_to": 200,
        "to_call": 0,
        "Current Street": "Pre flop",
        "Position": "Button",
        "board": [],
        "Hole Cards": ["AS", "KH"],
        "Opponent stack": 1000,
        "Pot size": 150,
        "history": []
    }
    legal_actions = ["fold", "call", "raise_to: 200 to 1000"]
    
    response = await player.make_decision(game_state, legal_actions)
    assert "raise_to: 1000" in response
    assert "Going all-in" in response
    print("✓ Async decision making works")
    
    # Test conversation history
    assert len(player.conversation_history) == 2
    assert player.conversation_history[-1]["role"] == "assistant"
    print("✓ Conversation history updated")


def test_factory_integration():
    """Test factory integration."""
    print("\nTesting factory integration...")
    
    # Test supported providers
    providers = PlayerFactory.get_supported_providers()
    assert "all-in" in providers
    print("✓ All-in provider registered")
    
    # Test supported models
    models = PlayerFactory.get_supported_models("all-in")
    assert "all-in-bot" in models
    print("✓ All-in-bot model registered")
    
    # Test validation
    try:
        PlayerFactory.create_player("Valid", "all-in")
        print("✓ Valid creation works")
    except Exception as e:
        print(f"✗ Valid creation failed: {e}")
        return False
    
    try:
        PlayerFactory.create_player("Invalid", "all-in", "invalid-model")
        print("✗ Invalid model should have failed")
        return False
    except ValueError:
        print("✓ Invalid model properly rejected")
    
    return True


def test_player_features():
    """Test that All-In player has all expected features."""
    print("\nTesting player features...")
    
    player = AllInPlayer("TestPlayer", initial_stack=1000)
    
    # Test stack updates
    player.update_stack(500)
    assert player.stack == 500
    print("✓ Stack updates work")
    
    # Test memory updates
    player.player_index = 0  # Set player index for memory updates
    hand_data = {
        "hand_id": 1,
        "starting_stacks": [1000, 1000],
        "actions": [{"player": 0, "action": "raise_to: 1000", "commentary": "All-in!"}],
        "result": {"final_stacks": [500, 1500], "profit_p0": -500, "profit_p1": 500}
    }
    player.update_memory(hand_data)
    assert len(player.hand_history) == 1
    print("✓ Memory updates work")
    
    # Test notes
    player.notes = "Always go all-in!"
    assert player.notes == "Always go all-in!"
    print("✓ Notes work")
    
    # Test performance metrics
    metrics = player.get_performance_metrics()
    assert isinstance(metrics, dict)
    print("✓ Performance metrics work")


async def main():
    """Run all tests."""
    print("=== All-In Player Test Suite ===\n")
    
    try:
        test_basic_functionality()
        test_response_generation()
        await test_async_functionality()
        
        if test_factory_integration():
            test_player_features()
        
        print("\n=== All Tests Passed! ===")
        print("The All-In player is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n=== Test Failed ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 