from enum import StrEnum


class EntityType(StrEnum):
    CORPORATION = "CORPORATION"
    COUNTRY = "COUNTRY"
    DIRECT = "DIRECT"
    INDIVIDUAL = "INDIVIDUAL"
    PARTNERSHIP = "PARTNERSHIP"
    SOLE_PROPRIETORSHIP = "SOLE_PROPRIETORSHIP"

    def __str__(self) -> str:
        return str(self.value)
