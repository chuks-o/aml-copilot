"""KYC profiles: the dataset's real fields plus deterministic synthetic ones (Faker, seed 42).

HI-Small has bank and entity for every account but no business type, country, expected
activity or onboarding date. Those four are generated, and every profile lists them under
``"synthetic"`` so nothing downstream presents them as fact. Rationale: docs/decisions/0023.

Determinism: each account gets its own Faker seed, ``sha256("42:<account id>")``, so its profile
depends only on its id: not on the order accounts are processed in, how many there are, or
the process (Python's ``hash()`` is randomised per process; sha256 isn't). Faker is pinned in
uv.lock because providers can change output between releases.
"""

import hashlib
from datetime import datetime, timedelta
from functools import cache
from typing import Any

from faker import Faker

SEED = 42
INCONSISTENT_SHARE = 10  # percent of accounts whose expected volume contradicts their activity
SYNTHETIC_FIELDS = ("business_type", "country", "expected_monthly_volume_band", "onboarded_at")

# Expected monthly transaction count (sent + received), lowest band first.
VOLUME_BANDS = ("<10", "10-99", "100-999", "1000-9999", "10000+")
_BAND_FLOORS = (0, 10, 100, 1_000, 10_000)

BUSINESS_TYPES = {
    "CORPORATION": (
        "Manufacturing",
        "Wholesale trade",
        "Software",
        "Logistics",
        "Real estate",
        "Import/export",
        "Construction",
    ),
    "PARTNERSHIP": ("Law firm", "Accounting practice", "Consultancy", "Medical practice"),
    "SOLE_PROPRIETORSHIP": ("Retail shop", "Restaurant", "Freelance services", "Car repair"),
    "INDIVIDUAL": ("Personal account",),
    "COUNTRY": ("Government entity",),
    "DIRECT": ("Unspecified",),
}


def _digest(*parts: object) -> int:
    text = ":".join(str(p) for p in (SEED, *parts))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def is_inconsistent(account_id: str) -> bool:
    """The deliberately inconsistent 10%: chosen by id hash alone, never by label, so the
    inconsistency can't leak the laundering label into features."""
    return _digest("inconsistent", account_id) % 100 < INCONSISTENT_SHARE


def band_index(monthly_transactions: float) -> int:
    return max(i for i, floor in enumerate(_BAND_FLOORS) if monthly_transactions >= floor)


@cache
def _faker() -> Faker:
    return Faker()  # one instance, re-seeded per account (constructing one is slow)


def profile(
    account_id: str,
    *,
    entity_type: str,
    real: dict[str, str],
    monthly_transactions: float,
    first_seen: datetime,
) -> dict[str, Any]:
    """The kyc_profile JSON for one account."""
    fake = _faker()
    fake.seed_instance(_digest(account_id))
    actual = band_index(monthly_transactions)
    if is_inconsistent(account_id):
        far = [i for i in range(len(VOLUME_BANDS)) if abs(i - actual) >= 2]
        band = fake.random_element(far)
    else:
        # Loosely consistent: usually the actual band, sometimes a neighbour.
        near = [actual] * 3 + [i for i in (actual - 1, actual + 1) if 0 <= i < len(VOLUME_BANDS)]
        band = fake.random_element(near)
    onboarded = first_seen - timedelta(days=fake.random_int(30, 3650))
    return {
        **real,
        "business_type": fake.random_element(BUSINESS_TYPES[entity_type]),
        "country": fake.country_code(),
        "expected_monthly_volume_band": VOLUME_BANDS[band],
        "onboarded_at": onboarded.date().isoformat(),
        "synthetic": list(SYNTHETIC_FIELDS),
        "kyc_seed": SEED,
    }
