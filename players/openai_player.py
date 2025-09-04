"""OpenAI player implementation for Poker RL agents."""

import os
from pathlib import Path
from typing import Sequence, Dict
from pydantic import BaseModel


# Handle optional imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from .base_player import BasePlayer


class OpenAIPlayer(BasePlayer):
    """OpenAI-specific player implementation."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
        enable_reflection: bool = False,
    ):
        super().__init__(name, model, initial_stack, system_prompt, enable_reflection)
        
        # Initialize OpenAI client
        self._setup_openai_client()

    def _setup_openai_client(self):
        """Setup OpenAI client with API key."""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI provider requires the 'openai' package. Install with 'pip install openai'")
        
        if not DOTENV_AVAILABLE:
            raise ImportError("OpenAI provider requires the 'python-dotenv' package. Install with 'pip install python-dotenv'")
        
        # Load environment variables from .env file if it exists
        env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        openai_key = os.getenv("OPENAI_KEY", "")
        if not openai_key:
            raise ValueError("OPENAI_KEY environment variable is not set")
        
        self.client = openai.AsyncOpenAI(api_key=openai_key)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to OpenAI API and get response with structured output when possible."""
        # Prefer structured output to reduce parsing errors
        class PokerAction(BaseModel):
            action: str
            amount: int
            reason: str
            notes: str

        try:
            rsp = await self.client.responses.parse(
                model = self.model,
                input = messages,
                text_format = PokerAction
            )

            content = rsp.output_parsed

        except Exception:
            print('Openai Structured output failed!')
            # Fallback: no structured output
            rsp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=400,
            )
            return rsp.choices[0].message.content.strip()

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
                result =  notes + "@"
            elif action in ("show", "muck"):
                result = action + "@"
                if action == 'show':
                    print("HOOOOOOOLLYYYYYY HE SHOWEEEEDDDD THE BLUFFFFF")
            else:
                print('Error in structured output. Debug openai player')
            if notes:
                result += f"\nNOTES: {notes}"
            return result
        except Exception:
            # If JSON parsing fails, return raw content
            return content.strip() if isinstance(content, str) else str(content)