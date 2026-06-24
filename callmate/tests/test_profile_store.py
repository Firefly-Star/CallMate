"""Tests for profile_store."""
from callmate.storage.profile_store import ProfileStore, Profile


class TestProfileStore:
    def test_list_empty(self, profile_store):
        assert profile_store.list() == []

    def test_get_nonexistent(self, profile_store):
        assert profile_store.get("不存在") is None

    def test_save_and_list(self, profile_store):
        profile_store.save(Profile(name="张老师", relationship="导师"))
        assert profile_store.list() == ["张老师"]

    def test_get_existing(self, profile_store):
        profile_store.save(Profile(name="张老师", relationship="导师"))
        p = profile_store.get("张老师")
        assert p is not None
        assert p.name == "张老师"
        assert p.relationship == "导师"

    def test_save_update(self, profile_store):
        profile_store.save(Profile(name="张老师", relationship="导师"))
        p = profile_store.get("张老师")
        p.notes.append("新备注")
        profile_store.save(p)
        p2 = profile_store.get("张老师")
        assert "新备注" in p2.notes

    def test_delete(self, profile_store):
        profile_store.save(Profile(name="李四", relationship="同事"))
        assert profile_store.delete("李四") is True
        assert profile_store.list() == []

    def test_delete_nonexistent(self, profile_store):
        assert profile_store.delete("不存在") is False
