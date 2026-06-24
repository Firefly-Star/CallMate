"""Tests for dialogue_manager."""
import tempfile
from pathlib import Path
from storage.profile_store import Profile
from core.dialogue_manager import DialogueManager


def _make_dm() -> tuple[DialogueManager, str]:
    """Create a DialogueManager with a temporary SOUL.md path."""
    tmp = tempfile.mktemp(suffix=".md")
    dm = DialogueManager(soul_path=tmp)
    return dm, tmp


def _cleanup(tmp_path: str) -> None:
    Path(tmp_path).unlink(missing_ok=True)


class TestDialogueManagerMessages:
    def test_add_message(self):
        dm, tmp = _make_dm()
        msg = dm.add_message("other", "你好")
        assert msg.role == "other"
        assert msg.content == "你好"
        assert msg.time is not None
        _cleanup(tmp)

    def test_get_history(self):
        dm, tmp = _make_dm()
        dm.add_message("other", "你好")
        dm.add_message("user", "嗨")
        history = dm.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "other", "content": "你好", "time": history[0]["time"]}
        assert history[1]["role"] == "user"
        assert history[1]["content"] == "嗨"

    def test_clear(self):
        dm, tmp = _make_dm()
        dm.add_message("other", "你好")
        dm.clear()
        assert dm.get_history() == []
        _cleanup(tmp)

    def test_empty_history(self):
        dm, tmp = _make_dm()
        assert dm.get_history() == []
        _cleanup(tmp)


class TestDialogueManagerSOUL:
    def test_default_soul_created(self):
        dm, tmp = _make_dm()
        soul = dm.load_soul()
        assert "# SOUL.md" in soul
        assert len(soul) > 50
        _cleanup(tmp)

    def test_save_and_load_soul(self):
        dm, tmp = _make_dm()
        custom = "# Custom SOUL\nI speak formally."
        dm.save_soul(custom)
        loaded = dm.load_soul()
        assert loaded == custom
        _cleanup(tmp)

    def test_soul_persists_across_instances(self):
        dm1, tmp = _make_dm()
        dm1.save_soul("# Persisted SOUL")
        dm2 = DialogueManager(soul_path=tmp)
        assert dm2.load_soul() == "# Persisted SOUL"
        _cleanup(tmp)


class TestDialogueManagerPrompt:
    def test_build_prompt_no_profile(self):
        dm, tmp = _make_dm()
        soul, profile_text, transcript = dm.build_prompt()
        assert "# SOUL.md" in soul
        assert profile_text == ""
        assert transcript == []
        _cleanup(tmp)

    def test_build_prompt_with_profile(self):
        dm, tmp = _make_dm()
        dm.add_message("other", "你好")
        profile = Profile(name="张老师", relationship="导师")
        soul, profile_text, transcript = dm.build_prompt(profile)
        assert "# SOUL.md" in soul
        assert "张老师" in profile_text
        assert "导师" in profile_text
        assert len(transcript) == 1
        _cleanup(tmp)

    def test_format_profile_all_fields(self):
        profile = Profile(
            name="李四",
            relationship="同事",
            occasion="项目讨论",
            topics=["进度同步", "下周计划"],
            notes=["他比较忙，尽量简短"],
            keywords=["deadline", "交付"],
        )
        text = DialogueManager._format_profile(profile)
        assert "李四" in text
        assert "同事" in text
        assert "项目讨论" in text
        assert "进度同步" in text
        assert "他比较忙" in text
        assert "deadline" in text

    def test_build_prompt_with_history(self):
        dm, tmp = _make_dm()
        dm.add_message("other", "最近怎么样？")
        dm.add_message("user", "还行")
        dm.add_message("other", "项目进度呢？")
        profile = Profile(name="张老师", relationship="导师")
        soul, profile_text, transcript = dm.build_prompt(profile)
        assert len(transcript) == 3
        assert transcript[0]["content"] == "最近怎么样？"
        assert transcript[2]["content"] == "项目进度呢？"
        _cleanup(tmp)
