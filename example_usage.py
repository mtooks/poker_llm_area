"""Example usage of the new player factory system."""

import asyncio
from players.player_factory import PlayerFactory


async def main():
    """Demonstrate different ways to create players."""
    
    print("=== Player Factory Example ===\n")
    
    # Method 1: Using the factory with default models
    print("1. Creating players with default models:")
    player1 = PlayerFactory.create_player("Alice", "openai")  # Uses gpt-4
    player2 = PlayerFactory.create_player("Bob", "gemini")    # Uses gemini-pro
    player3 = PlayerFactory.create_player("Charlie", "anthropic")  # Uses claude-3-sonnet
    
    print(f"   Alice: {player1.name} using {player1.model}")
    print(f"   Bob: {player2.name} using {player2.model}")
    print(f"   Charlie: {player3.name} using {player3.model}\n")
    
    # Method 2: Using convenience methods
    print("2. Using convenience methods:")
    openai_player = PlayerFactory.create_openai_player("David", "gpt-3.5-turbo")
    gemini_player = PlayerFactory.create_gemini_player("Eve", "gemini-pro-vision")
    
    print(f"   David: {openai_player.name} using {openai_player.model}")
    print(f"   Eve: {gemini_player.name} using {gemini_player.model}\n")
    
    # Method 3: Specifying exact models
    print("3. Specifying exact models:")
    custom_player = PlayerFactory.create_player("Frank", "anthropic", "claude-3-haiku")
    print(f"   Frank: {custom_player.name} using {custom_player.model}\n")
    
    # Method 4: Backward compatibility with old Player class
    print("4. Backward compatibility:")
    from player import Player
    legacy_player = Player("Grace", "openai", "gpt-4")
    print(f"   Grace: {legacy_player.name} using {legacy_player.model}\n")
    
    # Show supported models
    print("5. Supported models by provider:")
    for provider in PlayerFactory.get_supported_providers():
        models = PlayerFactory.get_supported_models(provider)
        print(f"   {provider}: {', '.join(models)}")
    
    print("\n=== Example completed ===")


if __name__ == "__main__":
    asyncio.run(main()) 