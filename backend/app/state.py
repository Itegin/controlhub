_current_state: dict = {}


def update_state(data: dict) -> dict:
    # Only return keys that actually changed value so callers can broadcast a
    # minimal diff instead of re-sending the whole state on every heartbeat.
    changed = {}
    for key, value in data.items():
        if _current_state.get(key) != value:
            _current_state[key] = value
            changed[key] = value
    return changed


def get_state() -> dict:
    return dict(_current_state)
