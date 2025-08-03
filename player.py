"""Player module for Poker RL agents - Main entry point."""

from players.player_factory import PlayerFactory

# For backward compatibility, create a Player class that uses the factory
class Player:
    """Player class that encapsulates LLM interaction and player state.
    
    This is a backward-compatible wrapper around the new factory-based system.
    For new code, consider using PlayerFactory directly.
    """

    def __init__(
        self,
        name: str,
        provider: str,  # "openai" | "gemini" | "anthropic"
        model: str = None,
        initial_stack: int = 400,
        system_prompt: str = None,
    ):
        # Create the actual player using the factory
        self._player = PlayerFactory.create_player(
            name=name,
            provider=provider,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt
        )
        
        # Expose all attributes and methods from the underlying player
        self.name = self._player.name
        self.provider = provider
        self.model = self._player.model
        self.stack = self._player.stack
        self.initial_stack = self._player.initial_stack
        self.hand_history = self._player.hand_history
        self.conversation_history = self._player.conversation_history
        self.system_prompt = self._player.system_prompt
        self.decision_times = self._player.decision_times
        self.position_stats = self._player.position_stats
        self.bluff_attempts = self._player.bluff_attempts
        self.bluff_successes = self._player.bluff_successes
        self.value_bets = self._player.value_bets
        self.value_bet_successes = self._player.value_bet_successes
        self.player_index = self._player.player_index
        self.notes = self._player.notes

    # Delegate all methods to the underlying player
    async def ask(self, messages):
        return await self._player.ask(messages)

    async def make_decision(self, game_state, legal_actions):
        return await self._player.make_decision(game_state, legal_actions)

    def update_notes(self, new_notes):
        return self._player.update_notes(new_notes)

    def update_memory(self, hand_result):
        return self._player.update_memory(hand_result)

    def get_performance_metrics(self):
        return self._player.get_performance_metrics()

    def reset_conversation_for_new_hand(self):
        return self._player.reset_conversation_for_new_hand()

    def update_stack(self, new_stack):
        return self._player.update_stack(new_stack)

# Export the factory for new code
__all__ = ["Player", "PlayerFactory"]
