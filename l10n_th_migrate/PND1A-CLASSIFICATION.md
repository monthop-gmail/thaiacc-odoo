# PND1A source-classification rule — decision proposal

**For task-34e91b4e** per discussion seq 19 guidance item 4: settle the
PND1A business rule before implementing any migration mapping.

## Verified evidence

| Side | Fact | Source |
| --- | --- | --- |
| Odoo 20 target | `l10n_th_pnd_report` defines form **`pnd1a`** ("P.N.D.1A - One-time Salary") and can render it | `l10n_th_pnd_report/models/l10n_th_pnd_report.py` selection (20.0) |
| Odoo 19 legacy source | `income_tax_form` selection = **pnd1, pnd2, pnd3, pnd3a, pnd53 — no `pnd1a`** | `l10n_th_account_tax/models/withholding_tax_cert.py` `INCOME_TAX_FORM` (19.0) |
| Migration runner | Classifies only `pnd_entity_type` (person/company) per partner; carries no form-level designation | `l10n_th_migrate/models/migrate_run.py` `_map_branch_identifiers` |

Conclusion: the absence of PND1A designation is a **source-model
limitation, not missing data**. A legacy withholding move that is
economically PND1A (one-time salary) is indistinguishable from a monthly
PND1 move in the 19.0 schema, so no derivation rule can be both complete
and safe.

## Options

| Option | Description | Risk |
| --- | --- | --- |
| A — derive in migration | Heuristic (e.g. single PIT move per person-year ⇒ PND1A) | Wrong statutory filing; silently rewrites tax history |
| B — extend legacy stack | Add `pnd1a` to the 19.0 `income_tax_form` selection and backfill in the source | Touches the frozen source schema; needs source-side deploy |
| C — manual classification queue (**recommended**) | Migration archives the legacy designation verbatim, marks PIT/person rows `form_requires_manual_classification`, and the accountant sets the form on the target before the first PND filing | Manual effort bounded by the count of qualifying rows; no silent rewrite |

## Recommendation

Option C. Concretely: the runner keeps archiving legacy withholding
evidence verbatim, the rehearsal/report flags any `is_pit` move whose
PND form is ambiguous as `form_requires_manual_classification`, and
PND1A/PND1 selection happens in the Odoo 20 target where the official
`pnd1a` form exists. No target row is auto-filed as PND1A.

**Owner decision needed:** approve Option C (or pick B if source-side
schema change is acceptable before cutover).
