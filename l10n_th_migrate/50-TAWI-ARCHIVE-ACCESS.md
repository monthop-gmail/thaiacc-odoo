# 50 Tawi certificate history — long-term read-only access proposal

**For task-34e91b4e** per discussion seq 19 guidance item 5 (and runbook
acceptance row 8).

## Verified evidence

- The migration runner already archives legacy certificates **verbatim**
  into `l10n_th.migrate.archive` (no legacy engine revival, no rewrite):
  see `_archive_certificates` / `_archive_legacy_only` in
  `l10n_th_migrate/models/migrate_run.py`. The rehearsal run archived
  1 certificate with source-scoped identity.
- Odoo 20 official has no 50 Tawi certificate engine equivalent; new
  transactions use the official withholding path
  (`l10n_account_withholding_tax` engine + `l10n_th_wht_defaults`).
- What is missing is only an **approved access path** for the archived
  history after cutover.

## Options

| Option | Description | Trade-off |
| --- | --- | --- |
| A — Accounting menu view (**recommended**) | Read-only list/form on `l10n_th.migrate.archive` (source-identity, payload JSON, archived date), visible to Accountants group, search by partner/number/date | Small addon surface; history lives with the books |
| B — Export-only | Periodic PDF/CSV export of archived certificates to an external document store | Two systems to keep auditable |
| C — SQL/DBA-only access | No UI; support retrieves via DB | Not operational for accountants |

## Recommendation

Option A: one read-only model view + access rule on the existing
archive model, plus a cross-reference from migrated payments to the
archived certificate rows. Old certificates stay queryable read-only
forever; new certificates are official 20 records only.

**Owner decision needed:** approve Option A (UI exposure) or B/C.
