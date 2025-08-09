"""Grok (xAI) player implementation for Poker RL agents."""

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


class GrokPlayer(BasePlayer):
    """xAI Grok-specific player implementation using OpenAI-compatible API."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
    ):
        super().__init__(name, model, initial_stack, system_prompt)

        # Initialize Grok client (OpenAI-compatible, different base_url)
        self._setup_grok_client()

    def _setup_grok_client(self) -> None:
        """Setup Grok client with API key via OpenAI SDK against xAI endpoint."""
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "Grok provider requires the 'openai' package. Install with 'pip install openai'"
            )

        if not DOTENV_AVAILABLE:
            raise ImportError(
                "Grok provider requires the 'python-dotenv' package. Install with 'pip install python-dotenv'"
            )

        # Load environment variables from .env file if it exists
        env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        xai_key = os.getenv("XAI_API_KEY", "")
        if not xai_key:
            raise ValueError("XAI_API_KEY environment variable is not set")

        # Point OpenAI client at xAI base URL
        self.client = openai.OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")

    async def ask(self, messages: Sequence[Dict[str, str]]) -> str:
        """Route request to appropriate LLM provider with conversation history."""
        # Combine system message, conversation history, and current message

        # if strucutured output, use a different flag

        full_messages = [{"role": "system", "content": self.structured_system_prompt}]
        full_messages.extend(self.conversation_history)
        
        # Only add the last user message if it's not already in conversation history
        if messages and messages[-1]["role"] == "user" and (not self.conversation_history or 
                                                          messages[-1] != self.conversation_history[-1]):
            full_messages.append(messages[-1])
        
        response = await self._chat(full_messages)
        if messages and messages[-1]["role"] == "user" and (not self.conversation_history or 
                                                          messages[-1] != self.conversation_history[-1]):
            self.conversation_history.append(messages[-1])
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        class PokerAction(BaseModel):
            action: str
            amount: int
            reason: str
            notes: str

        messages[1]['content']

        try:
            
            rsp = self.client.beta.chat.completions.parse(
                model = self.model,
                messages = messages,
                response_format = PokerAction
            )

            content = rsp.choices[0].message.parsed

        except Exception:
            print('Grok Structured output failed!')
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
            elif action == "raise_to" and isinstance(amount, int):
                result = f"raise_to:{amount}@{reason}" if reason else f"raise_to:{amount}"
            else:
                print('Error in structured output. Debug openai player')
            if notes:
                result += f"\nNOTES: {notes}"
            return result
        except Exception:
            # If JSON parsing fails, return raw content
            return content.strip() if isinstance(content, str) else str(content)