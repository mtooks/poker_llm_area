"""Callbox player implementation for Poker RL agents."""

from typing import Sequence, Dict, Any, List
from .base_player import BasePlayer


class CallboxPlayer(BasePlayer):
    """Callbox player that always calls on every hand."""

    def __init__(
        self,
        name: str,
        model: str = "callbox-bot",
        initial_stack: int = 400,
        system_prompt: str = None,
    ):
        super().__init__(name, model, initial_stack, system_prompt)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """
        Override the chat method to always return call action.
        This method is called by the base class but we don't actually need LLM communication.
        """
        # Extract the game state from the last user message
        game_state = self._extract_game_state(messages)
        
        # Always call
        return self._generate_call_response(game_state)

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

    def _generate_call_response(self, game_state: Dict[str, Any]) -> str:
        """
        Generate a call response based on the game state.
        
        Returns:
            String in format: "call@<reason>" or "check@<reason>"
        """
        # Get the amount to call
        to_call = game_state.get("to_call", 0)
        
        if to_call == 0:
            # If there's nothing to call, check instead
            return "check@Always checking when there's no bet to call"
        else:
            # Always call the current bet
            return f"call@Always calling {to_call} chips"

    async def make_decision(self, game_state: Dict[str, Any], legal_actions: List[str]) -> str:
        """
        Override make_decision to always call.
        This bypasses the LLM communication entirely.
        """
        # Update the game state with notes
        game_state["notes"] = self.notes
        game_state["can_update_notes"] = True
        
        # Generate call response directly
        response = self._generate_call_response(game_state)
        
        return response 