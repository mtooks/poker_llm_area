# Structured Output Constraints with Pydantic Literal

## Problem

LLMs sometimes return invalid actions like `"raise"` or `"bet"` instead of the required `"raise_to"`, causing parsing errors.

## Solution: Using `Literal` Type

Pydantic's `Literal` type enforces that the LLM can **only** return values from a predefined list. This is enforced at the schema level, so the LLM provider (OpenAI, Anthropic, etc.) will reject invalid values.

## How It Works

### Before (Unconstrained)
```python
class PokerAction(BaseModel):
    action: str  # ❌ Can be ANY string
    amount: int
    reason: str
    notes: str
```

**Problem:** LLM can return `action="raise"`, `action="bet"`, `action="all_in"`, etc.

### After (Constrained)
```python
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
```

**Benefits:**
- ✅ LLM **cannot** return invalid actions
- ✅ Provider validates against JSON schema
- ✅ Pydantic validates on parse
- ✅ Clear error messages if validation fails

## Provider Support

### OpenAI (`responses.parse`)
- ✅ Fully supports `Literal` via JSON schema
- Automatically converts Pydantic model to JSON schema
- Rejects invalid values at API level

### Anthropic (`response_format={"type": "json_object"}`)
- ✅ Supports enum constraints in JSON schema
- Requires manual JSON schema definition (Pydantic handles this)

### Gemini (`response_schema`)
- ✅ Supports Pydantic models with Literal
- Automatically converts to JSON schema

### Grok (OpenAI-compatible)
- ✅ Same as OpenAI, fully supported

## Validation Layers

1. **Provider Level**: API rejects invalid JSON that doesn't match schema
2. **Pydantic Level**: If JSON passes, Pydantic validates the Literal constraint
3. **Application Level**: Your code can trust the action is valid

## Example Error Handling

If an LLM tries to return `action="raise"`:

```python
# Provider will reject it or Pydantic will raise:
ValidationError: 1 validation error for PokerAction
action
  Input should be 'fold', 'check', 'call', 'raise_to', 'show' or 'muck' [type=literal_error, input_value='raise', input_type=str]
```

## Additional Improvements

1. **Optional `amount`**: Only required for `raise_to`, ignored otherwise
2. **Field descriptions**: Help LLM understand constraints
3. **Default values**: Prevent missing fields

## Testing

To verify constraints work:

```python
from pydantic import ValidationError

# This should work
action = PokerAction(action="fold", amount=0, reason="Weak hand", notes="")
assert action.action == "fold"

# This should fail
try:
    action = PokerAction(action="raise", amount=100, reason="...", notes="")
except ValidationError as e:
    print("✅ Constraint working! Invalid action rejected.")
```

## Migration Notes

All player implementations have been updated:
- ✅ `OpenAIPlayer`
- ✅ `AnthropicPlayer`
- ✅ `GeminiPlayer`
- ✅ `GrokPlayer`

The parsing logic has been simplified since we can now trust the action is valid.

