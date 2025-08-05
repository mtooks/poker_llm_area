"""All-In player implementation for Poker RL agents."""

from typing import Sequence, Dict, Any, List
from .base_player import BasePlayer


class AllInPlayer(BasePlayer):
    """All-In player that always goes all-in on every hand."""

    def __init__(
        self,
        name: str,
        model: str = "all-in-bot",
        initial_stack: int = 400,
        system_prompt: str = None,
    ):
        super().__init__(name, model, initial_stack, system_prompt)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """
        Override the chat method to always return all-in action.
        This method is called by the base class but we don't actually need LLM communication.
        """
        # Extract the game state from the last user message
        game_state = self._extract_game_state(messages)
        
        # Always go all-in
        return self._generate_all_in_response(game_state)

    def _extract_game_state(self, messages: Sequence[Dict[str, str]]) -> Dict[str, Any]:
        """Extract game state from the messages."""
        import json
        
        # Find the last user message which contains the game state
        for msg in reversed(messages):
            if msg["role"] == "user":
                try:
                    # Parse the JSON content
                    content = json.loads(msg["content"])
                    return content.get("state", {})
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Fallback to empty dict if we can't parse
        return {}

    def _generate_all_in_response(self, game_state: Dict[str, Any]) -> str:
        """
        Generate an all-in response based on the game state.
        
        Returns:
            String in format: "raise_to: <amount>@<reason>"
        """
        # Get the player's current stack
        player_stack = game_state.get("Your stack", self.stack)
        
        # Get the minimum raise amount if available
        min_raise_info = game_state.get("min_raise_to", "Cannot Raise")
        
        # Determine the raise amount (all-in)
        if isinstance(min_raise_info, str) and "Cannot Raise" in min_raise_info:
            # If we can't raise, we should call or fold
            to_call = game_state.get("to_call", 0)
            if to_call == 0:
                return "check@Going all-in by checking (no bet to call)"
            else:
                return f"call@Going all-in by calling {to_call}"
        else:
            # We can raise, so go all-in
            return f"raise_to: {player_stack}@Going all-in with {player_stack} chips!"

    async def make_decision(self, game_state: Dict[str, Any], legal_actions: List[str]) -> str:
        """
        Override make_decision to always go all-in.
        This bypasses the LLM communication entirely.
        """
        # Update the game state with notes
        game_state["notes"] = self.notes
        game_state["can_update_notes"] = True
        
        # Generate all-in response directly
        response = self._generate_all_in_response(game_state)
        
        # Update conversation history for consistency
        prompt_json = {
            "state": game_state,
            "legal": legal_actions,
            "instructions": "You can update your notes by including a line starting with 'NOTES:' after your action and commentary.",
        }
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": str(prompt_json)})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response 