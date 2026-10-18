"""Postgres container: migrations, a row round-trip, pgvector, and per-test isolation."""

from sqlalchemy import Connection, text


def test_migrations_ran(db: Connection) -> None:
    # Alembic creates its bookkeeping table even with no revisions yet (T10 adds the first).
    assert db.scalar(text("select to_regclass('public.alembic_version')")) == "alembic_version"


def test_insert_and_read_a_row(db: Connection) -> None:
    db.execute(text("create table scratch_cases (id uuid primary key, status text not null)"))
    db.execute(
        text("insert into scratch_cases values (:id, :status)"),
        {"id": "0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b", "status": "OPEN"},
    )

    row = db.execute(text("select id::text, status from scratch_cases")).one()

    assert tuple(row) == ("0b6f1c1e-5d2a-4a8e-9a43-7c1d2e3f4a5b", "OPEN")


def test_rows_do_not_leak_between_tests(db: Connection) -> None:
    # Runs after test_insert_and_read_a_row (file order); its table was rolled back.
    assert db.scalar(text("select to_regclass('public.scratch_cases')")) is None


def test_pgvector_is_available(db: Connection) -> None:
    db.execute(text("create extension if not exists vector"))

    distance = db.scalar(text("select '[1,2,3]'::vector <-> '[1,2,4]'::vector"))

    assert distance == 1.0
