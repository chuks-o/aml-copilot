from enum import StrEnum


class Typology(StrEnum):
    BIPARTITE = "BIPARTITE"
    CYCLE = "CYCLE"
    FAN_IN = "FAN_IN"
    FAN_OUT = "FAN_OUT"
    GATHER_SCATTER = "GATHER_SCATTER"
    RANDOM = "RANDOM"
    SCATTER_GATHER = "SCATTER_GATHER"
    STACK = "STACK"

    def __str__(self) -> str:
        return str(self.value)
