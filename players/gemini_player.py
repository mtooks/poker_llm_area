"""Gemini player implementation for Poker RL agents."""

from typing import Sequence, Dict
from pydantic import BaseModel

# Handle optional imports
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from utils.env_loader import get_env_value
from .base_player import BasePlayer


class GeminiPlayer(BasePlayer):
    """Gemini-specific player implementation."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
        enable_reflection: bool = False,
    ):
        super().__init__(name, model, initial_stack, system_prompt, enable_reflection)
        
        # Initialize Gemini client
        self._setup_gemini_client()

    def _setup_gemini_client(self):
        """Setup Gemini client with API key."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini provider requires the 'google-genai' package. Install with 'pip install google-genai'")

        gemini_key = get_env_value("GEMINI_KEY", required=True)
        self.client = genai.Client(api_key = gemini_key)

    def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send the prompt to Gemini via persistent client."""
        # Build the full conversation history for context
        full_history = ""
        for msg in messages:
            if msg["role"] == "system":
                full_history += f"<system>\n{msg['content']}\n</system>\n"
            elif msg["role"] == "user":
                full_history += f"<user>\n{msg['content']}\n</user>\n"
            elif msg["role"] == "assistant":
                full_history += f"<assistant>\n{msg['content']}\n</assistant>\n"
        
        class PokerAction(BaseModel):
                    action: str
                    amount: int
                    reason: str
                    notes: str

        rsp = self.client.models.generate_content(model = self.model, contents = full_history,config = {
            "response_mime_type": "application/json",
            "response_schema": PokerAction
        })
        content = rsp.parsed
        action = content.action
        amount = content.amount
        reason = content.reason
        notes = content.notes

        if action in ("fold", "check", "call"):
            result = f"{action}@{reason}" if reason else action
        elif (action == "raise_to" or "raise_to" in action) and isinstance(amount, int):
            result = f"raise_to:{amount}@{reason}" if reason else f"raise_to:{amount}"
        else:
            print('Error in structured output. Debug gemini player')
        if notes:
            result += f"\nNOTES: {notes}"
        return result

if __name__ == "__main__":
    player = GeminiPlayer(name="Gemini", model="gemini-2.0-flash-001")
    print(player._chat([{"role": "user", "content": "Hello, how are you?"}]))
