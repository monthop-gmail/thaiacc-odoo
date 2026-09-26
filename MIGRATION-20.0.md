# ThaiACC — แผน Migration สู่ Odoo 20.0

จัดทำ: 2026-09-26 (วัน release ของ Odoo 20.0-20260926)
เป้าหมาย: migrate โมดูลทั้งหมดของ thaiacc ขึ้น Odoo 20 ตามกฏของ [OCA maintainer-tools](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-20.0)

---

## 1. กฏที่ใช้ (แหล่งอ้างอิง)

| แหล่ง | ใช้ทำอะไร |
|---|---|
| [OCA wiki — Migration to version 20.0](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-20.0) | ขั้นตอน process: branch naming, วิธีพก history, commit/PR conventions, สิ่งที่ **ห้าม** ทำ |
| [OCA wiki — Migration to version 19.0](https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-19.0) | Checklist framework changes — เราผ่านมาแล้วตอน migrate 19.0 (ผล scan §3) ใช้เป็น **regression checklist** ย้ำตอนรีวิว PR |
| `odoo-19-migration-guide/` (repo ของทีม) | Workflow scan → auto-fix → validate ตาม `migration-rules.yaml` — จะต่อยอดเป็น odoo-20-migration-guide (§5) |
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

### Wave 2 — เตรียมล่วงหน้า + ปิดเมื่อ OCA 20.0 มา

| โมดูล | ติด OCA อะไร | งานที่เตรียมได้ล่วงหน้า | จุดที่ต้องรีเช็คเมื่อ OCA 20.0 มา |
|---|---|---|---|
| `l10n_th_account_tax_expense` | `l10n_th_account_tax` | view anchors ฝั่ง hr_expense ตรวจแล้ว ✅ (sheet/group/tax_ids อยู่ครบบน core 20) | hook `_prepare_writeoff_move_line`, `_get_partner_wht_lines/_get_partner_wht`, field `wht_tax_id`, `tax_invoice_ids` — เป็น API ของ OCA เอง ต้องดู signature ใหม่บน 20 |
| `l10n_th_company_novat` | `l10n_th_account_tax` | mixin `base.company.novat` เป็นของเราเอง สะอาด | `map_tax()` signature ของ core 20 (ย้ายไฟล์แล้ว), `account_sale_tax_id/account_purchase_tax_id`, `_get_wht_amount`, `is_pit`, `wht_tax_id` (OCA) |
| `l10n_th_sequence_branch` | `l10n_th_partner`, `l10n_th_base_sequence` | **พังแน่นอนบน 20** — `company_registry` ถูกถอด (§5 ข้อ 1) → ออกแบบผ่าน `additional_identifiers` (Wave 1.5) | จุดเดียว: แหล่งข้อมูล branch code เปลี่ยน |
| `ocaacc` (meta) | OCA Thai 10 โมดูล | ไม่มีโค้ด | gate: ติดตั้งผ่านเมื่อครบ |
| `thaiacc` (meta) | ocaacc + 4 โมดูลข้างบน | ไม่มีโค้ด | gate: สุดท้าย |

### Wave 3 — OCA upstream (ทีม l10n-thailand ตามอยู่ — เรา track ไม่ทำ)

Watch list + สิ่งที่ต้องแจ้งทีม:

| Repo | สถานะ 20.0 (ณ 26 ก.ย.) | ผลต่อเรา |
|---|---|---|
| OCA/l10n-thailand | ไม่มี branch, **ไม่มี issue "Migration to version 20.0"** | บล็อกทุกอย่างใน Wave 2 — ทีมควรเปิด issue ประกาศก่อน (ตามกฏ OCA "Before migrating") |
| OCA/partner-contact | มี branch 20.0 แต่ `partner_company_type` ยังไม่ migrate | บล็อก `l10n_th_partner` ต่อ ๆ ไป |
| OCA/server-ux, OCA/tier-validation, OCA/mis-builder, OCA/reporting-engine | ไม่มี branch | `date_range`/`base_tier_validation`/`mis_builder`/`report_xlsx` |
| OCA/OpenUpgrade | ไม่มี 20.0 | ใช้ diff source เองชั่วคราว |

เมื่อแต่ละ repo เปิด 20.0 → ใช้วิธีของ wiki (เก็บ history ด้วย format-patch):

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

**ห้ามทำ** (จากหน้า wiki 20.0): แก้ copyright year, แก้ original authors, squash commit จริง (มีแต่ bot/Weblate commits)

## 6. เกณฑ์ (gates) ต่อโมดูลก่อนถือว่าปิด

1. ติดตั้งบน db ใหม่ด้วย `run_install_test.sh <module>` ผ่าน + เทสต์ของโมดูลผ่าน (0 failed)
2. `--test-tags /<module>` รันแยกอีกรอบผ่าน (ตาม workflow เดิมใน CLAUDE.md)
3. เปิดหน้าจอหลักของโมดูลบน UI ได้ (view ไม่ตายตอน render)
4. pre-commit ของ OCA ผ่าน (เฉพาะตอนยื่น PR ฝั่ง OCA)
5. Manual test ตาม `TESTING.md` — รอบสุดท้ายหลัง `thaiacc` ติดตั้งได้เต็ม

## 7. ประมาณการ (rough)

- Wave 1: เกือบเสร็จ — เหลือเทสต์เสริม + guide + prototype sequence_branch ≈ 1-2 วัน
- Wave 2: ต่อโมดูล ≈ 0.5-2 วัน **หลัง** OCA ของจริงมา (ไม่นับรอ)
- ปัจจัยนอกเหนือการควบคุม: ความเร็วของ OCA 20.0 migration ทั้ง 6 repos

## 8. คำถามที่ต้องตัดสินใจ

1. ใครเปิด/แจ้ง issue "Migration to version 20.0" ใน OCA/l10n-thailand (ประสานทีมที่ตามอยู่)
2. ถ้า OCA ช้าแล้วต้องการใช้งานจริงก่อน — จะ vendor ชั่วคราวบน repo เรา (ได้ แต่ต้องระวัง shadow เวลา OCA มา) หรือรอ? (กฏห้าม vendor ใช้เฉพาะ PR ฝั่ง OCA)
3. `l10n_th_promptpay` จะยื่นขึ้น OCA 20.0 ไหม (ตอนนี้โค้ดอยู่ local มาตั้งแต่ 17 — จะส่งกลับต้องพก history หลาย version ตามกฏ)
