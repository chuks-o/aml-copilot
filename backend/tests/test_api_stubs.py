"""Stub behaviour the contract test only reaches by chance: success paths and state rules."""

from fastapi.testclient import TestClient

from aml.api.app import app

client = TestClient(app)
CASE = "0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b"
V1 = {"If-Match": '"1"'}
KEY = {"Idempotency-Key": "k-1"}
DECISION = {"reason": "Checked counterparties.", "analyst_id": "analyst-07"}


def test_patch_moves_an_open_case_to_investigating_and_bumps_the_version() -> None:
    r = client.patch(f"/cases/{CASE}/status", json={"status": "INVESTIGATING"}, headers=V1)

    assert (r.status_code, r.json()["status"], r.json()["version"]) == (200, "INVESTIGATING", 2)
    assert r.headers["etag"] == '"2"'


def test_patch_cannot_reach_a_final_status() -> None:
    r = client.patch(f"/cases/{CASE}/status", json={"status": "CLOSED"}, headers=V1)

    assert (r.status_code, r.headers["content-type"]) == (409, "application/problem+json")


def test_stale_and_missing_if_match() -> None:
    body = {"status": "INVESTIGATING"}

    assert (
        client.patch(f"/cases/{CASE}/status", json=body, headers={"If-Match": '"7"'}).status_code
        == 412
    )
    assert client.patch(f"/cases/{CASE}/status", json=body).status_code == 428
    assert (
        client.patch(f"/cases/{CASE}/status", json=body, headers={"If-Match": "1"}).status_code
        == 400
    )


def test_approve_applies_the_recommendation() -> None:
    r = client.post(
        f"/cases/{CASE}/decisions", json={"action": "APPROVE", **DECISION}, headers={**V1, **KEY}
    )

    assert (r.status_code, r.json()["status"], r.json()["decision"]["outcome"]) == (
        200,
        "ESCALATED",
        "ESCALATE",
    )


def test_override_must_differ_from_the_recommendation() -> None:
    url = f"/cases/{CASE}/decisions"
    close = {"action": "OVERRIDE", "outcome": "CLOSE", **DECISION}
    same = {"action": "OVERRIDE", "outcome": "ESCALATE", **DECISION}

    assert client.post(url, json=close, headers={**V1, **KEY}).json()["status"] == "CLOSED"
    assert client.post(url, json=same, headers={**V1, **KEY}).status_code == 409


def test_create_requires_an_idempotency_key_and_reuses_ids_for_the_same_key() -> None:
    body = {"account_id": "10:8000EBD30", "alert_ids": [CASE]}

    assert client.post("/cases", json=body).status_code == 400
    first, again = (client.post("/cases", json=body, headers=KEY) for _ in range(2))
    assert first.status_code == 201
    assert first.json()["id"] == again.json()["id"]
    assert first.headers["location"] == f"/cases/{first.json()['id']}"


def test_validation_errors_are_problem_json_with_pointers() -> None:
    r = client.get("/alerts", params={"limit": 501})

    assert (r.status_code, r.headers["content-type"]) == (422, "application/problem+json")
    assert r.json()["errors"] == [
        {"location": "/query/limit", "message": "Input should be less than or equal to 500"}
    ]


def test_bad_path_ids_are_400_with_an_encoded_instance() -> None:
    r = client.get("/accounts/%C2%84")

    assert r.status_code == 400
    assert r.json()["instance"] == "/accounts/%C2%84"
