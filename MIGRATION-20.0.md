# ThaiACC — Odoo 20: Architecture & Migration Status

**Doc v2 (2026-09-27) — supersedes v1.** Official-first is the canonical
architecture (team decision, ai-collab discussion `dis-ea38366d` /
`dis-90ea31a4`). The v1 "strategy B" (self-migrating the whole OCA
dependency chain as the primary plan) is superseded; that spike's useful
output survives as optional temporary bridges and as recorded migration
knowledge — see §4 and §5.

## 1. Status: E20 sequence complete

All six slices of the ThaiACC Odoo 20 implementation sequence
(`plan-ac508f12`) are delivered on branch `20.0`, built on the released
`20.0.20260926` official build:

| Slice | Deliverable | Commit |
|---|---|---|
| E20-001 | 20.0 branch + official-only compose/devcontainer baseline (`THAIACC_PROFILE=official`) | `b49ad6b` |
| E20-002 | Official-capability smoke tests (`test/official_smoke_test.sh`: official suite 15/15 + capability checks 9/9) | `68047a8` |
| E20-003 | `l10n_th_purchase_tax_invoice` — vendor tax invoice evidence + payment-time input-VAT invoices on the official `l10n_th.tax.invoice` model | `24aecc5` |
| E20-004 | `l10n_th_wht_defaults` — product-level default WHT on the official `l10n_account_withholding_tax` engine | `24aecc5` |
| E20-005 | `l10n_th_pit` — progressive PIT on the official WHT engine (per-year bracket tables, marginal computation, yearly base read from official payment withholding lines) | `b3d3e99` |
| E20-006 | `l10n_th_pnd_report` — normalized PND1/1A/2/3/53 adapter over official payment withholding data | `b3d3e99` |

Test evidence: 37 `def test_*` methods across the suite (purchase_tax_invoice
5 + superseded official replacement, wht_defaults 4, pit 4, pnd_report 4,
ocaacc 5, thaiacc 4, migrate 11) + official `l10n_th` regression 15/15, all
green on a fresh database (runs reproduced via `test/run_install_test.sh`;
note the Odoo runner's stats line attributes cases differently than source
`def test_*` counts — see discussion seq 22).

## 2. Canonical architecture (official-first)

Odoo official first → OCA upstream second → temporary fork only for missing
upstream → ThaiACC-local code only for proven Thai gaps.

- Official Odoo models are canonical: `l10n_th` (core Thai chart),
  `account.tax.is_withholding_tax`, `l10n_account_withholding_tax`,
  `l10n_th.tax.invoice`, `res.partner.additional_identifiers`
  (`TH_BRANCH_CODE` / `TH_VAT`).
- Do not recreate legacy engines (old WHT engine, certificate ledger,
  sales tax invoice, PromptPay QR, 50 Tawi) — official Odoo 20 provides them.
- Do not port `l10n_th_account_tax` 19.0 wholesale.

## 3. ThaiACC-local modules on 20.0 (proven Thai gaps)

| Module | Purpose |
|---|---|
| `l10n_th_purchase_tax_invoice` | Vendor tax invoice document evidence + purchase-side payment tax invoices (the one gap the official module explicitly leaves open) |
| `l10n_th_wht_defaults` | Product-level default WHT suggestion for vendor bills |
| `l10n_th_pit` | Progressive PIT rate tables + marginal withholding on official lines |
| `l10n_th_pnd_report` | Normalized PND1/1A/2/3/53 adapter + report |
| `l10n_th_base_sequence` | BE-year / quarter / range sequence legends (core-only; see §5) |
| `l10n_th_promptpay` | PromptPay QR on the custom payment provider (core-only deps) |

## 4. Temporary OCA bridges — inventory and exit conditions

Self-migration spike branches exist on the working clones (and can be pushed
to the `monthop-gmail` forks when needed). They are **optional bridges, not
the plan**: retire each one as soon as its exit condition is met.

| Bridge | Where | Needed by | Exit condition | Exit action |
|---|---|---|---|---|
| `date_range` | `OCA/server-ux` fork branch `20.0-mig-date_range` | `l10n_th_account_tax_report` (Later bucket) | `OCA/server-ux` 20.0 ships `date_range` | drop the `monthop 20.0-mig-*` line from `repos.yml`, aggregate upstream |
| `report_xlsx` + `report_xlsx_helper` | `OCA/reporting-engine` fork branches | PND/xlsx reporting (Later bucket) | `OCA/reporting-engine` 20.0 ships both | same |
| `partner_company_type`, `partner_firstname`, `partner_title` | `OCA/partner-contact` fork branches | `l10n_th_partner` chain (Later bucket) | `OCA/partner-contact` 20.0 ships them (mind the 20.0 `is_company` semantic, see §5) | same |
| `base_tier_validation` family, `mis_builder` | not started | `l10n_th_tier_department`, `l10n_th_mis_report` (Later bucket) | upstream 20.0 branches exist | migrate only if still needed by the Later-bucket work |

General exit rule (team fork policy): a fork is a temporary compatibility
bridge, retired once suitable OCA upstream exists **and** ThaiACC
compatibility tests pass against it.

## 5. Migration knowledge (spike output, preserved)

Generic Odoo 19→20 rules discovered during this work are recorded in the
shared guide — **that repo is the canonical place for migration knowledge**:
[`monthop-gmail/odoo-migration-guide`](https://github.com/monthop-gmail/odoo-migration-guide)
→ `transitions/19-to-20/` (ir.access refactor, odoo.http package split,
`report_file` removal, typed `ir.config_parameter` getters, post_install
test default, virgin-db `-i` quirk, `company_registry` →
`additional_identifiers`, CABA company-flag gate, `is_company` stored
compute, …), each with evidence.

Thai accounting–specific notes (kept here, linked from the guide):
- `res.company.tax_exigibility` is set by the Thai chart itself
  (`template_th._get_th_res_company`) — it is what enables CABA.
- The official test `test_no_tax_invoice_created_for_vendor_bill_payment` is
  intentionally superseded by `l10n_th_purchase_tax_invoice` (vendor bill
  payments DO create tax invoices now); the official test method is replaced
  on the official class with the new expectation.
- Official withholding line amounts are positive; signs are applied when
  AMLs are created.
- `l10n_th_base_sequence` on this branch carries the core-20.0 alignment
  fixes (ISO week legends, `env.transaction.clear()`); when
  `OCA/l10n-thailand` opens its 20.0 branch, these fixes go upstream via
  `20.0-mig-l10n_th_base_sequence` and the local copy is shadowed again.

## 6. Remaining (Later bucket — needs team/owner direction)

Utility OCA bridge packaging, ThaiACC extras, expense redesign, meta
packages (`ocaacc`/`thaiacc`), full 19→20 data migration, upstream
convergence automation. None of these are started; none block the 20.0
official-only baseline.

## 7. Decision history

- **v1 (2026-09-26):** "strategy B" — self-migrate the whole OCA dependency
  chain so the 19.0 feature set runs on 20.0. Executed as a spike: the
  `date_range` / `report_xlsx*` / partner-trio branches and most of the
  recorded 19→20 rules came from it.
- **v2 (2026-09-27, current):** team decision — official-first canonical
  architecture; the spike's branches are optional bridges (§4) and its
  findings are migration knowledge (§5). The E20 sequence was implemented
  under this architecture and supersedes the self-migration plan.
