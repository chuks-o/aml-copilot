# Seed fixture data

A 126-row HI-Small look-alike for `aml seed` tests. It covers:

- zero-padded banks (`010` and `0010` are both bank `10`);
- one account number at two banks;
- patterned and `UNLISTED` laundering;
- a hub above an activity gap;
- a tail after the analysis end;
- a Bitcoin amount with 6 decimals.

`generate.py` writes these files from scratch. Run it from this directory, and commit what it writes.
