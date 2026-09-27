# ThaiACC 19.0 → 20.0 Migration Runbook (repeatable)

Repeatable smoke for the migration contract (`MIGRATION-CONTRACT.md` in this
module). Source database is only ever read (`set_session(readonly=True)`);
posted accounting on the 20.0 side is never modified by the runner — it only
adds master data, evidence fields and an archive.

## Prerequisites

- Odoo 20.0 with the `thaiacc` suite installed (target database)
- A legacy 19.0 database reachable via a libpq DSN, containing the
  `legacy19` schema subset the contract maps. For the deterministic
  fixture: `l10n_th_migrate/fixture/legacy_19_fixture.sql`

## Steps

1. **Load the fixture** (smoke only — a real migration points the DSN at the
   actual legacy DB):
   ```bash
   psql -h db -U odoo -d postgres \
        -c 'DROP DATABASE IF EXISTS thaiacc19_fixture'
   psql -h db -U odoo -d postgres -c 'CREATE DATABASE thaiacc19_fixture'
   psql -h db -U odoo -d thaiacc19_fixture \
        -f "$(odoo path?) l10n_th_migrate/fixture/legacy_19_fixture.sql"
   ```
2. **Run 1 — master data** (Odoo shell or a server action):
   ```python
   run = env['l10n_th.migrate.run'].create({
       'source_dsn': 'host=db user=odoo password=odoo dbname=thaiacc19_fixture',
   })
   run.action_run()
   run.state, run.stats   # 'done' + reconciliation report
   ```
   Maps withholding taxes, PIT tables, branch identifiers, archives
   legacy-only rows. Idempotent: matching by name / vat / reference.
3. **Post the migrated accounting** on the 20.0 side (the legacy business
   events re-posted with the mapped taxes) — the reconciliation needs the
   official payment withholding lines to exist.
4. **Run 2 — evidence + reconciliation**: `run.action_run()` again on a new
   run record. Tax-invoice evidence lands on the matching vendor bills
   (search is scoped to in_invoice/in_receipt — payment entries carry the
   bill name in their ref too), and `run.stats['reconciliation']` compares
   legacy withholding totals with the official lines; `matched` must be
   true.
3. **Reconcile**: `run.stats['reconciliation']` compares legacy withholding
   evidence totals with the official payment withholding lines; `matched`
   must be true. Legacy-only evidence (withholding moves, novat flags) is
   archived verbatim in `l10n_th.migrate.archive`.
5. **Automated equivalent**: `l10n_th_migrate/tests/test_migrate_e2e.py`
   runs the whole sequence — fixture creation, two runs, reconciliation and
   the source-untouched fingerprint — with:
   ```bash
   DEMO=1 bash test/run_install_test.sh l10n_th_migrate
   ```

## Non-goals (per contract)

- No legacy engine is revived; legacy-only evidence is archived.
- Posted accounting on the target is never rewritten.
- `novat` and WHT certificates remain archived history (see contract gaps).
