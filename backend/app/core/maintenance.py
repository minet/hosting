"""In-memory maintenance mode flag."""

_maintenance = False


def is_maintenance() -> bool:
    return _maintenance


def set_maintenance(enabled: bool) -> None:
    global _maintenance
    _maintenance = enabled
