from enum import StrEnum


class PaymentFormat(StrEnum):
    ACH = "ACH"
    BITCOIN = "BITCOIN"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    CREDIT_CARD = "CREDIT_CARD"
    REINVESTMENT = "REINVESTMENT"
    WIRE = "WIRE"

    def __str__(self) -> str:
        return str(self.value)
