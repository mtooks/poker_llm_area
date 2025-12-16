"""OpenAI player implementation for Poker RL agents."""

from typing import Sequence, Dict, Literal, Optional
from pydantic import BaseModel, Field

# Handle optional imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from utils.env_loader import get_env_value
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
        use_structured_output: bool = True,
    ):
        super().__init__(
            name=name,
            model=model,
            initial_stack=initial_stack,
            system_prompt=system_prompt,
            enable_reflection=enable_reflection,
            use_structured_output=use_structured_output,
        )
        
        # Initialize OpenAI client
        self._setup_openai_client()

    def _setup_openai_client(self):
        """Setup OpenAI client with API key."""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI provider requires the 'openai' package. Install with 'pip install openai'")

        openai_key = get_env_value("OPENAI_KEY", required=True)
        self.client = openai.AsyncOpenAI(api_key=openai_key)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to OpenAI API and get response with structured output when possible."""
        # Prefer structured output to reduce parsing errors
        # Use Literal to constrain action to only valid values
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

            # Action is now constrained by Literal, so we can trust it's valid
            if action in ("fold", "check", "call"):
                result = f"{action}@{reason}" if reason else action
            elif action == "raise_to":
                if not isinstance(amount, int) or amount <= 0:
                    raise ValueError(f"raise_to requires a positive integer amount, got: {amount}")
                result = f"raise_to:{amount}@{reason}" if reason else f"raise_to:{amount}"
            elif action in ("show", "muck"):
                result = action + "@"
                if action == 'show':
                    print("HOOOOOOOLLYYYYYY HE SHOWEEEEDDDD THE BLUFFFFF")
            else:
                # This should never happen due to Literal constraint, but handle it anyway
                print(f'Unexpected action received (should be impossible): action="{action}"')
                result = f"{action}@{reason}" if reason else action
            
            # Append notes if present
            if notes:
                result += f"\nNOTES: {notes}"
            
            return result
        except Exception as e:
            # If JSON parsing fails, return raw content
            print(f'Exception in structured output conversion: {e}')
            return content.strip() if isinstance(content, str) else str(content)
