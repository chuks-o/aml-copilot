"""The labelling screen, driven by scripted answers over a fake Cases API source."""

import io
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from rich.console import Console

from aml.clients.cases_api.models import (
    Account,
    ActivitySummary,
    Alert,
    AlertStatus,
    CounterpartyEdge,
    CounterpartyList,
    Direction,
    EdgeDirection,
    EntityType,
    KycProfile,
    Money,
    PaymentFormat,
    Transaction,
)
from aml.evals import golden, label_cli

ACCOUNT = "10:8000000A1"
OTHER = "20:8000000B2"
T = datetime(2022, 9, 3, tzinfo=UTC)
ALERTS = [UUID(int=1), UUID(int=2), UUID(int=3)]
CITED = [41, 42, 43]  # on page 3 of 3 (20 rows a page)


def _tx(n: int) -> Transaction:
    usd = Money(amount="100.00", currency="USD")
    return Transaction(
        id=n,
        ts=T + timedelta(minutes=n),
        from_account_id=OTHER,
        to_account_id=ACCOUNT,
        direction=Direction.IN,
        amount_paid=usd,
        amount_received=usd,
        payment_format=PaymentFormat.WIRE,
    )


class FakeSource:
    def __init__(self) -> None:
        self.ends: list[datetime] = []

    def alert(self, alert_id: UUID) -> Alert:
        return Alert(
            id=alert_id,
            account_id=ACCOUNT,
            score=0.75,
            reason="Received from 5 distinct senders within 24 h.",
            transaction_ids=CITED,
            model_version="rules-v2:fan_in",
            typology=None,
            triggered_at=T + timedelta(minutes=43),
            window_start=T + timedelta(minutes=41),
            window_end=T + timedelta(minutes=44),
            status=AlertStatus.OPEN,
            case_id=None,
            created_at=datetime(2026, 10, 22, tzinfo=UTC),
        )

    def account(self, account_id: str) -> Account:
        return Account(
            id=account_id,
            bank_id="10",
            bank_name="Bank #10",
            account_number="8000000A1",
            entity_id="800AAA",
            entity_name="Corporation #1",
            entity_type=EntityType.CORPORATION,
            activity=ActivitySummary(
                first_seen=T, last_seen=T + timedelta(days=5), sent_count=0, received_count=987654
            ),
            kyc=KycProfile(
                country="NG",
                business_type="Construction",
                expected_monthly_volume_band="1000-9999",
                onboarded_at=date(2018, 6, 7),
                synthetic=["business_type", "country"],
            ),
        )

    def transactions(self, account_id: str, end: datetime) -> list[Transaction]:
        self.ends.append(end)
        return [_tx(n) for n in range(1, 44)]  # 43 rows up to the alert

    def counterparties(self, account_id: str, as_of: datetime) -> CounterpartyList:
        edge = CounterpartyEdge(
            counterparty_id=OTHER,
            direction=EdgeDirection.IN,
            transaction_count=43,
            total=Money(amount="4300.00", currency="USD"),
            first_ts=T,
            last_ts=as_of,
        )
        return CounterpartyList(
            account_id=account_id,
            window_start=as_of - timedelta(hours=72),
            window_end=as_of,
            items=[edge],
            total_edges=1,
        )


class Script:
    """Answers in order; fails the test if the screen asks for more than scripted."""

    def __init__(self, answers: list[str]) -> None:
        self.answers: Iterator[str] = iter(answers)

    def __call__(self, prompt: str) -> str:
        try:
            return next(self.answers)
        except StopIteration:
            pytest.fail(f"unscripted prompt: {prompt!r}")


class FakeClock(label_cli.Clock):
    """Returns ``times`` in order, then the last one forever."""

    def __init__(self, times: list[float]) -> None:
        ticks = iter(times)
        last = [times[-1]]

        def now() -> float:
            last[0] = next(ticks, last[0])
            return last[0]

        super().__init__(now=now)


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"alerts": [{"alert_id": str(a)} for a in ALERTS]}))
    return sample, tmp_path / "golden_v1.jsonl"


def _session(
    files: tuple[Path, Path], answers: list[str], clock: label_cli.Clock | None = None
) -> tuple[label_cli.Session, io.StringIO, FakeSource]:
    out = io.StringIO()
    source = FakeSource()
    session = label_cli.Session(
        source=source,
        console=Console(file=out, width=160, color_system=None),
        read=Script(answers),
        labeller="me",
        sample_path=files[0],
        labels_path=files[1],
        clock=clock or label_cli.Clock(),
        wall=lambda: datetime(2026, 10, 24, 9, tzinfo=UTC),
    )
    return session, out, source


def test_the_screen_shows_the_alert_kyc_counterparties_and_transactions_up_to_the_alert(
    files: tuple[Path, Path],
) -> None:
    session, out, source = _session(files, ["q"])

    session.run()

    text = out.getvalue()
    assert "rules-v2:fan_in" in text and "Received from 5 distinct senders" in text
    assert "NG (synthetic)" in text and "Construction (synthetic)" in text
    assert "1000-9999" in text and "1000-9999 (synthetic)" not in text  # not in the list
    assert "Counterparties, 72 h up to the alert" in text and OTHER in text
    assert "page 3/3" in text  # opens on the page with the cited transactions
    assert "up to the alert: 43 transactions (0 sent, 43 received, 0 to itself)" in text
    assert "[e]scalate · [c]lose" in text  # the command keys survive Rich markup
    assert source.ends == [T + timedelta(minutes=44)]  # nothing after the alert is fetched
    assert "987654" not in text  # whole-history counts (including later activity) not shown


def test_pages_move_and_stop_at_the_ends(files: tuple[Path, Path]) -> None:
    session, out, _ = _session(files, ["n", "g1", "p", "g9", "q"])

    session.run()

    pages = [line for line in out.getvalue().splitlines() if "Transactions up to the alert" in line]
    assert [p.split("page ")[1].split(" ")[0] for p in pages] == ["3/3", "3/3", "1/3", "1/3", "1/3"]


def test_an_escalation_is_saved_with_the_time_on_screen_minus_pauses(
    files: tuple[Path, Path],
) -> None:
    # start 100, drawn at 105, paused 110 to 160, drawn at 165, saved at 180:
    # 80 s minus 50 paused = 30 s on screen.
    clock = FakeClock([100.0, 105.0, 110.0, 160.0, 165.0, 180.0])
    answers = ["z", "", "e", "3", "41 42, 43", "Five senders in minutes, then silence.", "y", "q"]
    session, _, _ = _session(files, answers, clock)

    assert session.run() == 1

    [line] = files[1].read_text().splitlines()
    assert json.loads(line) == {
        "alert_id": str(ALERTS[0]),
        "decision": "ESCALATE",
        "typology": "FAN_IN",
        "typology_other": None,
        "key_transaction_ids": [41, 42, 43],
        "note": "Five senders in minutes, then silence.",
        "seconds": 30.0,
        "labeller": "me",
        "labelled_at": "2026-10-24T09:00:00+00:00",
        "version": "golden_v1",
        "revises": False,
    }


def test_invalid_answers_save_nothing_and_return_to_the_screen(files: tuple[Path, Path]) -> None:
    answers = [
        "c", "41 42", "two only",  # too few key transactions
        "c", "41 42 999", "unseen id",  # 999 is not visible up to the alert
        "c", "40 41 42", "uncited",  # a CLOSE lists the rule's transactions (rule 7)
        "e", "", # Enter at the typology goes back
        "c", "41 42 43", "fine", "n",  # declined at the confirmation
        "q",
    ]  # fmt: skip
    session, out, _ = _session(files, answers)

    assert session.run() == 0
    assert not files[1].exists()
    assert "give 3 to 8 key transactions" in out.getvalue()
    assert "not among this alert's visible transactions: [999]" in out.getvalue()
    assert "a CLOSE lists only transactions the rule cited: [40]" in out.getvalue()


def test_a_session_resumes_at_the_first_unlabelled_alert_and_skips_come_back_last(
    files: tuple[Path, Path],
) -> None:
    close = ["c", "41 42 43", "ordinary payroll", "y"]
    first, _, _ = _session(files, [*close, "q"])
    first.run()

    # Alert 1 is done: the next session starts at 2, skips it, labels 3, then returns to 2.
    second, _, _ = _session(files, ["s", *close, *close])
    assert second.run() == 2

    labelled = [json.loads(line)["alert_id"] for line in files[1].read_text().splitlines()]
    assert labelled == [str(ALERTS[0]), str(ALERTS[2]), str(ALERTS[1])]


def test_revise_relabels_one_alert_and_the_new_line_wins(files: tuple[Path, Path]) -> None:
    first, _, _ = _session(files, ["c", "41 42 43", "first look", "y", "q"])
    first.run()

    again, _, _ = _session(
        files, ["e", "9", "senders paid in sequence", "1 2 41", "second look", "y"]
    )
    assert again.run(revise=ALERTS[0]) == 1

    label = golden.load_labels(files[1])[ALERTS[0]]
    assert (label.decision, label.typology, label.typology_other, label.revises) == (
        "ESCALATE",
        "OTHER",
        "senders paid in sequence",
        True,
    )


def test_revise_refuses_an_alert_outside_the_sample(files: tuple[Path, Path]) -> None:
    session, _, _ = _session(files, [])

    with pytest.raises(golden.GoldenError, match="not in the golden sample"):
        session.run(revise=UUID(int=99))


def test_after_2_minutes_on_an_alert_the_screen_says_so(files: tuple[Path, Path]) -> None:
    clock = FakeClock([0.0, 60.0, 119.0, 121.0])  # start, three redraws
    session, out, _ = _session(files, ["n", "n", "q"], clock)

    session.run()

    warnings = [line for line in out.getvalue().splitlines() if "min on this alert" in line]
    assert warnings == ["2 min on this alert: decide, or [s]kip it for now."]
