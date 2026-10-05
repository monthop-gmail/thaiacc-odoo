# ThaiACC Odoo 19 → 20 migration guide

Use this sequence for each source company. The current `rehearse_odoo19.py`
supports a controlled invoice/payment cohort and rejects other move/tax
shapes. A production cutover requires a historical source snapshot and a
separate importer for every remaining journal shape.

## 1. Freeze and inspect the source

1. Record the source database UUID, company ID, Odoo 19 commit, OCA commit,
   installed module list, chart, fiscal periods, and record counts.
2. Restore the source backup into an isolated Odoo 19 clone. Never apply
   adapter views to the live database. Without a historical snapshot,
   `scripts/seed_odoo19_rehearsal.py` (run as stdin to `odoo shell` on the
   clone) seeds the deterministic rehearsal cohort instead.
3. Apply `fixture/odoo19_source_views.sql` to the clone and insert **exactly
   one** company ID into `legacy19.scope`. Grant the importer SELECT-only
   access. The Python connection also starts in read-only mode.
4. Export complete posted ledger and tax totals by company, period, account,
   partner, payment, and source document identity. Include cancelled/reversed
   entries, cash-basis journals, WHT/PIT/PND, tax invoices, bank proxies, and
   50 Tawi certificates. Keep the original dump and exports unchanged.

## 2. Prepare the target

Create an empty Odoo 20 database and install `thaiacc` plus
`l10n_th_migrate`. Configure the Thai chart, fiscal country, VAT registration,
and bank journals. Record the target image and Git commit. Never import into a
production target before a successful clone rehearsal and reviewed deltas.

## 3. Import and reconcile

For the supported cohort, pass `scripts/rehearse_odoo19.py` to `odoo shell`
on the target, with `THAIACC_SOURCE_DSN` and `THAIACC_TARGET_COMPANY` in its
environment. The script reads native Odoo 19 adapter views, posts through
the official Odoo 20 ORM, and emits one JSON report line. It maps source
database UUID + company + model + row ID to persistent Odoo external IDs.
Rerun it and verify `documents.created=0` and `payments.created=0`.

Example for an isolated Docker network; set the source DSN in the invoking
shell and replace database/image paths with the actual rehearsal values:

```bash
export THAIACC_SOURCE_DSN='host=db dbname=odoo19_clone user=readonly password=...'
docker run --rm -i --network thaiacc20net \
  -e THAIACC_SOURCE_DSN -e THAIACC_TARGET_COMPANY='ThaiACC 20 Rehearsal' \
  -v "$PWD":/mnt/extra-addons:ro --entrypoint /usr/bin/odoo thaiacc-test:20 \
  shell -d odoo20_rehearsal --db_host=db --db_user=odoo \
  --db_password=odoo --max-cron-threads=0 \
  < l10n_th_migrate/scripts/rehearse_odoo19.py
```

For other journal shapes, add a reviewed adapter and importer before the
production run. Do not silently skip journal entries, split payments,
unsupported taxes, or ambiguous partners. The rehearsal script fails when it
encounters unsupported invoice types, tax rates, missing accounts, or a
payment linked to multiple invoices.

Compare both document controls and **the complete posted ledger** by company,
period, and account. Gross debit/credit differences reveal changed posting
shapes even if net balance agrees. Investigate every net balance, VAT/WHT/PIT,
PND, cancellation/reversal, bank, and tax-invoice delta. Preserve the legacy
certificate archive for audit; decide its long-term read-only access before
cutover.

## 4. Upgrade and sign off

Upgrade `thaiacc,l10n_th_migrate` on the imported target. Reload the Odoo
registry, rerun the import and controls, then record the machine JSON and a
human PASS/DELTA/BLOCKED matrix. A runner state of `done` only means its
mapping step completed. Require zero unexplained deltas, complete source
coverage, no duplicate canonical identities, and explicit decisions for
legacy-only evidence before production sign-off.

The 2026-09-28 seeded-clone result is in `fixture/odoo19_rehearsal_report.json`
and explained in `MIGRATION-RUNBOOK.md`. Its CABA VAT difference and absent
historical source snapshot block production sign-off.
