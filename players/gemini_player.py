"""Gemini player implementation for Poker RL agents."""

import os
from pathlib import Path
from typing import Sequence, Dict
from pydantic import BaseModel

# Handle optional imports
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

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
        use_structured_output: bool = True,  # Default to True for Gemini
    ):
        super().__init__(name, model, initial_stack, system_prompt, enable_reflection, use_structured_output)
        
        # Initialize Gemini client
        self._setup_gemini_client()

    def _setup_gemini_client(self):
        """Setup Gemini client with API key."""
                
        # Load environment variables from .env file if it exists
        env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        gemini_key = os.getenv("GEMINI_KEY", "")
        if not gemini_key:
            raise ValueError("GEMINI_KEY environment variable is not set")
        
        self.client = genai.Client(api_key = gemini_key)

    async def _chat(self, messages: Sequence[Dict[str, str]], structured_output: bool = False) -> str:
        """Send messages to Gemini API and get response with optional structured output."""
        if structured_output:
            return await self._chat_structured(messages)
        else:
            return await self._chat_vanilla(messages)
    
    async def _chat_structured(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Gemini API with structured output."""
        class PokerAction(BaseModel):
            action: str
            amount: int
            reason: str
            notes: str

        # Build the full conversation history for context
        full_history = ""
        for msg in messages:
            if msg["role"] == "system":
                full_history += f"<system>\n{msg['content']}\n</system>\n"
            elif msg["role"] == "user":
                full_history += f"<user>\n{msg['content']}\n</user>\n"
            elif msg["role"] == "assistant":
                full_history += f"<assistant>\n{msg['content']}\n</assistant>\n"
        try:
            rsp = self.client.models.generate_content(
                model=self.model, 
                contents=full_history,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": PokerAction
                }
            )
            content = rsp.parsed
            
        except Exception:
            print('Gemini Structured output failed! Falling back to vanilla.')
            return await self._chat_vanilla(messages)

        # Try to convert structured JSON into required string format
        try:
            action = content.action
            amount = content.amount
            reason = content.reason
            notes = content.notes

            if action in ("fold", "check", "call"):
                result = f"{action}@{reason}" if reason else action
            elif (action == "raise_to" or "raise_to" in action) and isinstance(amount, int):
                result = f"raise_to:{amount}@{reason}" if reason else f"raise_to:{amount}"
            elif action == "reflection":
                result = notes + "@"
            elif action in ("show", "muck"):
                result = action + "@" + notes
            else:
                print('Error in structured output. Debug gemini player')
            if notes:
                result += f"\nNOTES: {notes}"
            return result
        except Exception:
            # If JSON parsing fails, return raw content
            return content.strip() if isinstance(content, str) else str(content)
    
    async def _chat_vanilla(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Gemini API with vanilla string output."""
        # Build the full conversation history for context
        full_history = ""
        for msg in messages:
            if msg["role"] == "system":
                full_history += f"<system>\n{msg['content']}\n</system>\n"
            elif msg["role"] == "user":
                full_history += f"<user>\n{msg['content']}\n</user>\n"
            elif msg["role"] == "assistant":
                full_history += f"<assistant>\n{msg['content']}\n</assistant>\n"
        
        rsp = self.client.models.generate_content(
            model=self.model, 
            contents=full_history
        )
        
        return rsp.text.strip()

if __name__ == "__main__":
    player = GeminiPlayer(name="Gemini", model="gemini-2.0-flash-001")
    print(player._chat([{"role": "user", "content": "Hello, how are you?"}]))