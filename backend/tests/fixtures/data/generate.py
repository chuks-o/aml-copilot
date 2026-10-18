"""Writes the seed fixture files (see README.md). Run from this directory."""

import csv

HEADER = [
    "Timestamp", "From Bank", "Account", "To Bank", "Account", "Amount Received",
    "Receiving Currency", "Amount Paid", "Payment Currency", "Payment Format", "Is Laundering",
]  # fmt: skip
HUB = ("070", "ABC000001")
rows: list[list[str]] = []


def tx(ts: str, src: tuple[str, str], dst: tuple[str, str], amount: str = "100.00",
       currency: str = "US Dollar", fmt: str = "Wire", label: int = 0) -> None:  # fmt: skip
    rows.append([ts, *src, *dst, amount, currency, amount, currency, fmt, str(label)])


# Normal days 2022-09-01..03: ten accounts at bank 10 trade with the hub, 4 transactions each
# per day (12 in total), the hub 120. Bank 10 is spelled both "010" and "0010".
for day in (1, 2, 3):
    for i in range(10):
        account = ("010" if i % 2 else "0010", f"80000000{i}")
        tx(f"2022/09/0{day} {i:02d}:00", HUB, account, fmt="ACH")
        tx(f"2022/09/0{day} {i:02d}:10", HUB, account, fmt="ACH")
        tx(f"2022/09/0{day} {i:02d}:20", account, HUB, fmt="Cheque")
        tx(f"2022/09/0{day} {i:02d}:30", account, HUB, fmt="Cheque")
# The same account number at two banks; a Bitcoin amount with 6 decimals.
tx("2022/09/01 12:00", ("010", "800000000"), ("020", "800000000"), "0.000001", "Bitcoin", "Bitcoin")
# Laundering: two patterned rows (ACH) and one UNLISTED (Cash).
tx("2022/09/02 13:00", ("010", "800000001"), ("020", "800000002"), "5000.00", fmt="ACH", label=1)
tx("2022/09/02 14:00", ("020", "800000002"), ("010", "800000003"), "4900.00", fmt="ACH", label=1)
tx("2022/09/02 15:00", ("010", "800000004"), ("020", "800000005"), "9000.00", fmt="Cash", label=1)
# Tail after normal activity stops (analysis end 2022-09-04T00:00Z): one clean, one laundering.
tx("2022/09/05 01:00", ("010", "800000006"), ("020", "800000007"))
tx("2022/09/05 02:00", ("020", "800000007"), ("010", "800000008"), fmt="Cash", label=1)

with open("HI-Small_Trans.csv", "w", newline="") as f:
    csv.writer(f).writerows([HEADER, *rows])
with open("HI-Small_Patterns.txt", "w", newline="") as f:
    f.write("BEGIN LAUNDERING ATTEMPT - FAN-IN:  Max 2-degree Fan-In\n")
    csv.writer(f, lineterminator="\n").writerows(r for r in rows if r[-1] == "1" and r[9] == "ACH")
    f.write("END LAUNDERING ATTEMPT - FAN-IN\n\n")
accounts = sorted({(r[i].lstrip("0") or "0", r[i + 1]) for r in rows for i in (1, 3)})
kinds = ["Corporation", "Individual", "Partnership", "Sole Proprietorship"]
with open("HI-Small_accounts.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Bank Name", "Bank ID", "Account Number", "Entity ID", "Entity Name"])
    for n, (bank, number) in enumerate(accounts):
        writer.writerow([f"Test Bank #{bank}", bank, number, f"E{n:05d}", f"{kinds[n % 4]} #{n}"])
print(f"{len(rows)} transactions, {len(accounts)} accounts")
