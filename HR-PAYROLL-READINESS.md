# ThaiACC HR/Payroll Localization — Statutory Evidence & Slice-1 Readiness

**Doc v0.1 (2026-10-01)** — study/readiness deliverable for handoff
`ho-b20317b2` / task `task-91ac46cd`. Extends the approved ThaiACC
18/19/20+ official-first strategy (`MIGRATION-20.0.md`). **This document
contains no implemented statutory numbers** — every rate/rule below carries
source + effective date; the implementation plan (Slice-1) ships them as
effective-dated data, never as Python/XML constants.

## 1. Verified statutory evidence (primary-source first)

### 1.1 Personal income tax (PIT) — มาตรา 48  bis / อัตราขั้นบันได

- **Source (primary):** กรมสรรพากร, [บัญชีอัตราภาษีเงินได้](https://www.rd.go.th/5938.html) (page updated 07-02-2024)
- **Brackets (เงินได้สุทธิ):** 0–150,000 ยกเว้น · 150,001–300,000 @5% · 300,001–500,000 @10% · 500,001–750,000 @15% · 750,001–1,000,000 @20% · 1,000,001–2,000,000 @25% · 2,000,001–5,000,000 @30% · เกิน 5,000,000 @35%
- **Effective:** พ.ร.บ. แก้ไขเพิ่มเติมประมวลรัษฎากรฉบับที่ 44 พ.ศ. 2560 — ใช้กับปีภาษีที่ 2560 เป็นต้นไป (source-stated)
- **Status: VERIFIED (primary).** Matches `l10n_th_pit` seeded brackets; the
  table model is already effective-dated per calendar year ✓.

### 1.2 Withholding returns — ภ.ง.ด.1 / 1ก / 2 / 2ก / 3 / 53

- **Source (primary):** กรมสรรพากร [ปฏิทินภาษีอากร](https://www.rd.go.th/62348.html) (+ [monthly calendar](https://www.rd.go.th/62348/archive/2026/3.html)) and the RD WHT guide [PDF](https://www.rd.go.th/publish/seminar/180515_WHT_doc.pdf)
- **Forms:** ภ.ง.ด.1 = 50(1) salary, paid **regularly** · ภ.ง.ด.1ก = 50(1) paid **once / irregularly** (ม.50(1) วรรคสอง criteria) · ภ.ง.ด.2/2ก = 50(2) hire-of-work · ภ.ง.ด.3 = 50(3)–(8) paid to **individuals** · ภ.ง.ด.53 = 50(1)(2)(3) paid to **corporates/partnerships**
- **Deadlines:** paper by the **7th** of the following month (next working day if holiday — e.g. Mar 2026 → 9 Mar); **e-filing by the 15th**
- **Certificate:** ม.50 ทวิ — payer must issue a WHT certificate (หนังสือรับรองการหักภาษี ณ ที่จ่าย) per withholding
- **Status: VERIFIED (primary).** Note the terminology trap: "50 ทวิ" in the
  certificate sense (ม.50 ทวิ certificate) is **not** the same document as
  ภ.ง.ด.50 (corporate half-year return) — the official `l10n_th` 50 Tawi
  report covers the latter.

### 1.3 Social Security (มาตรา 33) — SSO contribution

- **Rate & base:** employee and employer **5% each** of the wage, floor
  1,650 / cap 15,000 → max 750/month each — for **2567–2568**
- **⚠️ EFFECTIVE-DATE CHANGE (in force NOW):** กฎกระทรวง กำหนดค่าจ้างขั้นต่ำและค่าจ้างขั้นสูง (issued 12 Dec 2568, per ม.35 พ.ร.บ.ประกันสังคม) — stepped cap:
  - 1 Jan **2569** – 31 Dec 2571: cap **17,500** → max **875/month each**
  - 1 Jan 2572 – 31 Dec 2574: cap 20,000 → 1,000/month
  - 2575 onward: further steps
- **Status: SECONDARY-CONFIRMED** (four independent confirmations incl.
  [Thai PBS](https://www.thaipbs.or.th/news/content/359071),
  [ประชาชาติธุรกิจ](https://www.prachachat.net/sd/sdplus-hr/news-1936370);
  primary กฎกระทรวง/gazette PDF link to be attached — **action item**)
- **Periodic reductions exist** (e.g. Oct 2567 = 3%/450 per
  [SSO announcement](https://www.sso.go.th/wpr/download/download_by_pool_file/37788))
  — these MUST be data rows with validity windows, never constants.
- **This is the concrete proof of the "no hard-coded rates" rule**: a
  `5%/750` constant shipped on 27 Sep would have been wrong 4 days later.

### 1.4 Year-end employee reconciliation — ม.50(1) ทวิ วรรคสอง / payroll year-end

- **Source:** RD WHT guide [PDF](https://www.rd.go.th/publish/seminar/180515_WHT_doc.pdf), [ป.96/2543](https://www.rd.go.th/3558.html) — regular salary: annual projection ÷ months; lump-sum/irregular: ม.50(1) วรรคสอง criteria (director/retirement etc.)
- **Status: VERIFIED (primary, mechanism-level).** Exact year-end
  declaration forms (50 ทวิ certificate to employee; employee files
  ภ.ง.ด.90/91) — the [RD ภ.ง.ด.90/91 page](https://www.rd.go.th/65971.html) is primary.

### 1.5 SLF (กยศ.) repayment & PVD (กองทุนสำรองเลี้ยงชีพ) — **BLOCKED / CONDITIONAL**

- SLF repayment deduction terms: **UNVERIFIED** — no primary source fetched
  yet; treat any 'ปกส.'/'กยศ.' schedule as non-canonical until verified.
- PVD: contractual (fund deed), not statutory — deduction caps have tax
  rules (15%-of-income class) that need primary verification.
- Both are **out of Slice-1** until verified.

## 2. Capability matrix — Odoo 18/19/20 + OCA + ThaiACC repo

| Capability | Odoo 18/19/20 official | OCA 20.0 | ThaiACC repo | Gap |
|---|---|---|---|---|
| Payroll **engine** (salary structures, rules, payslips) | `hr_payroll` is **Enterprise-only** (community has 23 hr_* modules, no payroll) | [`OCA/payroll`](https://github.com/OCA/payroll) 20.0 community engine (generic, no TH rules) | none | decide engine: Enterprise (license) vs OCA `payroll` (community path) |
| Thai **payroll localization** (SSO/PIT/PND rules in payroll) | none (no `l10n_th_hr_payroll` in official) | none (verified: no l10n_th hit in OCA/payroll 20.0) | none | **the actual gap** |
| Employee **PIT progressive calc** (yearly brackets) | official `l10n_th` has no payroll PIT | — | **`l10n_th_pit`** (progressive table, effective-dated per year) ✓ | payroll-context monthly projection on top of the same table |
| **WHT engine + certificates** (ม.50 ทวิ) | official `l10n_th` WHT (is_withholding_tax engine) + certificates | — | reuse/verify ✓ | certificate formats per form 1/3/53 remain |
| **PND returns** (normalized data) | none | none | **`l10n_th_pnd_report`** (PND1/1A/2/3/53 normalized lines) ✓ | **e-file adapter (RD myTax/PND XML/JSON) — GAP** |
| **SSO contribution calc** | none | none | none | **GAP — Slice-1 core** |
| **50 ทวิ certificate** (WHT cert to payee) | official `l10n_th` has certificate formats (50 ทวิ cert) ✓ | — | reuse/verify ✓ | minor: per-form coverage |
| **Effective-dated statutory data** | chart tables are version-stamped (e.g. `account.tax-th.csv`) but payroll rules have no TH dataset | — | `l10n_th_pit.table` pattern ✓ | extend the pattern to SSO/PIT-bracket datasets |

## 3. Repo overlap / gaps (inspection of monthop-gmail/thaiacc-odoo @ 20.0)

- Already delivered (E20-001→006 + meta + migration contract): official
  chart/WHT/TI/50-Tawi/PromptPay reuse; `l10n_th_pit`; `l10n_th_pnd_report`;
  `l10n_th_wht_defaults`; `l10n_th_purchase_tax_invoice`; `l10n_th_migrate`.
- HR/Payroll overlap today: **none** — no `hr_*` Thai module in the repo.
- Reuse targets confirmed on 20.0: official `l10n_th` (50 Tawi report,
  WHT income types on `account.tax`, TIs), official WHT engine,
  `l10n_th_pit` table/progressive engine, `l10n_th_pnd_report` adapter.

## 4. Proposed module boundaries (calculation ≠ filing)

```
l10n_th_hr_payroll            # orchestration: links hr employees/payslips to
                              #   statutory datasets; NO rates in code
l10n_th_statutory_data        # effective-dated datasets + provenance fields:
                              #   sso.rate (rate/floor/cap/valid_from/to,
                              #   source_url, instrument), pit.bracket (from
                              #   l10n_th_pit), pnd.form catalog
l10n_th_payroll_pit           # monthly projection + year-end (ม.50(1)) using
                              #   l10n_th_pit progressive table (reuse, not
                              #   a second PIT engine)
l10n_th_payroll_sso           # SSO contribution computation (ม.33/39) from
                              #   sso.rate datasets incl. reduction windows
l10n_th_payroll_slf_pvd       # OPTIONAL later (blocked until verified)
l10n_th_pnd_efile             # RD e-file adapter (myTax/PND export) — reads
                              #   l10n_th_pnd_report, no calc logic
```

Invariants: official → OCA → bridge → ThaiACC-local; **calculation modules
never talk to filing endpoints**; adapters read the normalized PND report;
every statutory dataset row carries `source_url`, `instrument` (act/decree/
announcement), `valid_from`, `valid_to`.

## 5. Slice-1 — smallest justified implementation

**Scope:** `l10n_th_statutory_data` + `l10n_th_payroll_sso` (ม.33 only) +
read-only evidence doc.

- Data: `sso.rate` rows — 5%/1,650/15,000 (valid 2567-01-01→2568-12-31),
  5%/1,650/17,500 (2569-01-01→2571-12-31), 3%/450 reduction row (Oct 2567),
  each with source link; wage-base selection rule (min/floor → cap).
- Engine: monthly SSO per employee = clamp(wage, floor, cap) × rate, with
  reduction-window override; employer side mirrors.
- Tests: the 10 acceptance fixtures from the handoff (normal, mid-year
  join/leave, salary change, OT/allowance, bonus, bracket crossing, SSO
  bounds, reversal, multi-company, historical recompute at 2569 boundary).
- Explicitly **excluded from Slice-1**: PIT payroll projection (needs
  year-end decision gate), PND e-file (needs RD spec/credentials), SLF/PVD
  (unverified), payroll engine choice (Enterprise vs OCA — owner decision).

## 6. Implementable now vs blocked

| Item | Status |
|---|---|
| `l10n_th_statutory_data` model + SSO datasets (2567–2571, secondary-confirmed) | ✅ implementable now |
| `l10n_th_payroll_sso` ม.33 computation + fixtures | ✅ implementable now |
| PND e-file adapter | ⛔ BLOCKED — needs RD myTax format spec + credentials |
| SLF deduction | ⛔ BLOCKED — no primary source yet |
| PVD integration | ⛔ CONDITIONAL — fund-deed specific, needs owner input |
| Payroll engine (Enterprise vs OCA/payroll) | ⚠️ OWNER DECISION (license/architecture) |
| CABA VAT delta (−2,800) from the migration rehearsal | ⛔ BLOCKED — accounting decision gate (discussion seq 19) |

## 7. Open items

1. Attach the primary gazette/กฎกระทรวง PDF for the SSO cap (2569) —
   secondary-confirmed today.
2. Verify SLF repayment schedule against a primary source.
3. Confirm payroll engine choice (Enterprise vs OCA/payroll community).
4. Verify PVD tax-deduction caps (15%-class) against primary source.
