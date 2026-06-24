"""LLM advisor with tool calling support.

Provides response suggestions based on the three-layer prompt
(SOUL + Profile + Transcript). Supports multiple LLM backends
and uses native tool calling for historical session search.

Usage:
    advisor = create_advisor(config)
    suggestions = advisor.advise(soul_text, profile_text, transcript)
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Optional

from callmate.storage.history_store import HistoryStore


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_SESSION_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "session_search",
        "description": (
            "Search your past call history with this contact. "
            "Use this when you need to recall what was discussed before."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in past conversations",
                }
            },
            "required": ["query"],
        },
    },
}

_SYSTEM_TEMPLATE = """You are CallMate, a real-time call assistant designed to help introverts navigate phone calls naturally.

Your job is to listen to the conversation and suggest what the user could say next.

## Guidelines
- Suggest 2-3 options at different confidence levels (e.g. one safe, one more direct).
- Keep suggestions concise — the user needs to read them quickly during a call.
- Match the user's speaking style as described in their SOUL profile.
- Never write long paragraphs. One sentence per suggestion is ideal.
- Mark which option you recommend most with "[推荐]".

## Output Format
Return your response as a JSON array of objects:
```json
[
  {"text": "具体建议的话", "reason": "为什么这么说"},
  {"text": "另一个选项", "reason": "这个的考虑是什么"}
]
```"""


# ---------------------------------------------------------------------------
# Base advisor
# ---------------------------------------------------------------------------

class BaseAdvisor(ABC):
    """Abstract base for LLM advisors."""

    def __init__(self, history_store: Optional[HistoryStore] = None):
        self._history = history_store or HistoryStore()

    @abstractmethod
    def advise(
        self,
        soul_text: str,
        profile_text: str,
        transcript: list[dict],
    ) -> list[dict]:
        """Given SOUL + Profile + Transcript, return suggestion list.

        Returns:
            [{"text": "...", "reason": "..."}, ...]
        """
        ...

    def _build_system(self, soul_text: str, profile_text: str) -> str:
        """Assemble the system prompt from SOUL + Profile."""
        parts = [_SYSTEM_TEMPLATE]

        if soul_text:
            parts.append(f"\n## My Communication Style\n{soul_text}")

        if profile_text:
            parts.append(f"\n## Contact Information\n{profile_text}")

        return "\n\n".join(parts)

    def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool call and return its result as text."""
        if name == "session_search":
            query = args.get("query", "")
            results = self._history.search(query)
            if not results:
                return json.dumps({"found": False, "message": "No relevant history found."})
            return json.dumps({"found": True, "results": results}, ensure_ascii=False)
        return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

class OpenAIAdvisor(BaseAdvisor):
    """Advisor using OpenAI-compatible API (OpenAI, DeepSeek, etc.)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        history_store: Optional[HistoryStore] = None,
    ):
        super().__init__(history_store)
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model

    def advise(
        self,
        soul_text: str,
        profile_text: str,
        transcript: list[dict],
    ) -> list[dict]:
        system = self._build_system(soul_text, profile_text)
        messages = [{"role": "system", "content": system}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in transcript)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=[_SESSION_SEARCH_TOOL],
            temperature=0.7,
        )

        return self._handle_response(response, messages)

    def _handle_response(self, response: Any, messages: list[dict]) -> list[dict]:
        choice = response.choices[0]
        msg = choice.message

        # Tool calling loop
        while msg.tool_calls:
            for tool_call in msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = self._execute_tool(tool_call.function.name, args)
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=[_SESSION_SEARCH_TOOL],
                temperature=0.7,
            )
            choice = response.choices[0]
            msg = choice.message

        return self._parse_suggestions(msg.content)

    @staticmethod
    def _parse_suggestions(content: Optional[str]) -> list[dict]:
        if not content:
            return []
        # Try to extract JSON from markdown code block or plain JSON
        content = content.strip()
        if content.startswith("```"):
            # Find JSON in markdown code block
            start = content.find("\n") + 1
            end = content.rfind("```")
            if end > start:
                content = content[start:end].strip()
        try:
            suggestions = json.loads(content)
            if isinstance(suggestions, list):
                return suggestions
            return []
        except json.JSONDecodeError:
            # Fallback: return raw text as single suggestion
            return [{"text": content, "reason": ""}]


# ---------------------------------------------------------------------------
# Anthropic backend
# ---------------------------------------------------------------------------

class AnthropicAdvisor(BaseAdvisor):
    """Advisor using Anthropic API (Claude)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku",
        history_store: Optional[HistoryStore] = None,
    ):
        super().__init__(history_store)
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def advise(
        self,
        soul_text: str,
        profile_text: str,
        transcript: list[dict],
    ) -> list[dict]:
        system = self._build_system(soul_text, profile_text)
        messages = [{"role": m["role"], "content": m["content"]} for m in transcript]

        response = self._client.messages.create(
            model=self._model,
            system=system,
            messages=messages,
            tools=[self._anthropic_tool()],
            max_tokens=1024,
            temperature=0.7,
        )

        return self._handle_response(response, messages, system)

    @staticmethod
    def _anthropic_tool() -> dict:
        """Convert session_search to Anthropic tool format."""
        t = _SESSION_SEARCH_TOOL
        return {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }

    def _handle_response(
        self,
        response: Any,
        messages: list[dict],
        system: str,
    ) -> list[dict]:
        while response.stop_reason == "tool_use":
            tool_block = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_block = block
                    break

            if tool_block is None:
                break

            args = json.loads(tool_block.input) if hasattr(tool_block, 'input') else {}
            result = self._execute_tool(tool_block.name, args)

            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                }],
            })

            response = self._client.messages.create(
                model=self._model,
                system=system,
                messages=messages,
                tools=[self._anthropic_tool()],
                max_tokens=1024,
                temperature=0.7,
            )

        # Extract text from content blocks
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        return self._parse_suggestions(text)

    @staticmethod
    def _parse_suggestions(content: str) -> list[dict]:
        return OpenAIAdvisor._parse_suggestions(content)


# ---------------------------------------------------------------------------
# Mock advisor (for testing)
# ---------------------------------------------------------------------------

class MockAdvisor(BaseAdvisor):
    """Mock advisor that returns canned responses. No API calls."""

    def __init__(self, canned: Optional[list[dict]] = None):
        super().__init__()
        self._canned = canned or [
            {"text": "你可以说：好的，我明白了。", "reason": "稳妥的回复"},
            {"text": "或者说：让我想想再回答你。", "reason": "争取思考时间"},
        ]
        self.last_system = ""
        self.last_profile = ""
        self.last_transcript: list[dict] = []
        self.tool_calls: list[tuple[str, dict]] = []

    def advise(
        self,
        soul_text: str,
        profile_text: str,
        transcript: list[dict],
    ) -> list[dict]:
        self.last_system = soul_text
        self.last_profile = profile_text
        self.last_transcript = transcript
        return self._canned.copy()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_advisor(
    provider: str = "mock",
    api_key: str = "",
    model: str = "gpt-4o-mini",
    base_url: Optional[str] = None,
    history_store: Optional[HistoryStore] = None,
) -> BaseAdvisor:
    """Create an advisor based on the provider name."""
    if provider == "mock":
        return MockAdvisor()
    elif provider == "openai":
        return OpenAIAdvisor(api_key, model, base_url, history_store)
    elif provider == "deepseek":
        url = base_url or "https://api.deepseek.com/v1"
        return OpenAIAdvisor(api_key, model, url, history_store)
    elif provider == "anthropic":
        return AnthropicAdvisor(api_key, model, history_store)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
