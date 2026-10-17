from enum import StrEnum


class AlertStatus(StrEnum):
    DISMISSED = "DISMISSED"
    IN_CASE = "IN_CASE"
    OPEN = "OPEN"

    def __str__(self) -> str:
        return str(self.value)
