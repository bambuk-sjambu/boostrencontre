"""Shared dependencies for route modules."""

ALLOWED_PLATFORMS: set = set()


def init_platforms(allowed: set):
    global ALLOWED_PLATFORMS
    ALLOWED_PLATFORMS = allowed


def validate_platform(platform: str) -> bool:
    """Check platform against whitelist."""
    return platform in ALLOWED_PLATFORMS
