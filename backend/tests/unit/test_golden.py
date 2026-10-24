"""Golden sample quotas and determinism, label validation, and the append-only label store."""

import json
from collections import Counter
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from aml.evals import golden
from aml.evals.golden import Candidate, GoldenError, GoldenLabel

NS = UUID("0e5f3c1a-9b2d-4c6e-8f10-2a3b4c5d6e7f")
# Dev pool sizes in accounts (T17 plan): CYCLE has only 3.
LISTED_SIZES = {
    "SCATTER_GATHER": 32,
    "GATHER_SCATTER": 29,
    "FAN_IN": 23,
    "STACK": 12,
    "FAN_OUT": 12,
    "RANDOM": 11,
    "BIPARTITE": 5,
    "CYCLE": 3,
}
RULES = {"rules-v2:fan_in": 50, "rules-v2:fan_out": 10, "rules-v2:structuring": 7}


def _candidates(stratum: str, group: str, n: int) -> list[Candidate]:
    return [
        Candidate(uuid5(NS, f"{stratum}/{group}/{i}"), f"{stratum}:{group}:{i}", group)
        for i in range(n)
    ]


def _pools() -> dict[str, list[Candidate]]:
    pools: dict[str, list[Candidate]] = {
        "positive_listed": [
            c for group, n in LISTED_SIZES.items() for c in _candidates("pos", group, n)
        ],
        "positive_unlisted_non_ach": _candidates("unl", "", 38),
        # T01: four accounts with several alerts each (one account has none in dev).
        "negative_t01": [
            Candidate(uuid5(NS, f"t01/{account}/{i}"), account, account)
            for account in golden.T01_ACCOUNTS[:1] + golden.T01_ACCOUNTS[2:]
            for i in range(5)
        ],
        "negative_near_miss": _candidates("near", "", 30),
        "negative_high_score": _candidates("high", "", 30),
        "negative_ordinary": [c for rule, n in RULES.items() for c in _candidates("ord", rule, n)],
    }
    return pools


def test_listed_positives_spread_evenly_and_a_short_typology_gives_its_place_away() -> None:
    shares = golden.equal_shares(32, LISTED_SIZES)

    assert sum(shares.values()) == 32
    assert shares["CYCLE"] == 3
    assert sorted(shares.values()) == [3, 4, 4, 4, 4, 4, 4, 5]
    assert shares["SCATTER_GATHER"] == 5  # the largest pool takes the spare place


def test_equal_shares_fail_when_the_pools_are_too_small() -> None:
    with pytest.raises(GoldenError, match="only 5 of 6"):
        golden.equal_shares(6, {"A": 2, "B": 3})


def test_ordinary_negatives_follow_rule_volume() -> None:
    assert golden.proportional_shares(20, RULES) == {
        "rules-v2:fan_in": 15,
        "rules-v2:fan_out": 3,
        "rules-v2:structuring": 2,
    }


def test_the_sample_meets_every_quota() -> None:
    sample = golden.draw(_pools())
    strata = Counter(i.stratum for i in sample)

    assert len(sample) == 80
    assert strata == {
        "positive_listed": 32,
        "positive_unlisted_non_ach": 8,
        "negative_t01": 4,  # one per T01 account with dev alerts
        "negative_high_score": 8,
        "negative_near_miss": 8,  # 20 hard negatives in all
        "negative_ordinary": 20,
    }
    typologies = Counter(i.group for i in sample if i.stratum == "positive_listed")
    assert len(typologies) >= 6
    assert typologies["CYCLE"] == 3
    assert len({i.account_id for i in sample}) == 80  # at most one alert per account
    assert {i.account_id for i in sample if i.stratum == "negative_t01"} == set(
        golden.T01_ACCOUNTS
    ) - {"4726:808FAF7C0"}


def test_the_draw_is_fixed_by_the_seed_not_by_row_order() -> None:
    pools = _pools()
    reversed_pools = {stratum: list(reversed(cs)) for stratum, cs in pools.items()}

    first = golden.draw(pools)
    assert golden.draw(reversed_pools) == first
    assert golden.draw(pools, seed=18) != first


def test_strata_are_mixed_in_labelling_order() -> None:
    order = [i.stratum.startswith("positive") for i in golden.draw(_pools())]

    assert order != sorted(order) and order != sorted(order, reverse=True)


def test_a_short_stratum_stops_the_draw() -> None:
    pools = _pools()
    pools["positive_unlisted_non_ach"] = pools["positive_unlisted_non_ach"][:5]

    with pytest.raises(GoldenError, match="positive_unlisted_non_ach: 5 of 8"):
        golden.draw(pools)


def test_one_alert_per_account_across_strata() -> None:
    pools = _pools()
    # A near-miss candidate on an account already taken as a high score is passed over.
    shared = pools["negative_high_score"]
    pools["negative_near_miss"] = [
        Candidate(uuid5(NS, f"dup/{c.alert_id}"), c.account_id, "") for c in shared
    ] + pools["negative_near_miss"]

    sample = golden.draw(pools)
    assert len({i.account_id for i in sample}) == len(sample) == 80


def test_the_sample_file_keeps_order_seed_and_source_hash(tmp_path: Path) -> None:
    sample = golden.draw(_pools())
    document = golden.sample_document(sample, "ab" * 32)
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(document))

    assert golden.load_sample(path) == [i.alert_id for i in sample]
    assert (document["seed"], document["splits_sha256"]) == (golden.SEED, "ab" * 32)
    assert document["t01_without_dev_alerts"] == ["4726:808FAF7C0"]
    assert sum(document["counts"].values()) == 80


VISIBLE = {1, 2, 3, 4, 5, 6, 7, 8, 9}


@pytest.mark.parametrize(
    ("decision", "typology", "ids", "note", "problem"),
    [
        ("ESCALATE", "FAN_IN", [1, 2, 3], "ok", None),
        ("CLOSE", None, [1, 2, 3, 4, 5, 6, 7, 8], "ok", None),
        ("ESCALATE", "UNLISTED", [1, 2, 3], "ok", None),
        ("MAYBE", None, [1, 2, 3], "ok", "decision must be one of"),
        ("ESCALATE", None, [1, 2, 3], "ok", "needs a typology"),
        ("ESCALATE", "FAN-IN", [1, 2, 3], "ok", "needs a typology"),
        ("CLOSE", "FAN_IN", [1, 2, 3], "ok", "a CLOSE has no typology"),
        ("CLOSE", None, [1, 2], "ok", "give 3 to 8"),
        ("CLOSE", None, [1, 2, 3, 4, 5, 6, 7, 8, 9], "ok", "give 3 to 8"),
        ("CLOSE", None, [1, 1, 2, 3], "ok", "listed twice"),
        ("CLOSE", None, [1, 2, 99], "ok", "not among this alert's visible transactions: [99]"),
        ("CLOSE", None, [1, 2, 3], "  ", "write a short note"),
        ("CLOSE", None, [1, 2, 3], "x" * 501, "under 500"),
    ],
)
def test_validation(
    decision: str, typology: str | None, ids: list[int], note: str, problem: str | None
) -> None:
    problems = golden.validate(decision, typology, ids, note, VISIBLE)

    if problem is None:
        assert problems == []
    else:
        assert any(problem in p for p in problems), problems


def _label(alert: int, decision: str = "CLOSE", **changes: object) -> GoldenLabel:
    fields: dict[str, object] = {
        "alert_id": UUID(int=alert),
        "decision": decision,
        "typology": None,
        "key_transaction_ids": [1, 2, 3],
        "note": "n",
        "seconds": 12.5,
        "labeller": "me",
        "labelled_at": "2026-10-24T09:00:00+00:00",
    }
    return GoldenLabel(**(fields | changes))  # type: ignore[arg-type]


def test_labels_append_and_the_last_line_per_alert_wins(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    golden.append(_label(1), path)
    golden.append(_label(2), path)
    golden.append(_label(1, "ESCALATE", typology="STACK", revises=True), path)

    loaded = golden.load_labels(path)
    assert set(loaded) == {UUID(int=1), UUID(int=2)}
    assert (loaded[UUID(int=1)].decision, loaded[UUID(int=1)].typology) == ("ESCALATE", "STACK")
    assert len(path.read_text().splitlines()) == 3  # nothing rewritten


def test_a_torn_last_line_is_ignored_but_a_torn_middle_line_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    golden.append(_label(1), path)
    with path.open("a") as f:
        f.write('{"alert_id": "00000000-')  # the crash happened mid-write

    assert set(golden.load_labels(path)) == {UUID(int=1)}

    path.write_text(path.read_text() + "\n" + _label(2).to_json() + "\n")
    with pytest.raises(GoldenError, match=":2 is not valid JSON"):
        golden.load_labels(path)


def test_no_labels_yet(tmp_path: Path) -> None:
    assert golden.load_labels(tmp_path / "missing.jsonl") == {}
