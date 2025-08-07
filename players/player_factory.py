"""Player factory for creating poker players with different LLM providers."""

from typing import Optional, Dict, List

from .openai_player import OpenAIPlayer
from .gemini_player import GeminiPlayer
from .anthropic_player import AnthropicPlayer


class PlayerFactory:
    """Factory class for creating poker players with different LLM providers."""
    
    # Supported models for each provider
    SUPPORTED_MODELS = {
        "openai": ["gpt-4o-mini"],
        "gemini": ["gemini-pro", "gemini-pro-vision"],
        "anthropic": ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest", "claude-opus-4-20250514", "claude-sonnet-4-20250514"],
        "grok": ["grok-4"]
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
        **kwargs
    ):
        """
        Create a player with the specified provider and model.
        
        Args:
            name: Player name
            provider: LLM provider ("openai", "gemini", "anthropic")
            model: Specific model to use (optional, uses default if not specified)
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
            model = cls.SUPPORTED_MODELS[provider][0]  # First model as default
        
        # Validate model for provider
        if model not in cls.SUPPORTED_MODELS[provider]:
            raise ValueError(
                f"Model '{model}' not supported for provider '{provider}'. "
                f"Supported models for {provider}: {cls.SUPPORTED_MODELS[provider]}"
            )
        
        # Create appropriate player
        if provider == "openai":
            return OpenAIPlayer(name, model, **kwargs)
        elif provider == "gemini":
            return GeminiPlayer(name, model, **kwargs)
        elif provider == "anthropic":
            return AnthropicPlayer(name, model, **kwargs)
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

    def create_grok_player(cls, name: str, model: str = "claude-3-sonnet", **kwargs):
        return cls.create_player(name, "grok", model, **kwargs)
    