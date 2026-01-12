from abc import ABC, abstractmethod
from typing import AsyncIterator, Type, TypeVar
from pydantic import BaseModel
from dataclasses import dataclass, field
from datetime import datetime


class LLMMessage(BaseModel):
    """A message in the LLM conversation."""
    role: str  # "system", "user", "assistant"
    content: str


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30


@dataclass
class LLMCallLog:
    """Log entry for a single LLM call."""
    call_type: str  # "preplan", "greeting", "question", "evaluate", "conclusion", "report"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model: str = ""
    prompt_messages: list = field(default_factory=list)
    response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "call_type": self.call_type,
            "timestamp": self.timestamp,
            "model": self.model,
            "prompt_messages": self.prompt_messages,
            "response": self.response,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
        }


T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, config: LLMConfig):
        self.api_key = api_key
        self.config = config

    @abstractmethod
    async def generate(self, messages: list[LLMMessage]) -> str:
        """Generate a text response from the LLM.

        Args:
            messages: List of conversation messages.

        Returns:
            Generated text response.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[LLMMessage],
        response_model: Type[T],
    ) -> T:
        """Generate a structured response validated against a Pydantic model.

        Args:
            messages: List of conversation messages.
            response_model: Pydantic model class for response validation.

        Returns:
            Validated Pydantic model instance.
        """
        pass

    @abstractmethod
    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        """Stream response tokens from the LLM.

        Args:
            messages: List of conversation messages.

        Yields:
            Response tokens as they are generated.
        """
        pass

    def _format_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Convert LLMMessage objects to provider-specific format."""
        return [{"role": m.role, "content": m.content} for m in messages]

    @abstractmethod
    async def generate_with_usage(self, messages: list[LLMMessage]) -> tuple[str, dict]:
        """Generate response and return usage info.

        Returns:
            Tuple of (response_text, usage_dict) where usage_dict contains:
            - input_tokens: int
            - output_tokens: int
            - total_tokens: int
        """
        pass
