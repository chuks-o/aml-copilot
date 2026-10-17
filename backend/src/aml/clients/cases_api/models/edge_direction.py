from enum import StrEnum


class EdgeDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"

    def __str__(self) -> str:
        return str(self.value)
