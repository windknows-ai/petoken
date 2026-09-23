"""Central Daily / Token mode state with small transition hysteresis.

The activity input is provider-agnostic: any selected provider's live
claim feeds the same 0.4-second activation / 2-second deactivation
timing (V1.2 slice 4 generalizes the input without changing timing).
"""
import time

DAILY_MODE = "daily"
TOKEN_MODE = "token"


class AppModeState:
    def __init__(self, activate_after=.4, deactivate_after=2.0):
        self.mode = DAILY_MODE
        self.activate_after = activate_after
        self.deactivate_after = deactivate_after
        self.pending = None
        self.pending_since = None

    @property
    def is_token(self):
        return self.mode == TOKEN_MODE

    def update(self, active, reliable=True, now=None):
        now = time.monotonic() if now is None else now
        target = TOKEN_MODE if reliable and active else DAILY_MODE
        if target == self.mode:
            self.pending = None
            self.pending_since = None
            return self.mode
        if target != self.pending:
            self.pending = target
            self.pending_since = now
            return self.mode
        delay = self.activate_after if target == TOKEN_MODE else self.deactivate_after
        if now - self.pending_since >= delay:
            self.mode = target
            self.pending = None
            self.pending_since = None
        return self.mode
