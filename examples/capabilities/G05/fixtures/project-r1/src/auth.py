"""Synthetic sign-in handler for the G05 fixture (never run)."""


def sign_in(store, user, password):
    record = store.get(user)
    if record is None or record["password"] != password:
        return None
    return {"user": user, "session": store.new_session(user)}
