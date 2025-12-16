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
        use_structured_output: bool = True,  # Default to True for Gemini
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=use_structured_output,
        )
        
        # Initialize Gemini client
        self._setup_gemini_client()

    def _setup_gemini_client(self):
        """Setup Gemini client with API key."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini provider requires the 'google-genai' package. Install with 'pip install google-genai'")

        gemini_key = get_env_value("GEMINI_KEY", required=True)
        self.client = genai.Client(api_key = gemini_key)

    async def _chat(self, messages: Sequence[Dict[str, str]], structured_output: bool = False) -> str:
        """Send messages to Gemini API and get response with optional structured output."""
        if structured_output:
            return await self._chat_structured(messages)
        else:
            return await self._chat_vanilla(messages)
    
    async def _chat_structured(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Gemini API with structured output."""
        from typing import Literal, Optional
        from pydantic import Field
        
        class PokerAction(BaseModel):
            action: Literal["fold", "check", "call", "raise_to", "show", "muck"] = Field(
                description="The poker action to take. Must be one of: fold, check, call, raise_to, show, muck"
            )
            amount: Optional[int] = Field(
                default=0,
                description="Amount to raise to (only required for raise_to action, ignored otherwise)"
            )
            reason: str = Field(description="Your reasoning for this action")
            notes: str = Field(default="", description="Optional notes to remember for future hands")

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

            # Action is constrained by Literal, so we can trust it's valid
            if action in ("fold", "check", "call"):
                result = f"{action}@{reason}" if reason else action
            elif action == "raise_to":
                if not isinstance(amount, int) or amount <= 0:
                    raise ValueError(f"raise_to requires a positive integer amount, got: {amount}")
                result = f"raise_to:{amount}@{reason}" if reason else f"raise_to:{amount}"
            elif action in ("show", "muck"):
                result = action + "@"
            else:
                # This should never happen due to Literal constraint
                print(f'Unexpected action received (should be impossible): action="{action}"')
                result = f"{action}@{reason}" if reason else action
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
