"""Player factory for creating poker players with different LLM providers."""

from typing import Optional, Dict, List

from .openai_player import OpenAIPlayer
from .gemini_player import GeminiPlayer
from .anthropic_player import AnthropicPlayer
from .all_in_player import AllInPlayer
from .grok_player import GrokPlayer
from .callbox_player import CallboxPlayer
from .gto_player import GTOPlayer

class PlayerFactory:
    """Factory class for creating poker players with different LLM providers."""
    
    # Supported models for each provider
    SUPPORTED_MODELS = {
        "openai": ["gpt-4o-mini",'gpt-5-mini'],
        "gemini": ["gemini-pro", "gemini-pro-vision"],
        "anthropic": ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest", "claude-opus-4-20250514", "claude-sonnet-4-20250514"],
        "grok": ["grok-4","grok-3","grok-3-mini"],
        "callbox": ["callbox-bot"],
        "all-in": ["all-in-bot"],
        "gto": ["gto-bot"]
    }
    
    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported providers."""
        return list(cls.SUPPORTED_MODELS.keys())
    
    @classmethod
    def get_supported_models(cls, provider: str) -> List[str]:
        """Get list of supported models for a specific provider."""
        return cls.SUPPORTED_MODELS.get(provider, [])
    
    @classmethod
    def create_player(
        cls, 
        name: str, 
        provider: str, 
        model: Optional[str] = None, 
        enable_reflection: bool = False,
        use_structured_output: bool = None,
        **kwargs
    ):
        """
        Create a player with the specified provider and model.
        
        Args:
            name: Player name
            provider: LLM provider ("openai", "gemini", "anthropic")
            model: Specific model to use (optional; defaults to first known model for the provider)
            enable_reflection: Whether to enable hand reflection
            use_structured_output: Whether to use structured output (None = provider default)
            **kwargs: Additional arguments passed to player constructor
            
        Returns:
            Player instance
            
        Raises:
            ValueError: If provider or model is not supported
        """
        # Validate provider
        if provider not in cls.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {list(cls.SUPPORTED_MODELS.keys())}"
            )
        
        # Use default model if none specified
        if model is None:
            defaults = cls.SUPPORTED_MODELS.get(provider, [])
            if not defaults:
                raise ValueError(f"No default model configured for provider '{provider}'. Please specify a model.")
            model = defaults[0]  # First model as default
        
        # Create appropriate player
        if provider == "openai":
            return OpenAIPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "gemini":
            return GeminiPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "anthropic":
            return AnthropicPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "all-in":
            return AllInPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "grok":
            return GrokPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "callbox":
            return CallboxPlayer(name, model, enable_reflection=enable_reflection, use_structured_output=use_structured_output, **kwargs)
        elif provider == "gto":
            return GTOPlayer(name, model, enable_reflection=enable_reflection, **kwargs)
        else:
            # This should never happen due to validation above
            raise ValueError(f"Unknown provider: {provider}")
    
    @classmethod
    def create_openai_player(cls, name: str, model: str = "gpt-4", **kwargs):
        """Convenience method to create an OpenAI player."""
        return cls.create_player(name, "openai", model, **kwargs)
    
    @classmethod
    def create_gemini_player(cls, name: str, model: str = "gemini-pro", **kwargs):
        """Convenience method to create a Gemini player."""
        return cls.create_player(name, "gemini", model, **kwargs)
    
    @classmethod
    def create_anthropic_player(cls, name: str, model: str = "claude-3-sonnet", **kwargs):
        """Convenience method to create an Anthropic player."""
        return cls.create_player(name, "anthropic", model, **kwargs) 

    @classmethod
    def create_grok_player(cls, name: str, model: str = "grok-4", **kwargs):
        """Convenience method to create a Grok (xAI) player."""
        return cls.create_player(name, "grok", model, **kwargs)

    @classmethod
    def create_gto_player(cls, name: str, model: str = "gto-bot", **kwargs):
        """Convenience method to create the deterministic GTO baseline player."""
        return cls.create_player(name, "gto", model, **kwargs)
    
