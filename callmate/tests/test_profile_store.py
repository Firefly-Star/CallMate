"""Tests for profile_store."""
from storage.profile_store import ProfileStore, Profile


class TestProfileStore:
    def test_list_defaults(self, profile_store):
        names = profile_store.list()
        assert "张老师" in names

    def test_get_existing(self, profile_store):
        p = profile_store.get("张老师")
        assert p is not None
        assert p.name == "张老师"
        assert p.relationship == "研究生导师"

    def test_get_nonexistent(self, profile_store):
        assert profile_store.get("不存在") is None

    def test_save_new(self, profile_store):
        profile_store.save(Profile(name="李四", relationship="同事"))
        assert "李四" in profile_store.list()

    def test_save_update(self, profile_store):
        p = profile_store.get("张老师")
        p.notes.append("新备注")
        profile_store.save(p)
        p2 = profile_store.get("张老师")
        assert "新备注" in p2.notes

    def test_delete(self, profile_store):
        profile_store.save(Profile(name="李四", relationship="同事"))
        assert profile_store.delete("李四") is True
        assert "李四" not in profile_store.list()

    def test_delete_nonexistent(self, profile_store):
        assert profile_store.delete("不存在") is False
