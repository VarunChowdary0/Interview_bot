import json
from typing import AsyncIterator, Type, TypeVar
from pydantic import BaseModel

from services.llm.base import LLMProvider, LLMMessage, LLMConfig

T = TypeVar("T", bound=BaseModel)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude LLM provider implementation."""

    def __init__(self, api_key: str, config: LLMConfig):
        super().__init__(api_key, config)
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _format_messages_for_claude(self, messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Format messages for Claude API (separate system prompt)."""
        system_prompt = ""
        conversation = []

        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            else:
                # Claude uses "user" and "assistant" roles
                role = "user" if msg.role == "user" else "assistant"
                conversation.append({"role": role, "content": msg.content})

        return system_prompt.strip(), conversation

    async def generate(self, messages: list[LLMMessage]) -> str:
        """Generate a text response from Claude."""
        text, _ = await self.generate_with_usage(messages)
        return text

    async def generate_with_usage(self, messages: list[LLMMessage]) -> tuple[str, dict]:
        """Generate response and return usage info."""
        system_prompt, conversation = self._format_messages_for_claude(messages)

        # Build kwargs - only include system if non-empty
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": conversation,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self.client.messages.create(**kwargs)
        text = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens if response.usage else 0,
            "output_tokens": response.usage.output_tokens if response.usage else 0,
            "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
        }
        return text, usage

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        response_model: Type[T],
    ) -> T:
        """Generate a structured response using Claude."""
        # Add JSON instruction to the system prompt
        json_instruction = f"Respond with valid JSON matching this schema:\n{json.dumps(response_model.model_json_schema(), indent=2)}\n\nReturn ONLY the JSON object, no other text."

        # Prepend instruction to messages
        augmented_messages = [LLMMessage(role="system", content=json_instruction)] + messages

        system_prompt, conversation = self._format_messages_for_claude(augmented_messages)

        # Build kwargs - only include system if non-empty
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": conversation,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self.client.messages.create(**kwargs)

        content = response.content[0].text

        # Parse JSON (handle potential markdown code blocks)
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        data = json.loads(content)
        return response_model.model_validate(data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        """Stream response tokens from Claude."""
        system_prompt, conversation = self._format_messages_for_claude(messages)

        # Build kwargs - only include system if non-empty
        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": conversation,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
