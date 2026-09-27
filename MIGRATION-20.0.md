# ThaiACC — แผน Migration สู่ Odoo 20.0

จัดทำ: 2026-09-26 (วัน release ของ Odoo 20.0-20260926)
เป้าหมาย: migrate โมดูลทั้งหมดของ thaiacc ขึ้น Odoo 20 ตามกฏของ [OCA maintainer-tools](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-20.0)

---

## 1. กฏที่ใช้ (แหล่งอ้างอิง)

| แหล่ง | ใช้ทำอะไร |
|---|---|
| [OCA wiki — Migration to version 20.0](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-20.0) | ขั้นตอน process: branch naming, วิธีพก history, commit/PR conventions, สิ่งที่ **ห้าม** ทำ |
| [OCA wiki — Migration to version 19.0](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-19.0) | Checklist framework changes — เราผ่านมาแล้วตอน migrate 19.0 (ผล scan §3) ใช้เป็น **regression checklist** ย้ำตอนรีวิว PR |
| [`odoo-migration-guide/`](https://github.com/monthop-gmail/odoo-migration-guide) (repo ของทีม, เดิมชื่อ odoo-19-migration-guide) | Workflow scan → auto-fix → validate ตาม `migration-rules.yaml`; กฏ 19→20 จากงานนี้ถูก seed ไว้ที่ `transitions/19-to-20/` แล้ว (PR #1 merged) |
| [OpenUpgrade](https://github.com/OCA/OpenUpgrade) `upgrade_analysis.txt` | อ้าง data-model changes — **ยังไม่มี branch 20.0** (ณ 26 ก.ย.) ชั่วคราว diff จาก source จริง (มี `odoo-src/` clone 20.0 ไว้แล้ว) |

ข้อกฏทีม (จาก thaiacc-workspace `CLAUDE.md`) ยังบังคับเหมือนเดิม: **1 PR ต่อ 1 โมดูล**, **พก commit history ครบ + `[MIG]` commit เดียวด้านบน**, `Assisted-by:` trailer (ไม่ใช่ Co-authored-by), **ห้าม vendor dependency ที่ยังไม่ release** ใส่ branch เพื่อดัน CI, และ branch `*mig-*` บน fork คือ PR สด — ระวัง force-push

## 2. สถานะตั้งต้น — Wave 0 เสร็จแล้ว (2026-09-26)

- Branch `20.0` (local): bump version `20.0.1.0.0` ทั้ง 7 โมดูล, fix promptpay view, fix base_sequence, `repos.yml` เล็ง `oca 20.0`, Dockerfile → `odoo:20.0`
- ติดตั้ง + เทสต์บน Odoo 20.0-20260926 (deb official, sha1 ตรง): `l10n_th_base_sequence` 8 tests ✅, `l10n_th_promptpay` 3 tests ✅, `/web/login` 200 ✅
- `ocaacc`/`thaiacc` ยัง install ไม่ได้ — OCA ยังไม่มี branch 20.0 (มีแค่ partner-contact) → error ตรงตามคาด: `depends on module "l10n_th_account_tax" ... not available`
- Infra ทดสอบ: image `odoo:20` + `thaiacc-test:20`, สคริปต์ `test/run_install_test.sh` (นอก repo)

## 3. ผล scan กฏ 19.0 บนโมดูลทำเอง — สะอาด

`groups_id`, `_sql_constraints`, `auto_join`, `ormcache_context`, `@api.returns`, `toggle_active`, `osv.expression`, `read_group(`, `self._cr/_context/_uid`, `target='inline'`, `FakeModelLoader`, `type="json"`, `from odoo import SUPERUSER_ID`, `env.clear()` → **0 hits ทั้งหมด** (14 patterns, 7 โมดูล)

> แปลว่างาน 19→20 ไม่ต้องแก้พวก legacy ซ้ำ — โฟกัสเฉพาะสิ่งที่เปลี่ยนใหม่ใน 20 (§5)

## 4. แผนหลัก — 3 Waves

### Wave 1 — ปิดได้ตอนนี้ (ไม่ติด OCA)

| # | งาน | สถานะ / เกณฑ์ปิด |
|---|---|---|
| 1.1 | `l10n_th_base_sequence` — แก้ 3 จุดเสร็จแล้ว (ISO legends, exception align, env.clear) | ✅ เทสต์ผ่าน เหลือ: เพิ่มเทสต์ครอบ ISO legends + BE year บน 20.0 |
| 1.2 | `l10n_th_promptpay` — fix anchor `provider_credentials` | ✅ เทสต์ผ่าน เหลือ: ถ่ายรูปหน้าจอ form ใหม่สำหรับ `static/description/` (รูปเดิมเป็น 16.0-era) |
| 1.3 | **Sync กลับ upstream** เมื่อ OCA/l10n-thailand เปิด branch 20.0: base_sequence ต้องไปยื่นเป็น `20.0-mig-l10n_th_base_sequence` เพราะเมื่อนั้น OCA copy จะกลับมา **shadow** local copy อีกครั้ง (เหมือนสถานการณ์บน 19.0) — fix ของเราต้องขึ้น PR ก่อน เดี๋ยวแก้ local แล้วเห็นผลนอก | ⏳ gate: OCA เปิด 20.0 |
| 1.4 | สร้าง `odoo-20-migration-guide/` ต่อจาก 19 — ใช้ §5 เป็น seed ของ `migration-rules.yaml` + วิธีเดิม (README/rules/CHECKLIST/CLAUDE 4 ไฟล์อัปเดตพร้อมกัน) | ทำได้เลย |
| 1.5 | `l10n_th_sequence_branch` — ออกแบบ fix ใหม่ล่วงหน้า (ดู §5 ข้อ 1): อ่าน branch code จาก `res.partner.additional_identifiers` scheme `TH_BRANCH_CODE` (core 20 มี `th_branch_code_validate` พร้อม) + เทสต์ prototype | ทำได้เลย — เพราะ logic อยู่ใน `ir.sequence` override ทดสอบแยกได้ แม้โมดูลเต็มยังติด deps |

### Wave 2 (เดิม) — โมดูลของเราที่ติด deps OCA → จะปิดได้เมื่อ Wave 2 (self-migrate) เสร็จ

| โมดูล | ติด OCA อะไร | งานที่เตรียมได้ล่วงหน้า | จุดที่ต้องรีเช็คเมื่อ OCA ตัวจริงมา (rebase) |
|---|---|---|---|
| `l10n_th_account_tax_expense` | `l10n_th_account_tax` | view anchors ฝั่ง hr_expense ตรวจแล้ว ✅ (sheet/group/tax_ids อยู่ครบบน core 20) | hook `_prepare_writeoff_move_line`, `_get_partner_wht_lines/_get_partner_wht`, field `wht_tax_id`, `tax_invoice_ids` — เป็น API ของ OCA เอง ต้องดู signature ใหม่บน 20 |
| `l10n_th_company_novat` | `l10n_th_account_tax` | mixin `base.company.novat` เป็นของเราเอง สะอาด | `map_tax()` signature ของ core 20 (ย้ายไฟล์แล้ว), `account_sale_tax_id/account_purchase_tax_id`, `_get_wht_amount`, `is_pit`, `wht_tax_id` (OCA) |
| `l10n_th_sequence_branch` | `l10n_th_partner`, `l10n_th_base_sequence` | **พังแน่นอนบน 20** — `company_registry` ถูกถอด (§5 ข้อ 1) → ออกแบบผ่าน `additional_identifiers` (Wave 1.5) | จุดเดียว: แหล่งข้อมูล branch code เปลี่ยน |
| `ocaacc` (meta) | OCA Thai 10 โมดูล | ไม่มีโค้ด | gate: ติดตั้งผ่านเมื่อครบ |
| `thaiacc` (meta) | ocaacc + 4 โมดูลข้างบน | ไม่มีโค้ด | gate: สุดท้าย |

### Wave 2 — Self-migrate OCA dependencies (กลยุทธ์ B — อัปเดต 26 ก.ย.)

**การตัดสินใจ:** ไม่รอ OCA — migrate โมดูล OCA ที่ต้องใช้ **ทุกตัวเอง** บน fork branches (`monthop-gmail/*`, branch `20.0-mig-*` พก history ตามวิธี wiki) เพื่อให้ `thaiacc` ใช้งานได้เต็มบน 20 โดยเร็ว เมื่อ OCA ตัวจริงของทีมเดิมมา จะสลับผ่าน `repos.yml` (ถอด merge line ของ fork ทีละ repo) และงานที่ทำไว้บน fork ก็ยื่นเป็น PR ได้ทันทีถ้าต้องการ

> **หลักการสำคัญ:** ทำบน fork branches พร้อม history (ไม่ vendor โค้ดเปล่า ๆ ลง thaiacc-odoo) เพื่อให้ (1) สลับกลับ OCA ได้โดยแก้แค่ repos.yml (2) branch พร้อมยื่น PR ขึ้น OCA ตอน repo เปิด 20.0 (3) ไม่ซ้ำกับกฏ "never vendor unreleased deps" ของทีม

**ผลตรวจวัดจริง (spike) — `date_range` ใช้เวลาไม่ถึงชั่วโมง, 3 commits, โค้ด Python/JS ไม่ต้องแก้เลย:**
1. bump version → 2. แปลง `ir.model.access.csv` → `ir.access.csv` (§5 ข้อ 9) → 3. แปลง `ir.rule` XML → `ir.access` records (§5 ข้อ 10) — เทสต์ 27 cases ผ่านบน Odoo 20
Branch: `20.0-mig-date_range` (ใน clone ของ OCA/server-ux, ยังไม่ push)

**Inventory จริงของ chain (นับจาก source 19.0, เรียงตามลำดับ migration):**

| # | โมดูล | จาก repo | LOC | เทสต์ | หมายเหตุ |
|---|---|---|---|---|---|
| 1 | `date_range` | server-ux | 1,632 | 4 files | ✅ **เสร็จแล้ว** (spike) |
| 2 | `report_xlsx` | reporting-engine | 450 | 1 file | |
| 3 | `report_xlsx_helper` | reporting-engine | 1,132 | 1 file | |
| 4 | `partner_company_type` | partner-contact | 184 | 1 file | ใกล้ตายร้าง — core 20 มี identifier ระบบใหม่ (§5 ข้อ 1) |
| 5 | `partner_firstname` | partner-contact | 1,366 | — | ให้ l10n_th_partner ใช้ |
| 6 | `partner_title` | partner-contact | 403 | — | |
| 7 | `l10n_th_base_utils` | l10n-thailand (OCA 19.0) | 222 | 1 file | |
| 8 | `l10n_th_amount_to_text` | l10n-thailand (OCA 19.0) | 151 | 1 file | |
| 9 | `l10n_th_base_sequence` | l10n-thailand (OCA 19.0) | 337 | 2 files | ✅ แก้แล้วบน branch 20.0 (thaiacc-odoo) — ย้ายไป fork branch ตอนยื่น PR |
| 10 | `l10n_th_account_tax` | l10n-thailand (OCA 19.0) | 5,752 | 3 files | ตัวใหญ่ฝั่งไทย — ภาษี/WHT/PIT |
| 11 | `l10n_th_partner` | fork branch | 430 | 1 file | **ยากสุดเชิง design**: ใช้ `company_registry` เต็มโมดูล + deps `partner_firstname`, `partner_title` |
| 12 | `base_tier_validation` | tier-validation | 4,649 | — | |
| 13 | `base_tier_validation_formula` | tier-validation | 310 | — | |
| 14 | `l10n_th_tier_department` (+demo) | fork branch | 338+276 | 2 files | |
| 15 | `mis_builder` | mis-builder | 9,470 | 16 files | ตัวใหญ่สุด — เผื่อเวลามากหน่อย |
| 16 | `l10n_th_mis_report` | fork branch | 343 | — | ต้องมี mis_builder ก่อน |
| 17 | `l10n_th_account_tax_report` | fork branch | 4,028 | 2 files | ต้องมี date_range + report_xlsx |
| 18 | `l10n_th_account_wht_cert_form` | fork branch | 802 | 1 file | ต้องมี l10n_th_account_tax |
| — | `l10n_th` (ผังบัญชี) | — | — | — | **ไม่ต้อง migrate** — อยู่ใน core 20 แล้ว ("Thailand - Accounting" v2.0) |

รวม ≈ 27,000 LOC / 18 โมดูล เรียงตาม deps แล้ว — หลายตัว (รวม date_range) อาจโค้ดไม่ต้องแก้อะไรเลยนอกจาก security ที่ถูกบังคับเปลี่ยน format

**ข้อควรรู้จากการนับ:** หลายโมดูลไทย (`tax_report`, `wht_cert_form`, `mis_report`, `partner`, `tier_department*`) **ยังไม่ถูก merge ขึ้น OCA 19.0** — อยู่แค่บน fork เป็น PR ค้าง → 20.0 ของเราจะสร้างบน fork branches พวกนั้นต่อไป

**การเชื่อมกลับ thaiacc-odoo:** แก้ `repos.yml` เป็นแบบ `merge: oca 19.0 (ฐานชั่วคราว) + monthop 20.0-mig-<module>` — เมื่อ OCA เปิด 20.0 จริง สลับ `oca 19.0` → `oca 20.0` แล้วถอด fork line ทีละ repo ตามที่ OCA merge

### Wave 3 — OCA upstream (คงเดิม: ประสาน ไม่ทำแทน)

Watch list + สิ่งที่ต้องแจ้งทีม:

| Repo | สถานะ 20.0 (ณ 26 ก.ย.) | ผลต่อเรา |
|---|---|---|
| OCA/l10n-thailand | ไม่มี branch, **ไม่มี issue "Migration to version 20.0"** | กลยุทธ์ B ทำให้ไม่บล็อกเราแล้ว — แต่ควรแจ้งทีมว่าเรา migrate เองบน fork เพื่อเลี่ยงงานซ้ำ/ชน PR |
| OCA/partner-contact | มี branch 20.0 แต่ `partner_company_type` ยังไม่ migrate | เรา migrate เอง (ตาราง Wave 2 #4-6) |
| OCA/server-ux, OCA/tier-validation, OCA/mis-builder, OCA/reporting-engine | ไม่มี branch | เรา migrate เอง (ตาราง Wave 2) |
| OCA/OpenUpgrade | ไม่มี 20.0 | ใช้ diff source เองชั่วคราว |

เมื่อแต่ละ repo เปิด 20.0 → ยก branch ของเราขึ้นเป็น PR ด้วยวิธี wiki (เก็บ history ด้วย format-patch):

```bash
git clone https://github.com/OCA/$repo -b 20.0 && cd $repo
git checkout -b 20.0-mig-$module origin/20.0
git format-patch --keep-subject --stdout origin/20.0..origin/19.0 -- $module | git am -3 --keep
pre-commit run -a   # ignore pylint รอบแรก
git add -A && git commit -m "[IMP] $module: pre-commit auto fixes" --no-verify
# ... แก้ตาม checklist ...
git commit -m "[MIG] $module: Migration to 20.0"
# PR title: "[20.0][MIG] <module>: Migration to 20.0"
```

## 5. กฏ 20.0 เฉพาะ — จากการ migrate จริง (seed ของ odoo-20-migration-guide)

สิ่งที่ตรวจพบเมื่อขึ้น 20 จริง (นอกเหนือจากหน้า wiki ซึ่งยังสั้น):

1. **`res.partner.company_registry` ถูกถอดจาก core** (รวม related บน `res.company`) → ใช้ `res.partner.additional_identifiers` (Json) + `odoo.tools.partner_identifiers` แทน — ข่าวดี: core 20 มี scheme `TH_BRANCH_CODE` (5 หลัก, placeholder `00000`, validate ด้วย `th_branch_code_validate`) และ `TH_VAT` ในตัว → `l10n_th_sequence_branch` ต้องย้ายแหล่งข้อมูล (`%(b1-b5)s` อ่านจาก identifiers ของ company partner)
2. **`--http-interface` default เปลี่ยน `0.0.0.0` → `127.0.0.1`** — container ที่รัน `odoo` ตรง ๆ จะไม่รับ connection ภายนอก (entrypoint ของเราใส่ flag อยู่แล้ว / เพิ่ม `http_interface = 0.0.0.0` ใน odoo.conf ถ้าจำเป็น)
3. **`env.clear()` deprecated** → `env.transaction.clear()` (clear cache + tocompute + cached properties) หรือ `env.transaction.reset()` (หลัง commit/rollback เท่านั้น)
4. **payment provider form**: `<group name="payment_form">` ถูกถอด → anchor ใหม่ที่แนะนำ `provider_credentials` / `provider_config*` บนหน้า Configuration
5. **website_sale templates ย้ายโฟลเดอร์**: `views/*.xml` → `templates/**` (เช่น confirmation ไปที่ `templates/checkout/confirmation_templates.xml`) — xml id เดิม (`website_sale.confirmation`, `payment_confirmation_status`) ยังอยู่ครบ xpath เดิมยัง match
6. **`ir.sequence`**: `_get_prefix_suffix(date, date_range)` signature คงเดิม (override ของเรายังใช้ได้); core เพิ่ม legends `isoyear/isoy/isoweek` — โมดูลที่ replace dict ต้องพกต่อ; core เพิ่ม guard `if not seq.id` ใน `_get_number_next_actual`
7. ยังไม่เปลี่ยน (เช็คแล้ว): `hr.expense._prepare_move_lines_vals`, `account.move._post(soft=True)`, `payment.payment_provider_transfer`, `qr_code` field บน payment_custom, `get_portal_last_transaction`, test helper `freeze_time`
8. Docker: ตอน release week ยังไม่มี `odoo:20` บน Docker Hub — build เองจาก [odoo/docker 20.0](https://github.com/odoo/docker/tree/master/20.0) + nightly deb (เช็ค sha1 ที่ประกาศใน Dockerfile)
9. **ระบบ security ใหม่ทั้งชุด (ผลกระทบกว้างสุด): model `ir.model.access` ถูกแทนด้วย `ir.access`** — loader อนุมาน model จากชื่อไฟล์ CSV ดังนั้น `ir.model.access.csv` เดิมตายทันที (`KeyError: 'ir.model.access'`); format ใหม่: ชื่อไฟล์ `ir.access.csv`, column `id,name,model_id,group_id/id,operation,domain` โดย 4 boolean เดิม (`perm_read/write/create/unlink`) รวมเป็น `operation` แบบ subset ของ `crud` (เช่น `r`, `ru`, `crud`), และ `model_id` อ้างด้วย **ชื่อ model** (`date.range`) ไม่ใช่ xml-id (`model_date_range`)
10. **`ir.rule` ถูกยุบรวมเข้า `ir.access` ด้วย** — row ที่ *ไม่ระบุ group* = `kind=restriction` (ทำหน้าที่ record rule เดิม, ใช้ field `domain` ไม่ใช่ `domain_force`), row ที่ระบุ group = `kind=permission` (ACL) — แปลง multi-company rule เป็น row แบบ global + `operation=crud` + domain เดิม
    - ตัวช่วย: converter แปลง `ir.model.access.csv` → `ir.access.csv` อัตโนมัติ (อ่าน `_name` จาก `*.py` ของโมดูลมา map model_id; อยู่ในคอมเมนต์ session 26 ก.ย. — ควรเก็บเป็น script ใน odoo-20-migration-guide ตอนทำ 1.4)

**ห้ามทำ** (จากหน้า wiki 20.0): แก้ copyright year, แก้ original authors, squash commit จริง (มีแต่ bot/Weblate commits)

## 6. เกณฑ์ (gates) ต่อโมดูลก่อนถือว่าปิด

1. ติดตั้งบน db ใหม่ด้วย `run_install_test.sh <module>` ผ่าน + เทสต์ของโมดูลผ่าน (0 failed)
2. `--test-tags /<module>` รันแยกอีกรอบผ่าน (ตาม workflow เดิมใน CLAUDE.md)
3. เปิดหน้าจอหลักของโมดูลบน UI ได้ (view ไม่ตายตอน render)
4. pre-commit ของ OCA ผ่าน (เฉพาะตอนยื่น PR ฝั่ง OCA)
5. Manual test ตาม `TESTING.md` — รอบสุดท้ายหลัง `thaiacc` ติดตั้งได้เต็ม

## 7. ประมาณการ (rough) — อัปเดตหลัง spike date_range

- Wave 1: เกือบเสร็จ — เหลือเทสต์เสริม + guide + prototype sequence_branch ≈ 1-2 วัน
- Wave 2 (self-migrate): ก้อนเล็ก (ACL/rule แปลงเป็นหลัก, โค้ดไม่แก้) ≈ 2-3 ตัว/วัน — ก้อนใหญ่ (`l10n_th_account_tax` 5.7k LOC, `mis_builder` 9.5k LOC, `base_tier_validation` 4.6k LOC) เผื่อ 1-3 วัน/ตัว — รวมคาด ≈ 2-3 สัปดาห์ ทำไล่ตามตารางลำดับ
- ข้อดีของกลยุทธ์ B: ไม่ขึ้นกับความเร็ว OCA อีกต่อไป; ข้อเสีย: ถ้า OCA ตัวจริงมา design ต่างจากเรา (โดยเฉพาะ `company_registry`/branch code) ต้อง rebase โมดูลเราบางตัว

## 8. คำถามที่ต้องตัดสินใจ — อัปเดต

1. ~~ถ้า OCA ช้าจะทำไง~~ → **ตัดสินใจแล้ว: กลยุทธ์ B (self-migrate บน fork branches)** — เหลือเพียง: แจ้งทีม l10n-thailand ว่าเรา migrate เอง เพื่อกันงานซ้ำ/ชน PR กัน
2. เมื่อ OCA เปิด 20.0: ยก fork branches ขึ้นเป็น PR จริงไหม (แนะนำ: ใช่ — เหมือนที่ทำบน 19.0)
3. `l10n_th_promptpay` จะยื่นขึ้น OCA 20.0 ไหม (ตอนนี้โค้ดอยู่ local มาตั้งแต่ 17 — จะส่งกลับต้องพก history หลาย version ตามกฏ)
