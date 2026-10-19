"""Synthetic session store for the G05 fixture (never run)."""


class Sessions:
    def __init__(self):
        self.live = {}

    def new_session(self, user):
        token = "s-%d" % (len(self.live) + 1)
        self.live[token] = user
        return token
