"""Grok (xAI) player implementation for Poker RL agents."""

from typing import Sequence, Dict
from pydantic import BaseModel

# Handle optional imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from utils.env_loader import get_env_value
from .base_player import BasePlayer


class GrokPlayer(BasePlayer):
    """xAI Grok-specific player implementation using OpenAI-compatible API."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
        enable_reflection: bool = False,
        use_structured_output: bool = False,
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=use_structured_output,
        )

        # Initialize Grok client (OpenAI-compatible, different base_url)
        self._setup_grok_client()

    def _setup_grok_client(self) -> None:
        """Setup Grok client with API key via OpenAI SDK against xAI endpoint."""
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "Grok provider requires the 'openai' package. Install with 'pip install openai'"
            )

        xai_key = get_env_value("XAI_API_KEY", required=True)

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
