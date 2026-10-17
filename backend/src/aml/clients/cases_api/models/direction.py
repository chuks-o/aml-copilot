from enum import StrEnum


class Direction(StrEnum):
    IN = "IN"
    OUT = "OUT"
    SELF = "SELF"

    def __str__(self) -> str:
        return str(self.value)
