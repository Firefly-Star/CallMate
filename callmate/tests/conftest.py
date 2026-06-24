import tempfile
import pytest
from storage.profile_store import ProfileStore

@pytest.fixture
def profile_store():
    """ProfileStore with a temporary JSON file."""
    tmp = tempfile.mktemp(suffix=".json")
    store = ProfileStore(path=tmp)
    yield store
    import os
    os.remove(tmp)
