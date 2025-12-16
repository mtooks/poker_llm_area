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
        use_structured_output: bool = True,  # Default to True for Anthropic
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=use_structured_output,
        )
        
        # Initialize Anthropic client
        self._setup_anthropic_client()

    def _setup_anthropic_client(self):
        """Setup Anthropic client with API key."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic provider requires the 'anthropic' package. Install with 'pip install anthropic'")

        anthropic_key = get_env_value("ANTHROPIC_KEY", required=True)
        self.client = anthropic.AsyncAnthropic(api_key=anthropic_key)

    async def _chat(self, messages: Sequence[Dict[str, str]], structured_output: bool = False) -> str:
        """Send messages to Anthropic API and get response with optional structured output."""
        if structured_output:
            return await self._chat_structured(messages)
        else:
            return await self._chat_vanilla(messages)
    
    async def _chat_structured(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Anthropic API with structured output."""
        from pydantic import BaseModel, Field
        from typing import Literal, Optional
        
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
        
        try:
            # Create the message request with structured output
            response = await self.client.messages.create(
                model=self.model,
                system=system_content,
                messages=conversation,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # Parse the JSON response
            import json
            content = json.loads(response.content[0].text)
            
        except Exception:
            print('Anthropic Structured output failed! Falling back to vanilla.')
            return await self._chat_vanilla(messages)

        # Try to convert structured JSON into required string format
        try:
            action = content.get("action", "")
            amount = content.get("amount", 0)
            reason = content.get("reason", "")
            notes = content.get("notes", "")

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
            return response.content[0].text.strip()
    
    async def _chat_vanilla(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Anthropic API with vanilla string output."""
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
