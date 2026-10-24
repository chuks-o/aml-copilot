# Generated from openapi.yaml by datamodel-codegen (make codegen). Do not edit.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

type Uuid = Annotated[UUID, Field(examples=["0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b"])]


type AccountId = Annotated[
    str,
    Field(
        description='`"<bank>:<account>"`. The bank code has no leading zeros; the account number is\nupper-case hex.\n',
        examples=["10:8000EBD30"],
        max_length=64,
        pattern="^(0|[1-9][0-9]*):[0-9A-F]+$",
    ),
]


type TransactionId = Annotated[int, Field(examples=[1048576], ge=1)]


type Timestamp = Annotated[AwareDatetime, Field(examples=["2022-09-01T00:20:00Z"])]


type Currency = Annotated[
    str,
    Field(
        description="ISO 4217 code, or `BTC` for Bitcoin.", examples=["USD"], pattern="^[A-Z]{3}$"
    ),
]


class Money(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    amount: Annotated[
        str,
        Field(
            description="Non-negative decimal, at most 8 fractional digits. Never a JSON number.",
            examples=["3697.34"],
            pattern="^(0|[1-9][0-9]{0,17})(\\.[0-9]{1,8})?$",
        ),
    ]
    currency: Currency


class Typology(StrEnum):
    FAN_IN = "FAN_IN"
    FAN_OUT = "FAN_OUT"
    CYCLE = "CYCLE"
    BIPARTITE = "BIPARTITE"
    STACK = "STACK"
    SCATTER_GATHER = "SCATTER_GATHER"
    GATHER_SCATTER = "GATHER_SCATTER"
    RANDOM = "RANDOM"


class Problem(BaseModel):
    type: Annotated[
        str,
        Field(
            description="Identifies the problem type. `about:blank` when only `status` matters.",
            examples=["https://aml-copilot.local/problems/invalid-transition"],
        ),
    ]
    title: Annotated[
        str,
        Field(
            description="Short, human-readable summary of the problem type.",
            examples=["Invalid status transition"],
        ),
    ]
    status: Annotated[int, Field(examples=[409], ge=400, le=599)]
    detail: Annotated[
        str | None,
        Field(
            description="Explanation specific to this occurrence.",
            examples=["Case is CLOSED; CLOSED is final."],
        ),
    ] = None
    instance: Annotated[
        str | None,
        Field(
            description="The request path that produced the problem.",
            examples=["/cases/0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b/status"],
        ),
    ] = None


class Error(BaseModel):
    location: Annotated[
        str,
        Field(
            description="JSON Pointer into the request, prefixed by its part.",
            examples=["/body/alert_ids/0"],
        ),
    ]
    message: Annotated[str, Field(examples=["not a valid UUID"])]


class ValidationProblem(Problem):
    errors: Annotated[list[Error] | None, Field(description="One entry per invalid field.")] = None


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    IN_CASE = "IN_CASE"
    DISMISSED = "DISMISSED"


class AlertFields(BaseModel):
    account_id: AccountId
    score: Annotated[
        float,
        Field(
            description="Model score; higher is more suspicious.", examples=[0.93], ge=0.0, le=1.0
        ),
    ]
    typology: Annotated[
        Typology | None, Field(description="The model's guess at the pattern, if it makes one.")
    ] = None
    reason: Annotated[
        str,
        Field(
            description="Why the model raised the alert, in a sentence.",
            examples=["Received from 14 accounts within 6 hours, then sent out within 2 hours."],
            max_length=2000,
            min_length=1,
        ),
    ]
    transaction_ids: Annotated[
        set[TransactionId],
        Field(
            description="The transactions that triggered the alert.", max_length=500, min_length=1
        ),
    ]
    model_version: Annotated[str, Field(examples=["gbm-2026-10-01"], max_length=64, min_length=1)]


class Alert(AlertFields):
    id: Uuid
    triggered_at: Annotated[
        Timestamp,
        Field(
            description="Dataset time of the latest cited transaction: when the alert would have fired in\nproduction. Labels and the dev/test split are defined on it (decision 0029).\n"
        ),
    ]
    window_start: Annotated[Timestamp, Field(description="The earliest cited transaction.")]
    window_end: Annotated[
        Timestamp, Field(description="One minute after the latest cited transaction (exclusive).")
    ]
    status: AlertStatus
    case_id: Annotated[
        Uuid | None, Field(description="The case this alert belongs to, once `IN_CASE`.")
    ]
    created_at: Timestamp
    typology: Annotated[
        Typology | None, Field(description="The model's guess at the pattern, if it makes one.")
    ]


class EntityType(StrEnum):
    CORPORATION = "CORPORATION"
    PARTNERSHIP = "PARTNERSHIP"
    SOLE_PROPRIETORSHIP = "SOLE_PROPRIETORSHIP"
    INDIVIDUAL = "INDIVIDUAL"
    COUNTRY = "COUNTRY"
    DIRECT = "DIRECT"


type Country = Annotated[
    str, Field(description="ISO 3166-1 alpha-2.", examples=["NG"], pattern="^[A-Z]{2}$")
]


class KycProfile(BaseModel):
    country: Annotated[Country | None, Field(description="ISO 3166-1 alpha-2.")]
    business_type: str | None
    expected_monthly_volume_band: Annotated[
        str | None, Field(description="The declared monthly volume, as a band of amounts.")
    ]
    onboarded_at: date | None
    synthetic: Annotated[
        list[str],
        Field(
            description="The fields above that are generated rather than taken from the dataset."
        ),
    ]


class ActivitySummary(BaseModel):
    first_seen: Annotated[
        Timestamp | None, Field(description="First transaction, or `null` if the account has none.")
    ]
    last_seen: Timestamp | None
    sent_count: Annotated[int, Field(ge=0)]
    received_count: Annotated[int, Field(ge=0)]


class PaymentFormat(StrEnum):
    ACH = "ACH"
    BITCOIN = "BITCOIN"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    CREDIT_CARD = "CREDIT_CARD"
    REINVESTMENT = "REINVESTMENT"
    WIRE = "WIRE"


class Direction(StrEnum):
    IN = "IN"
    OUT = "OUT"
    SELF = "SELF"


class Transaction(BaseModel):
    id: TransactionId
    ts: Timestamp
    from_account_id: AccountId
    to_account_id: AccountId
    direction: Direction
    amount_paid: Money
    amount_received: Money
    payment_format: PaymentFormat


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    COMPLETE = "COMPLETE"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class Outcome(StrEnum):
    ESCALATE = "ESCALATE"
    CLOSE = "CLOSE"


class Recommendation(BaseModel):
    outcome: Outcome
    summary: Annotated[
        str,
        Field(
            examples=["Funds from 14 unrelated accounts consolidated and forwarded within 8 hours."]
        ),
    ]
    created_at: Timestamp


class CaseCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    account_id: AccountId
    alert_ids: Annotated[set[Uuid], Field(max_length=100, min_length=1)]


class CaseStatusChange(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: CaseStatus
    reason: Annotated[
        str | None, Field(description="Optional note stored with the transition.", max_length=2000)
    ] = None


type DecisionReason = Annotated[
    str,
    Field(
        description="Required, for the audit trail.",
        examples=["Counterparties are payroll accounts of the same employer; pattern is benign."],
        max_length=4000,
        min_length=1,
    ),
]


type AnalystId = Annotated[
    str,
    Field(
        description="Who decided. Supplied by the caller until authentication exists.",
        examples=["analyst-07"],
        max_length=128,
        min_length=1,
    ),
]


class Action(StrEnum):
    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"


class Decision(BaseModel):
    id: Uuid
    case_id: Uuid
    action: Action
    outcome: Outcome
    reason: DecisionReason
    analyst_id: AnalystId
    created_at: Timestamp


type PageLimit = Annotated[int, Field(ge=1, le=500)]


type TransactionLimit = Annotated[int, Field(ge=1, le=500)]


type Cursor = Annotated[str, Field(max_length=512, min_length=1)]


type WindowHours = Annotated[int, Field(ge=1, le=8760)]


type CounterpartyLimit = Annotated[int, Field(ge=1, le=500)]


type IdempotencyKeyValue = Annotated[str, Field(max_length=255, min_length=1)]


type ETagValue = Annotated[
    str,
    Field(
        description='A strong ETag holding a case version, e.g. `"3"`.', pattern='^"[1-9][0-9]*"$'
    ),
]


class EdgeDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"


type NextCursor = Annotated[
    str | None, Field(description="Pass as `cursor` for the next page; `null` on the last page.")
]


type TotalEstimate = Annotated[
    int,
    Field(
        description="Approximate count of matching items across all pages. Not exact; don't page by it.",
        ge=0,
    ),
]


class AlertCreate(AlertFields):
    model_config = ConfigDict(
        extra="forbid",
    )


class AlertPage(BaseModel):
    items: list[Alert]
    next_cursor: NextCursor
    total_estimate: TotalEstimate


class Account(BaseModel):
    id: AccountId
    bank_id: Annotated[str, Field(examples=["10"], pattern="^(0|[1-9][0-9]*)$")]
    bank_name: Annotated[str, Field(examples=["Canada Bank #27"])]
    account_number: Annotated[str, Field(examples=["8000EBD30"], pattern="^[0-9A-F]+$")]
    entity_id: Annotated[
        str,
        Field(
            description="The account holder. One entity can hold accounts at several banks.",
            examples=["800C998A0"],
        ),
    ]
    entity_name: Annotated[str, Field(examples=["Corporation #33520"])]
    entity_type: EntityType
    activity: ActivitySummary
    kyc: KycProfile


class TransactionPage(BaseModel):
    items: list[Transaction]
    next_cursor: NextCursor
    total: Annotated[
        int,
        Field(
            description="Transactions in the window, across all pages. Exact unless `total_is_estimate`.\n",
            ge=0,
        ),
    ]
    total_is_estimate: Annotated[
        bool,
        Field(
            description="True when the window holds more than 10,000 transactions and `total` is the\nplanner's estimate (at least 10,001) instead of an exact count.\n"
        ),
    ]


class CounterpartyEdge(BaseModel):
    counterparty_id: AccountId
    direction: EdgeDirection
    transaction_count: Annotated[int, Field(ge=1)]
    total: Money
    first_ts: Timestamp
    last_ts: Timestamp


class CounterpartyList(BaseModel):
    account_id: AccountId
    window_start: Timestamp
    window_end: Timestamp
    items: list[CounterpartyEdge]
    total_edges: Annotated[
        int,
        Field(
            description="Edges in the window before `limit`; more than `items` means truncated.",
            ge=0,
        ),
    ]


class Case(BaseModel):
    id: Uuid
    version: Annotated[
        int,
        Field(description="Goes up by one on every change. Sent as `ETag`.", examples=[3], ge=1),
    ]
    status: CaseStatus
    typology: Annotated[
        Typology | None, Field(description="Assigned during the investigation; `null` until then.")
    ]
    account_id: AccountId
    alert_ids: Annotated[list[Uuid], Field(min_length=1)]
    recommendation: Recommendation | None
    decision: Annotated[
        Decision | None, Field(description="The analyst's decision, once recorded.")
    ]
    created_at: Timestamp
    updated_at: Timestamp


class CasePage(BaseModel):
    items: list[Case]
    next_cursor: NextCursor
    total_estimate: TotalEstimate


class ApproveDecision(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    action: Literal["APPROVE"]
    reason: DecisionReason
    analyst_id: AnalystId


class OverrideDecision(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    action: Literal["OVERRIDE"]
    outcome: Outcome
    reason: DecisionReason
    analyst_id: AnalystId


type DecisionCreate = Annotated[
    ApproveDecision | OverrideDecision,
    Field(
        description="`APPROVE` takes the recommendation's outcome; `OVERRIDE` states a different one.",
        discriminator="action",
    ),
]
