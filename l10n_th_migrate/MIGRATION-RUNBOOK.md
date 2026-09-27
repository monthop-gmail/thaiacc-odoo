# ThaiACC 19.0 → 20.0 Migration Runbook

This runbook covers the deterministic legacy evidence fixture and the
`l10n_th_migrate` runner. The runner connects to the source with a read-only
PostgreSQL session. It maps master data and evidence; it does **not** carry
posted journal entries into Odoo 20. An accounting migration must post or
import those entries separately, then the runner can reconcile them.

## Fixture test

Use an isolated Odoo 20 database with `thaiacc` and `l10n_th_migrate`
installed. Run with demo data because the fixture targets the ThaiACC demo
partners and taxes:

```bash
DEMO=1 bash test/run_install_test.sh thaiacc l10n_th_migrate
```

The script recreates its named test database and PostgreSQL container. Do
not run it against a shared database. The end-to-end test recreates
`thaiacc19_fixture`; set `THAIACC_LEGACY_FIXTURE_DB` to an isolated name when
running Odoo directly. The fixture SQL is
`l10n_th_migrate/fixture/legacy_19_fixture.sql`.

## Two-run sequence

1. Install the target `thaiacc` meta package and `l10n_th_migrate` on Odoo
   20. Configure the Thai chart and fiscal country.
2. Point `source_dsn` at a legacy database. Grant the credential read-only
   access. The runner calls `set_session(readonly=True)` as a second guard.
   Current SQL expects a normalized `legacy19` schema shaped like the fixture.
   A stock Odoo 19 database uses its own schema and cannot be passed directly;
   build and validate read-only source views before a real database run.
3. Run once to map WHT taxes, PIT brackets, branch identifiers, PND person or
   company classification, and bank/PromptPay proxies. Legacy WHT moves,
   `novat`, and 50 Tawi certificates are archived as read-only evidence.
4. Migrate posted accounting through the accounting migration process.
   Preserve historical postings and references. The test constructs mirror
   documents only to exercise the reconciliation contract.
5. Run again to attach vendor tax-invoice evidence and produce
   `stats.reconciliation_summary`. Review every missing reference, debit and
   credit delta, WHT delta, unresolved partner, and duplicate tax name.
   `state=done` means this runner finished; it is **not** migration sign-off.
6. Upgrade `thaiacc` on the migrated target database and verify registry
   load, all module states, and accounting control totals independently.

Example Odoo shell call:

```python
run = env["l10n_th.migrate.run"].create({
    "source_dsn": "host=db user=readonly dbname=thaiacc19",
})
run.action_run()
assert run.state == "done", run.error_message
print(run.stats["reconciliation_summary"])
```

## Acceptance matrix from ThaiACC discussion seq 13

| Item | Fixture evidence | Remaining gate |
|---|---|---|
| 1. Trial balance | Source posted debit and credit = 903,000; target document debit and credit are measured and checked separately | Explain every source-to-target journal total delta after full accounting import |
| 2. Sales and purchase VAT | Customer output VAT 7,000 and official tax invoice; vendor CABA input VAT in two payments | Compare full source and target input/output VAT periods |
| 3. PIT | Two payments: base 200,000 then 100,000; WHT 2,500 then 5,000 from official payment lines | Validate against a real legacy PIT cohort |
| 4. PND | Fixture checks PND1/2/3/53 totals in the 2026 period | PND1A source designation is absent; manually classify or add a reliable source field |
| 5. Cancel/reverse | Cancelled invoice and WHT move excluded from posted totals; target invoice cancellation checked | Add a genuine reversal pair with source and target journal evidence |
| 6. Partial/CABA | Two payments, 40% and 60%, produce two official purchase tax invoices and 3,000 WHT total | Reconcile source and target VAT amounts per payment |
| 7. PromptPay/bank | Bank account and tax-ID proxy map to official `proxy_type`/`proxy_value` | Check live QR rendering after actual bank-owner mapping |
| 8. 50 Tawi history | Legacy certificates archived verbatim, no legacy engine revived | Confirm an official replacement or approve read-only historical access |
| 9. Post-migration upgrade | `thaiacc` installed and registry loads in fixture test | Upgrade the migrated target *after* persistent accounting migration |
| 10. No duplicates | Mapped tax names checked; a second runner pass does not add payment WHT lines | Reconcile canonical transaction identities against source import |
| 11. Consolidated report | `stats.reconciliation_summary` records control totals, deltas, missing refs and unresolved partners | Resolve all review flags before sign-off |
| 12. Documentation | This runbook and `MIGRATION-CONTRACT.md` record the expanded fixture and limits | Update with results from an actual 19 database |

The fixture is synthetic. Its green test result proves the stated mapping
paths and control checks, not a full production migration. No source ledger
is rewritten. `novat` and historical certificates remain read-only evidence
until their target policy is decided.
