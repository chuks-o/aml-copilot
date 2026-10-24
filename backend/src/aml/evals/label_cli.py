"""The golden-set labelling screen (``aml golden-label``): Rich, in the terminal.

For each sampled alert it shows the alert and the rule that fired, the account's KYC profile, a
counterparty summary for the 72 h up to the alert, and a paginated table of the account's
transactions **up to the alert** (what an analyst would have had; nothing later). It records a
decision, a typology, 3 to 8 key transactions, a note and the time spent, one JSON line per
alert (``aml.evals.golden``). Quit any time; the next run starts at the first unlabelled alert.

Everything shown comes through the Cases API, which never exposes ground truth (0014): no
stratum, label or laundering flag can reach the screen. Rationale: decision 0032.
"""

import math
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from aml.clients import Client, cases_api_client
from aml.clients.cases_api.api.accounts import (
    get_account,
    list_account_counterparties,
    list_account_transactions,
)
from aml.clients.cases_api.api.alerts import get_alert
from aml.clients.cases_api.models import (
    Account,
    Alert,
    CounterpartyList,
    Transaction,
    TransactionPage,
)
from aml.clients.cases_api.types import UNSET, Unset
from aml.evals import golden, labels

PAGE_ROWS = 20
COUNTERPARTY_HOURS = int(labels.LABEL_WINDOW.total_seconds() // 3600)
HELP = (
    "[n]ext / [p]rev page · [g N] go to page · [e]scalate · [c]lose · [s]kip for now · "
    "[z] pause the clock · [q]uit"
)


class Source(Protocol):
    """What the screen reads. ``ApiSource`` in use; a fake in the tests."""

    def alert(self, alert_id: UUID) -> Alert: ...

    def account(self, account_id: str) -> Account: ...

    def transactions(self, account_id: str, end: datetime) -> list[Transaction]: ...

    def counterparties(self, account_id: str, as_of: datetime) -> CounterpartyList: ...


class ApiSource:
    """The Cases API through the generated client."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or cases_api_client()

    def alert(self, alert_id: UUID) -> Alert:
        return _ok(get_alert.sync(alert_id, client=self._client), Alert, f"alert {alert_id}")

    def account(self, account_id: str) -> Account:
        found = get_account.sync(account_id, client=self._client)
        return _ok(found, Account, f"account {account_id}")

    def transactions(self, account_id: str, end: datetime) -> list[Transaction]:
        rows: list[Transaction] = []
        cursor: str | Unset = UNSET
        while True:
            found = list_account_transactions.sync(
                account_id, client=self._client, to=end, limit=500, cursor=cursor
            )
            page = _ok(found, TransactionPage, f"transactions of {account_id}")
            rows.extend(page.items)
            if not page.next_cursor:
                return rows
            cursor = page.next_cursor

    def counterparties(self, account_id: str, as_of: datetime) -> CounterpartyList:
        found = list_account_counterparties.sync(
            account_id,
            client=self._client,
            window_hours=COUNTERPARTY_HOURS,
            as_of=as_of,
            limit=25,
        )
        return _ok(found, CounterpartyList, f"counterparties of {account_id}")


def _ok[T](found: object, kind: type[T], what: str) -> T:
    if isinstance(found, kind):
        return found
    raise golden.GoldenError(f"{what}: {_detail(found)}")


def _detail(problem: object) -> str:
    return str(getattr(problem, "detail", None) or getattr(problem, "title", None) or problem)


@dataclass
class Clock:
    """Seconds an alert is on screen, minus pauses."""

    now: Callable[[], float] = time.monotonic
    _started: float = field(default=0.0, init=False)
    _paused: float = field(default=0.0, init=False)

    def start(self) -> None:
        self._started, self._paused = self.now(), 0.0

    def pause(self, wait: Callable[[], object]) -> None:
        stopped = self.now()
        wait()
        self._paused += self.now() - stopped

    def seconds(self) -> float:
        return round(self.now() - self._started - self._paused, 1)


@dataclass
class View:
    alert: Alert
    account: Account
    transactions: list[Transaction]
    counterparties: CounterpartyList
    page: int = 0

    @property
    def pages(self) -> int:
        return max(1, math.ceil(len(self.transactions) / PAGE_ROWS))

    @property
    def visible_ids(self) -> set[int]:
        return {t.id for t in self.transactions}


def load_view(source: Source, alert_id: UUID) -> View:
    alert = source.alert(alert_id)
    rows = source.transactions(alert.account_id, alert.window_end)
    view = View(
        alert=alert,
        account=source.account(alert.account_id),
        transactions=rows,
        counterparties=source.counterparties(alert.account_id, alert.window_end),
    )
    cited = [n for n, t in enumerate(rows) if t.id in set(alert.transaction_ids)]
    view.page = cited[0] // PAGE_ROWS if cited else view.pages - 1  # open at the evidence
    return view


# --------------------------------------------------------------------------- rendering


def _ts(value: datetime | None) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M") if value else "-"


def alert_panel(alert: Alert) -> Panel:
    cited = sorted(alert.transaction_ids)
    shown = ", ".join(map(str, cited[:12])) + (
        f" … (+{len(cited) - 12})" if len(cited) > 12 else ""
    )
    guess = alert.typology.value if alert.typology else "none"
    body = (
        f"[bold]{alert.model_version}[/]  score {alert.score:.2f}  rule's typology guess: {guess}\n"
        f"{alert.reason}\n"
        f"triggered {_ts(alert.triggered_at)} UTC · window {_ts(alert.window_start)} .. "
        f"{_ts(alert.window_end)}\n"
        f"cited ({len(cited)}): {shown}"
    )
    return Panel(body, title=f"Alert {alert.id}", title_align="left")


def kyc_panel(account: Account, transactions: Sequence[Transaction]) -> Panel:
    kyc = account.kyc
    synthetic = set(kyc.synthetic)

    def field_(name: str, value: object) -> str:
        mark = " [dim](synthetic)[/]" if name in synthetic else ""
        return f"{value if value is not None else '-'}{mark}"

    moves = Counter(t.direction.value for t in transactions)
    body = (
        f"[bold]{account.entity_name}[/] ({account.entity_type.value}) · {account.bank_name} · "
        f"account {account.id}\n"
        f"country {field_('country', kyc.country)} · business "
        f"{field_('business_type', kyc.business_type)} · expected monthly volume "
        f"{field_('expected_monthly_volume_band', kyc.expected_monthly_volume_band)} · "
        f"onboarded {field_('onboarded_at', kyc.onboarded_at)}\n"
        f"up to the alert: {len(transactions)} transactions ({moves['OUT']} sent, "
        f"{moves['IN']} received, {moves['SELF']} to itself), "
        f"first {_ts(account.activity.first_seen)}"
    )
    return Panel(body, title="KYC profile", title_align="left")


def counterparty_table(counterparties: CounterpartyList) -> Table:
    table = Table(
        title=f"Counterparties, {COUNTERPARTY_HOURS} h up to the alert "
        f"({counterparties.total_edges} edges)",
        title_justify="left",
    )
    for column in ("counterparty", "dir", "txs", "total", "first", "last"):
        table.add_column(column, justify="right" if column in ("txs", "total") else "left")
    for e in counterparties.items:
        table.add_row(
            e.counterparty_id,
            e.direction.value,
            str(e.transaction_count),
            f"{e.total.amount} {e.total.currency}",
            _ts(e.first_ts),
            _ts(e.last_ts),
        )
    return table


def transaction_table(view: View) -> Table:
    cited = set(view.alert.transaction_ids)
    start = view.page * PAGE_ROWS
    table = Table(
        title=f"Transactions up to the alert · page {view.page + 1}/{view.pages} · "
        f"* = cited by the rule",
        title_justify="left",
    )
    for column in ("", "id", "ts (UTC)", "dir", "counterparty", "paid", "received", "format"):
        table.add_column(column, justify="right" if column in ("paid", "received") else "left")
    for t in view.transactions[start : start + PAGE_ROWS]:
        other = t.to_account_id if t.from_account_id == view.account.id else t.from_account_id
        table.add_row(
            "*" if t.id in cited else "",
            str(t.id),
            _ts(t.ts),
            t.direction.value,
            other,
            f"{t.amount_paid.amount} {t.amount_paid.currency}",
            f"{t.amount_received.amount} {t.amount_received.currency}",
            t.payment_format.value,
        )
    return table


def screen(view: View) -> Group:
    return Group(
        alert_panel(view.alert),
        kyc_panel(view.account, view.transactions),
        counterparty_table(view.counterparties),
        transaction_table(view),
    )


# ----------------------------------------------------------------------------- session


def parse_ids(text: str) -> list[int] | None:
    parts = text.replace(",", " ").split()
    try:
        return [int(p) for p in parts]
    except ValueError:
        return None


@dataclass
class Session:
    source: Source
    console: Console
    read: Callable[[str], str]
    labeller: str
    sample_path: Path = golden.SAMPLE_FILE
    labels_path: Path = golden.LABELS_FILE
    clock: Clock = field(default_factory=Clock)
    wall: Callable[[], datetime] = lambda: datetime.now(UTC)

    def run(self, revise: UUID | None = None) -> int:
        """Label until the queue is empty or the labeller quits; returns how many were saved."""
        sample = golden.load_sample(self.sample_path)
        if revise is not None and revise not in sample:
            raise golden.GoldenError(f"{revise} is not in the golden sample")
        saved = 0
        queue = [revise] if revise else self._unlabelled(sample)
        skipped: list[UUID] = []
        while queue or skipped:
            if not queue:  # skipped alerts come back once the rest are done
                queue, skipped = skipped, []
            alert_id = queue.pop(0)
            outcome = self._label(alert_id, len(sample), revise is not None)
            if outcome == "quit":
                break
            if outcome == "skip":
                skipped.append(alert_id)
            else:
                saved += 1
            if revise:
                break
        done = len(golden.load_labels(self.labels_path))
        self.console.print(f"Saved {saved} this session; {done} of {len(sample)} labelled.")
        return saved

    def _unlabelled(self, sample: Sequence[UUID]) -> list[UUID]:
        done = golden.load_labels(self.labels_path)
        return [a for a in sample if a not in done]

    def _label(self, alert_id: UUID, total: int, revising: bool) -> str:
        view = load_view(self.source, alert_id)
        done = len(golden.load_labels(self.labels_path))
        self.clock.start()
        while True:
            self.console.rule(f"{done} of {total} labelled" + (" · revising" if revising else ""))
            self.console.print(screen(view))
            self.console.print(escape(HELP), style="dim")
            command = self.read("> ").strip().lower()
            if command in ("n", ""):
                view.page = min(view.page + 1, view.pages - 1)
            elif command == "p":
                view.page = max(view.page - 1, 0)
            elif command.startswith("g"):
                number = command[1:].strip()
                if number.isdigit() and 1 <= int(number) <= view.pages:
                    view.page = int(number) - 1
            elif command == "z":
                self.clock.pause(lambda: self.read("Paused. Press Enter to resume. "))
            elif command == "s":
                return "skip"
            elif command == "q":
                return "quit"
            elif command in ("e", "c"):
                if self._record(view, "ESCALATE" if command == "e" else "CLOSE", revising):
                    return "saved"
            else:
                self.console.print(f"Unknown command {command!r}.")

    def _record(self, view: View, decision: str, revising: bool) -> bool:
        """Ask for the label's fields; False (back to the screen) on an empty answer."""
        typology: str | None = None
        if decision == "ESCALATE":
            choices = " ".join(f"{n}={t}" for n, t in enumerate(golden.TYPOLOGIES, 1))
            answer = self.read(f"Typology ({choices}; Enter to go back): ").strip().upper()
            if not answer:
                return False
            typology = (
                golden.TYPOLOGIES[int(answer) - 1]
                if answer.isdigit() and 1 <= int(answer) <= len(golden.TYPOLOGIES)
                else answer
            )
        answer = self.read("Key transaction ids, 3 to 8 (Enter to go back): ")
        if not answer.strip():
            return False
        key_ids = parse_ids(answer)
        if key_ids is None:
            self.console.print("[red]Transaction ids are numbers.[/]")
            return False
        note = self.read("Note: ").strip()
        problems = golden.validate(decision, typology, key_ids, note, view.visible_ids)
        if problems:
            for problem in problems:
                self.console.print(f"[red]{problem}[/]")
            return False
        seconds = self.clock.seconds()
        summary = f"{decision} {typology or ''} {key_ids} ({seconds:.0f} s): {note}"
        if self.read(f"Save {summary}? [Y/n] ").strip().lower() not in ("", "y", "yes"):
            return False
        golden.append(
            golden.GoldenLabel(
                alert_id=view.alert.id,
                decision=decision,
                typology=typology,
                key_transaction_ids=key_ids,
                note=note,
                seconds=seconds,
                labeller=self.labeller,
                labelled_at=self.wall().isoformat(),
                revises=revising,
            ),
            self.labels_path,
        )
        return True
