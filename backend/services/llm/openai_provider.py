import json
from typing import AsyncIterator, Type, TypeVar
from pydantic import BaseModel

from services.llm.base import LLMProvider, LLMMessage, LLMConfig

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""

    def __init__(self, api_key: str, config: LLMConfig):
        super().__init__(api_key, config)
        self._client = None

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(self, messages: list[LLMMessage]) -> str:
        """Generate a text response from OpenAI."""
        text, _ = await self.generate_with_usage(messages)
        return text

    async def generate_with_usage(self, messages: list[LLMMessage]) -> tuple[str, dict]:
        """Generate response and return usage info."""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=self._format_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        text = response.choices[0].message.content
        usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        return text, usage

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        response_model: Type[T],
    ) -> T:
        """Generate a structured response using OpenAI's JSON mode."""
        # Add instruction to return JSON
        system_msg = messages[0] if messages and messages[0].role == "system" else None
        json_instruction = f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(response_model.model_json_schema(), indent=2)}"

        formatted_messages = self._format_messages(messages)
        if system_msg:
            formatted_messages[0]["content"] += json_instruction
        else:
            formatted_messages.insert(0, {"role": "system", "content": json_instruction})

        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=formatted_messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return response_model.model_validate(data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        """Stream response tokens from OpenAI."""
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=self._format_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
