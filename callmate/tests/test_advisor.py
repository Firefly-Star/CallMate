"""Tests for advisor."""
import json
from callmate.core.advisor import (
    MockAdvisor,
    OpenAIAdvisor,
    AnthropicAdvisor,
    create_advisor,
)

_SOUL = "# SOUL\nI speak casually."
_PROFILE = "Name: 张老师\nRelationship: 导师"
_TRANSCRIPT = [
    {"role": "user", "content": "这周实验进展怎么样？"},
    {"role": "assistant", "content": "跑通了"},
]


class TestMockAdvisor:
    def test_returns_canned(self):
        advisor = MockAdvisor()
        result = advisor.advise(_SOUL, _PROFILE, _TRANSCRIPT)
        assert len(result) == 2
        assert "text" in result[0]
        assert "reason" in result[0]

    def test_custom_canned(self):
        custom = [{"text": "自定义建议", "reason": "自定义理由"}]
        advisor = MockAdvisor(canned=custom)
        result = advisor.advise(_SOUL, _PROFILE, _TRANSCRIPT)
        assert result == custom

    def test_records_inputs(self):
        advisor = MockAdvisor()
        advisor.advise(_SOUL, _PROFILE, _TRANSCRIPT)
        assert advisor.last_system == _SOUL
        assert advisor.last_profile == _PROFILE
        assert advisor.last_transcript == _TRANSCRIPT

    def test_empty_transcript(self):
        advisor = MockAdvisor()
        result = advisor.advise("", "", [])
        assert len(result) == 2


class TestSystemPrompt:
    def test_build_system_with_soul_and_profile(self):
        advisor = MockAdvisor()
        system = advisor._build_system(_SOUL, _PROFILE)
        assert "My Communication Style" in system
        assert "I speak casually" in system
        assert "Contact Information" in system
        assert "张老师" in system
        assert "导师" in system

    def test_build_system_empty_profile(self):
        advisor = MockAdvisor()
        system = advisor._build_system(_SOUL, "")
        assert "My Communication Style" in system
        assert "Contact Information" not in system

    def test_build_system_empty_soul(self):
        advisor = MockAdvisor()
        system = advisor._build_system("", _PROFILE)
        assert "Contact Information" in system
        assert "My Communication Style" not in system

    def test_build_system_contains_guidelines(self):
        advisor = MockAdvisor()
        system = advisor._build_system(_SOUL, _PROFILE)
        assert "2-3 options" in system
        assert "[推荐]" in system


class TestToolExecution:
    def test_execute_unknown_tool(self):
        advisor = MockAdvisor()
        result = json.loads(advisor._execute_tool("unknown", {}))
        assert "error" in result

    def test_session_search_returns_json(self):
        advisor = MockAdvisor()
        result_text = advisor._execute_tool("session_search", {"query": "实验进展"})
        result = json.loads(result_text)
        assert "found" in result


class TestSuggestionParsing:
    def test_parse_valid_json(self):
        content = json.dumps([
            {"text": "建议一", "reason": "理由一"},
            {"text": "建议二", "reason": "理由二"},
        ])
        result = OpenAIAdvisor._parse_suggestions(content)
        assert len(result) == 2

    def test_parse_markdown_json(self):
        content = f"""```json
{json.dumps([{"text": "建议一", "reason": "理由一"}])}
```"""
        result = OpenAIAdvisor._parse_suggestions(content)
        assert len(result) == 1
        assert result[0]["text"] == "建议一"

    def test_parse_empty(self):
        result = OpenAIAdvisor._parse_suggestions("")
        assert result == []

    def test_parse_invalid_as_fallback(self):
        result = OpenAIAdvisor._parse_suggestions("直接回复就好")
        assert len(result) == 1
        assert result[0]["text"] == "直接回复就好"


class TestFactory:
    def test_create_mock(self):
        advisor = create_advisor("mock")
        assert isinstance(advisor, MockAdvisor)

    def test_create_openai_no_key_raises(self):
        import pytest
        with pytest.raises(Exception):
            create_advisor("openai")

    def test_create_unknown_provider(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_advisor("nonexistent")
