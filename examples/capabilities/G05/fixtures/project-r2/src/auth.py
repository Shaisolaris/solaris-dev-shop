"""Synthetic sign-in handler for the G05 fixture (never run). r2: constant-time compare, session rotation."""
import hmac


def sign_in(store, user, password):
    record = store.get(user)
    if record is None or not hmac.compare_digest(record["password"], password):
        return None
    store.drop_sessions(user)
    return {"user": user, "session": store.new_session(user)}
