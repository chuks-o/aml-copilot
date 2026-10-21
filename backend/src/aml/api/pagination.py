"""Opaque keyset cursors: where the next page starts, bound to the filters it was issued for.

A cursor is ``base64url(JSON{"v": 1, "ts": …, "id": …, "f": <filter hash>})``, unpadded. It is
not signed: tampering can only move the start position within the caller's own query, and
there is no permission boundary to cross. Rationale: docs/decisions/0024-account-pagination.md.
"""

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

VERSION = 1


class CursorError(ValueError):
    """The cursor is malformed, from another version, or was issued for other filters."""


@dataclass(frozen=True)
class Position:
    """The last row of a page; the next page starts strictly after it in (ts, id) order."""

    ts: datetime
    id: int


def filter_hash(**filters: datetime | str | None) -> str:
    """Stable digest of the filters that define a result set (not the page size)."""
    canonical = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in filters.items()}
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def encode(position: Position, filters: str) -> str:
    body = {"v": VERSION, "ts": position.ts.isoformat(), "id": position.id, "f": filters}
    raw = json.dumps(body, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode(cursor: str, filters: str) -> Position:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        body = json.loads(raw)
        if not isinstance(body, dict) or body.get("v") != VERSION:
            raise CursorError("unsupported cursor version")
        if body.get("f") != filters:
            raise CursorError("cursor was issued for a different account or time window")
        ts = datetime.fromisoformat(body["ts"])
        row_id = body["id"]
    except CursorError:
        raise
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise CursorError("malformed cursor") from exc
    if ts.tzinfo is None or not isinstance(row_id, int) or isinstance(row_id, bool) or row_id < 1:
        raise CursorError("malformed cursor")
    return Position(ts=ts, id=row_id)
