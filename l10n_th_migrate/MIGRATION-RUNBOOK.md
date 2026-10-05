# ThaiACC 19.0 → 20.0 Migration Runbook

This runbook covers the deterministic legacy evidence fixture, the
`l10n_th_migrate` runner, and a native Odoo 19 accounting rehearsal. The
runner connects to the source with a read-only PostgreSQL session. It maps
master data and evidence; it does **not** carry posted journal entries into
Odoo 20. The separate `scripts/rehearse_odoo19.py` imports the supported
invoice/payment cohort through the official Odoo 20 ORM, then invokes the
runner to reconcile it. It rejects unsupported document and tax shapes.

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
   A stock Odoo 19 database uses its own schema and cannot be passed directly.
   On an isolated Odoo 19 clone, apply
   `l10n_th_migrate/fixture/odoo19_source_views.sql`, insert the source
   company ID into `legacy19.scope`, and validate that it contains exactly one
   company before a run. These views translate the installed ThaiACC 19/OCA
   schema to the runner contract. Apply them only to a clone; the runner itself
   opens the source read-only.
3. Run once to map WHT taxes, PIT brackets, branch identifiers, PND person or
   company classification, and bank/PromptPay proxies. Legacy WHT moves,
   `novat`, and 50 Tawi certificates are archived as read-only evidence.
4. Migrate posted accounting through the accounting migration process.
   Preserve historical postings and references. The test constructs mirror
   documents only to exercise the reconciliation contract. The native clone
   rehearsal script below persists supported documents and payments and
   assigns source-scoped external IDs for repeat runs.
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
| 6. Partial/CABA | Two payments, 40% and 60%, produce two official purchase tax invoices and 3,000 WHT total | Real 19.0 clone check below found a 2,800 VAT delta on the second payment; investigate source posting before sign-off |
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

## Odoo 19 clone check (2026-09-28)

No usable old Odoo 19 database or Docker volume was found under
`../odoo-thaiacc` or `../odoo-thaiacc-test`. An isolated Odoo 19 database was
created from the 19.0 ThaiACC code and installed with the Thai chart and
ThaiACC modules. The database was then upgraded with the current
`monthop-gmail/thaiacc-odoo` 19.0 branch at commit `abd970f` (2026-09-02);
the OCA dependency checkout is retained from the old test directory. A
company-specific vendor bill was posted through the Odoo
ORM, paid with 3% withholding tax, and issued a 50 Tawi certificate. The
source views returned one WHT tax, one WHT move (base 100,000; WHT 3,000), one
vendor bill, two bill journal lines, one partner, one bank proxy, one issued
certificate, one PIT table, and eight PIT rates. All 11 view queries executed.

The Odoo 19 certificate relationship uses the certificate's payment journal
and partner, not `account_withholding_move.cert_id`; the adapter reflects that
verified relationship. A second Odoo 19 vendor bill was posted with 7,000
input VAT and tax invoice `VAT-MIG-19-001`; the source view returned the number,
date, and correct bill reference. This is a newly seeded cohort rather than
historical business data. The remaining acceptance gates above still require
a real source snapshot and a posted accounting import on the Odoo 20 target.

The Odoo 20 runner was executed twice against this clone. Before the target
bill was posted, it reported the missing bill reference, debit and credit
deltas of -100,000 each, and WHT delta of -3,000. After a matching bill and
payment were posted through the Odoo 20 ORM, the second run reported one
source and one target document, debit and credit of 100,000 on each side,
WHT 3,000 on each side, no missing reference, no duplicate mapped tax, and
`requires_manual_review=False` for the rows in this seeded cohort. This
first zero-delta result did not cover VAT. After posting the matching 107,000
VAT bill on Odoo 20, a further run mapped the vendor tax-invoice number and
date onto the target bill. Source and target document debit and credit totals
were 207,000 each, WHT stayed 3,000 each, and all reported deltas were zero.
The bill journal lines also matched by account code on both sides:
`611100` debit 200,000, `114200` input VAT debit 7,000, and `212100`
payables credit 207,000.
The clone was extended with a posted customer invoice (output VAT 7,000) and
a cancelled customer invoice. The Odoo 20 posted invoice has an official
sales tax invoice, while the cancelled invoice's tax invoice has state
`cancel`. The cancelled source and target invoices are excluded from posted
controls. The runner's customer tax-invoice lookup now restricts by posted
state and company, which matters when a cancelled target invoice shares a
reference with the posted replacement. The final source and target document
debit and credit totals were 314,000 each, with no reported deltas.

The clone was then extended with an on-payment VAT bill of 107,000, paid in
two installments of 42,800 and 64,200. Odoo 19 created two CABA tax invoices.
The source view now follows `tax_cash_basis_origin_move_id` from each CABA
journal to its original bill and preserves each tax invoice and VAT amount
separately. The first source installment recorded VAT 2,800 and matched the
Odoo 20 official tax invoice, so its number `CABA-MIG-19-40` was mapped.
The second source installment recorded VAT 7,000 while the Odoo 20 official
tax invoice recorded 4,200. Source CABA VAT totals 9,800; target totals
7,000. The runner archives both source CABA rows, leaves the second target
number unset, and reports source ID 5 unresolved with `caba_vat_delta=-2800`
and `requires_manual_review=True`. The posted bill document debit and credit
controls still match at 421,000 on each side. This is an observed result in
the seeded Odoo 19 clone and needs investigation before any live migration.
The corresponding consistent fixture (VAT 2,800 + 4,200) maps both numbers;
the focused CABA test and the full `l10n_th_migrate` suite passed (11/11).

A genuine reversal pair, PIT payment history, PND period totals, and historic
transaction identities are not represented by this new clone cohort; those
acceptance items remain open.

## Native Odoo 19 accounting rehearsal (2026-09-28)

Apply `fixture/odoo19_source_views.sql` to an **isolated clone** of Odoo 19,
insert one source company into `legacy19.scope`, then grant the source DSN
read-only access. Create a fresh Odoo 20 database with `thaiacc` and
`l10n_th_migrate` installed. Run `scripts/rehearse_odoo19.py` as stdin to
`odoo shell` with `THAIACC_SOURCE_DSN` and `THAIACC_TARGET_COMPANY` set. The
script creates the Thai target company and chart, imports native invoice lines
and reconciled payments, maps the source WHT posting account to the official
tax repartition, and runs the evidence mapper on both sides of the import.
Afterwards run `-u thaiacc,l10n_th_migrate` on that target database and run
the script again with `THAIACC_POST_UPGRADE=1`. A run emits one
`THAIACC_REHEARSAL_REPORT=` JSON line. Persist it for audit; the report from
our final after-upgrade run is `fixture/odoo19_rehearsal_report.json`. The
script is a strict rehearsal for its supported invoice/payment shapes, not a
general ledger migration for arbitrary historical source rows.

The isolated source was the current `monthop-gmail/thaiacc-odoo` 19.0 commit
`abd970f` with the ThaiACC 19/OCA stack. Repeating the CABA case against an
upgraded copy with current OCA `l10n-thailand` 19.0 commit `cc24480` still
gave 2,800 VAT on the first 40% payment and 7,000 on the second 60% payment.
The source posting, not only the older OCA checkout, therefore needs an
accounting decision.

The final fresh-target run used database `thaiacc13_rehearsal_v3`. It imported
four posted documents, one cancelled document, and three payments. Source and
target posted document debit/credit were 421,000 each. Source and target WHT
were 3,000 each. Vendor and customer on-invoice tax invoices mapped, as did
one bank/proxy and one historical 50 Tawi certificate into the archive. A
second import created **zero** documents and **zero** payments; all eight
source identities remained linked. The post-import `thaiacc,l10n_th_migrate`
upgrade and a following registry/reconciliation run succeeded.

| Gate | Result | Evidence / action |
|---|---|---|
| Posted invoice debit/credit | PASS | 421,000 each; four posted refs, no missing refs |
| WHT | PASS | 3,000 both sides; source account `MIGWHT19` preserved in target tax repartition |
| On-invoice VAT | PASS | Vendor 7,000 and customer 7,000 with official target invoices |
| Canonical import identity and post-upgrade run | PASS | 5 moves + 3 payments linked; repeat created 0; upgrade succeeded |
| CABA and monthly ledger | DELTA | Source VAT 9,800 vs target 7,000. September account `114200` net target-minus-source = -2,800 and `114299` = +2,800; source CABA tax invoice ID 5 unresolved |
| Gross expense turnover | DELTA, net zero | Two official-only mirror shapes, both net zero: official WHT payments mirror the base through the expense account on the payment entry (±100,000) and official CABA entries mirror the proportional base per partial (±100,000 combined); the legacy stack books neither. Classified in `CABA-VAT-DECISION-GATE.md` §7 |
| PIT/PND, reversal, live QR, historical 50 Tawi access | BLOCKED | The seeded clone lacks the relevant historical transactions or approved replacement policy |
| Production historical migration | BLOCKED | No historical Odoo 19 database/snapshot was available; this is a newly seeded clone |

`PASS` applies only to this seeded cohort. The overall machine report is
`BLOCKED` because the historical source and several acceptance rows are not
available. Do not promote this database as a production migration or close
task #13 on this evidence.

## Reproducible seed cohort and CABA classification (2026-10-05)

`scripts/seed_odoo19_rehearsal.py` rebuilds the native Odoo 19 cohort on a
fresh clone deterministically (payments pinned to 2026-09-10/15/20): the
WHT bill with 50 Tawi certificate, the on-invoice VAT bill with tax
invoice `VAT-MIG-19-001`, a posted and a cancelled customer invoice, and
the on-payment (CABA) bill paid 42,800 then 64,200. Apply
`fixture/odoo19_source_views.sql`, set `legacy19.scope` to the seeded
company, grant a read-only role the `legacy19` schema, and run
`scripts/rehearse_odoo19.py` on a fresh Odoo 20 target followed by
`-u thaiacc,l10n_th_migrate` and a post-upgrade rerun with
`THAIACC_POST_UPGRADE=1`. The archived report from that sequence is
`fixture/odoo19_rehearsal_report.json`.

The rerun reproduced every frozen control total (documents 421,000, WHT
3,000, on-invoice VAT mapped, CABA source 9,800 vs target 7,000) and the
post-upgrade import created 0 documents and 0 payments. After the owner
decisions (dec-24252acf, dec-a92c38dc, dec-5684a37d) were implemented,
the cohort also carries a genuine reversal pair — vendor credit note
`MIG-REFUND-001` posted, reconciled against `MIG-BILL-002`, and mirrored
by the target with `reversed_entry_id` set (documents 528,000 both
sides) — and the machine gates close as follows: posted_documents,
withholding, on_invoice_vat, canonical_identity, post_migration_upgrade,
reversal_pair = PASS; caba_vat = PASS under the
`l10n_th_migrate.caba_over_claim_policy=official_canonical` parameter
(the legacy 7,000 over-claim row is archived with a cross-reference to
the canonical bill, never rebooked); pit_pnd_periods = PASS with the
PND1A manual review queue recorded; historical_50_tawi_access = PASS
via the read-only Accounting archive menu;
full_ledger_by_period = DELTA with every delta explained (the accepted
2,800 CABA pair plus official-only net-zero mirror shapes ±200,000);
bank_qr_render and historical_source_snapshot stay BLOCKED on external
dependencies.

**Settlement order decides the CABA over-claim.** Clearing each
installment's deferred tax before paying the next yields 2,800 + 4,200 =
7,000 (equal to official 20). Paying both installments before any
clear-tax step yields the frozen 2,800 + 7,000 = 9,800: the legacy
draft-reset between partials destroys the incremental claimed-VAT state,
so the second entry books the full remaining VAT. Q1–Q3 traces on both
sides and the ENGINE BEHAVIOR classification are in
`CABA-VAT-DECISION-GATE.md` §7; PND1A options are in
`PND1A-CLASSIFICATION.md` and the 50 Tawi archive access options in
`50-TAWI-ARCHIVE-ACCESS.md`. Both await the owner decision.
