"""Anthropic player implementation for Poker RL agents."""

from typing import Sequence, Dict

# Handle optional imports
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from utils.env_loader import get_env_value
from .base_player import BasePlayer


class AnthropicPlayer(BasePlayer):
    """Anthropic-specific player implementation."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
        enable_reflection: bool = False,
    ):
        super().__init__(name, model, initial_stack, system_prompt, enable_reflection)
        
        # Initialize Anthropic client
        self._setup_anthropic_client()

    def _setup_anthropic_client(self):
        """Setup Anthropic client with API key."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic provider requires the 'anthropic' package. Install with 'pip install anthropic'")

        anthropic_key = get_env_value("ANTHROPIC_KEY", required=True)
        self.client = anthropic.AsyncAnthropic(api_key=anthropic_key)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Anthropic API and get response."""
        # Convert from OpenAI-style messages to Anthropic format
        system_content = ""
        conversation = []
        
        # Extract system message
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
                break
        
        # Build the conversation messages
        for msg in messages:
            if msg["role"] == "user":
                conversation.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                conversation.append({"role": "assistant", "content": msg["content"]})
        
        # Create the message request
        response = await self.client.messages.create(
            model=self.model,
            system=system_content,
            messages=conversation,
            max_tokens=1000
        )
        
        return response.content[0].text 
