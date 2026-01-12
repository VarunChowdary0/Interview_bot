from typing import Optional
from functools import lru_cache

from services.llm.base import LLMProvider, LLMConfig
from services.llm.openai_provider import OpenAIProvider
from services.llm.claude_provider import ClaudeProvider
from config import get_settings


class LLMFactory:
    """Factory for creating LLM provider instances."""

    _providers: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
    }

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ) -> LLMProvider:
        """Create an LLM provider instance.

        Args:
            provider: Provider name ("openai" or "claude").
            api_key: API key (uses settings if not provided).
            config: LLM configuration (uses defaults if not provided).

        Returns:
            LLMProvider instance.

        Raises:
            ValueError: If provider is not supported.
        """
        if provider not in cls._providers:
            raise ValueError(f"Unsupported provider: {provider}. Supported: {list(cls._providers.keys())}")

        settings = get_settings()

        # Get API key from settings if not provided
        if api_key is None:
            if provider == "openai":
                api_key = settings.openai_api_key
            elif provider == "claude":
                api_key = settings.claude_api_key

        if not api_key:
            raise ValueError(f"API key not provided for {provider}")

        # Get config from settings if not provided
        if config is None:
            if provider == "openai":
                config = LLMConfig(
                    model=settings.openai_model,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    timeout=settings.llm_timeout,
                )
            elif provider == "claude":
                config = LLMConfig(
                    model=settings.claude_model,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    timeout=settings.llm_timeout,
                )

        provider_class = cls._providers[provider]
        return provider_class(api_key, config)

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a new provider class."""
        cls._providers[name] = provider_class


@lru_cache()
def get_llm_provider(provider: Optional[str] = None) -> LLMProvider:
    """Get a cached LLM provider instance.

    Args:
        provider: Provider name (uses settings default if not provided).

    Returns:
        LLMProvider instance.
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    return LLMFactory.create(provider)
