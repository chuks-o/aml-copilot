from enum import StrEnum


class CaseStatus(StrEnum):
    CLOSED = "CLOSED"
    COMPLETE = "COMPLETE"
    ESCALATED = "ESCALATED"
    INVESTIGATING = "INVESTIGATING"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    OPEN = "OPEN"

    def __str__(self) -> str:
        return str(self.value)
