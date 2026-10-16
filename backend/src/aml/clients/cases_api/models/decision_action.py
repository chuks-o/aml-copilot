from enum import StrEnum


class DecisionAction(StrEnum):
    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"

    def __str__(self) -> str:
        return str(self.value)
