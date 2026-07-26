_current_state = {}


def update_state(data: dict) -> dict:
    """Updates internal state and returns only keys that actually changed."""
    changed = {}
    for key, value in data.items():
        if _current_state.get(key) != value:
            _current_state[key] = value
            changed[key] = value
    return changed


def get_state() -> dict:
    """Returns a copy of the current state snapshot."""
    return _current_state.copy()
