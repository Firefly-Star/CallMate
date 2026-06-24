"""End-to-end tests for mock mode."""
import tempfile
from pathlib import Path

from callmate.storage.profile_store import ProfileStore, Profile
from callmate.core.dialogue_manager import DialogueManager
from callmate.core.advisor import MockAdvisor
from callmate.core.presenter import Presenter
from callmate.core.command_handler import CommandHandler
from callmate.main import _build_command_handler, _select_profile


class TestProfileSelection:
    def test_select_by_name(self):
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        store.save(Profile(name="张老师", relationship="导师"))
        p = _select_profile(store, "张老师")
        assert p is not None
        assert p.name == "张老师"

    def test_select_nonexistent(self):
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        store.save(Profile(name="张老师", relationship="导师"))
        p = _select_profile(store, "不存在")
        assert p is None

    def test_select_empty_store(self):
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        p = _select_profile(store)
        assert p is None

    def test_select_single_auto(self, capsys):
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        store.save(Profile(name="张老师", relationship="导师"))
        p = _select_profile(store)
        assert p is not None
        assert p.name == "张老师"


class TestCommandHandlerBuild:
    def test_build_and_switch_profile(self):
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        store.save(Profile(name="张老师", relationship="导师"))
        store.save(Profile(name="李四", relationship="同事"))

        presenter = Presenter()
        dialogue_mgr = DialogueManager(soul_path=tempfile.mktemp(suffix=".md"))
        advisor = MockAdvisor()

        handler = _build_command_handler(presenter, dialogue_mgr, store, advisor)
        result = handler.execute(Command("profile", "李四"))
        assert "李四" in result
        assert handler._get_current_profile() == "李四"

    def test_help_works(self):
        handler = _build_command_handler(Presenter(), DialogueManager(), ProfileStore(), MockAdvisor())
        result = handler.execute(Command("help"))
        assert "/help" in result
        assert "/quit" in result


# Need to import Command here
from callmate.core.command_handler import Command


class TestMockFlow:
    def test_full_conversation_cycle(self):
        """Simulate a full mock conversation."""
        store = ProfileStore(path=tempfile.mktemp(suffix=".json"))
        profile = Profile(name="张老师", relationship="导师")
        store.save(profile)

        dialogue_mgr = DialogueManager(soul_path=tempfile.mktemp(suffix=".md"))
        advisor = MockAdvisor()
        presenter = Presenter(profile_name="张老师")
        handler = _build_command_handler(presenter, dialogue_mgr, store, advisor)

        soul, profile_text, _ = dialogue_mgr.build_prompt(profile)

        # Simulate: other person speaks
        dialogue_mgr.add_message("other", "这周实验进展怎么样？")
        soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
        suggestions = advisor.advise(soul, profile_text, transcript)
        assert len(suggestions) == 2
        assert suggestions[0]["text"] is not None

        # Simulate: user responds
        dialogue_mgr.add_message("user", "跑通了，效果不错")
        soul, profile_text, transcript = dialogue_mgr.build_prompt(profile)
        suggestions = advisor.advise(soul, profile_text, transcript)
        assert len(suggestions) == 2

        # Verify history
        history = dialogue_mgr.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "other"
        assert history[1]["role"] == "user"
