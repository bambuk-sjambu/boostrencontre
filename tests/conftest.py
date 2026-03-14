import copy
import os
import pytest

# Enable debug routes for tests (must be set before src.app is imported)
os.environ.setdefault("DEBUG", "true")


@pytest.fixture(autouse=True)
def restore_my_profile():
    """Save and restore MY_PROFILE between tests to prevent cross-test pollution."""
    from src.messaging.ai_messages import MY_PROFILE
    original = copy.deepcopy(MY_PROFILE)
    yield
    MY_PROFILE.clear()
    MY_PROFILE.update(original)
