from enum import StrEnum


class Outcome(StrEnum):
    CLOSE = "CLOSE"
    ESCALATE = "ESCALATE"

    def __str__(self) -> str:
        return str(self.value)
