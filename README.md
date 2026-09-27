# ThaiACC — โมดูลบัญชีไทยสำหรับ Odoo 20 (official-first)

ThaiACC บน Odoo 20 สร้างตามสถาปัตยกรรม **official-first**: ใช้โมดูล official ของ Odoo 20 เป็นหลัก (`l10n_th` ผังบัญชีไทย, ใบกำกับภาษี, WHT engine, 50 ต.ว., PromptPay QR — มีใน core ทั้งหมด) แล้วเสริมเฉพาะช่องว่างของไทยที่ official ยังไม่ครอบคลุมด้วยโมดูลของ ThaiACC

> สถานะล่าสุด, สถาปัตยกรรม และนโยบาย bridge: [MIGRATION-20.0.md](MIGRATION-20.0.md) ·
> กฏ migration รวมทุกเวอร์ชัน: [odoo-migration-guide](https://github.com/monthop-gmail/odoo-migration-guide)

## Quick Start (GitHub Codespaces)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/monthop-gmail/thaiacc-odoo?ref=20.0)

1. กดปุ่มด้านบน หรือไปที่ **Code > Codespaces > Create codespace on 20.0**
2. รอ build (~3-5 นาที) — ระบบจะ start Odoo 20 + PostgreSQL และติดตั้ง `l10n_th` official ให้อัตโนมัติ (โปรไฟล์ official-only)
3. เปิด browser ที่ port 8069 — พร้อมใช้งาน!
4. Login: **admin / admin**

## โครงสร้างชุดโมดูลบน 20.0

| Meta package | ครอบคลุม |
|---|---|
| **`ocaacc`** — Official Thai Accounting Essentials | ตัวเดียวจบ: ติดตั้ง `l10n_th` (core) = ผังบัญชีไทย, ใบกำกับภาษีขาย + รอบการจ่าย, ภาษีหัก ณ ที่จ่ายผ่าน `account.tax.is_withholding_tax`, รายงาน 50 ต.ว., PromptPay EMV QR |
| **`thaiacc`** — Thai Accounting Complete Suite | ocaacc + โมดูลช่องว่างไทยทั้งหมดของ ThaiACC (ตารางด้านล่าง) — แนะนำ |

### โมดูลของ ThaiACC บน 20.0 (ช่องว่างที่ official ไม่มี)

| โมดูล | สิ่งที่เสริม |
|---|---|
| **l10n_th_purchase_tax_invoice** | ใบกำกับภาษีซื้อ: บันทึกเลขที่/วันที่ต้นฉบับของ vendor + ใบกำกับภาษีซื้อตอนจ่ายเงิน (input VAT แบบ on-payment) — official ทำเฉพาะฝั่งขาย |
| **l10n_th_wht_defaults** | ค่าเริ่มต้นภาษีหัก ณ ที่จ่ายรายสินค้า (Default WHT) สำหรับ vendor bill |
| **l10n_th_pit** | ภาษีหัก ณ ที่จ่ายแบบขั้นบันได (บุคคลธรรมดา) — ตารางอัตรารายปี + คำนวณแบบ marginal บน official WHT engine |
| **l10n_th_pnd_report** | รายงาน ภ.ง.ด.1/1ก/2/3/53 แบบ normalized จากข้อมูลหัก ณ ที่จ่ายจริง |
| **l10n_th_base_sequence** | เลขที่เอกสาร พ.ศ./ไตรมาส/ช่วงวันที่ |
| **l10n_th_promptpay** | QR Code พร้อมเพย์บน provider แบบโอนเงิน |

ยังไม่อยู่ในชุด 20.0 (รอ OCA bridge — ตารางใน MIGRATION-20.0.md §4): `l10n_th_company_novat`, `l10n_th_sequence_branch`, `l10n_th_account_tax_expense`

## วิธีติดตั้ง

### วิธี A: Docker Compose (แนะนำ)

```bash
git clone -b 20.0 https://github.com/monthop-gmail/thaiacc-odoo.git
cd thaiacc-odoo
docker compose up -d --build
```

`THAIACC_PROFILE=official` (ค่าเริ่มต้น) จะ boot Odoo 20 + PostgreSQL และติดตั้ง `l10n_th` + `thaiacc`-local modules โดยไม่ต้องดึง OCA ใด ๆ — ติดตั้งใหม่ไม่ต้องรอ migration

โปรไฟล์เดิม (gitaggregate + fail-loud protections) ยังใช้ได้ผ่าน `THAIACC_PROFILE=aggregate` — ใช้เมื่อต้องการ bridge modules

### วิธี B: GitHub Codespaces

กดปุ่มด้านบน — เหมือนวิธี A ทุกอย่าง

> หมายเหตุ: ณ release week ของ Odoo 20 Docker Hub อาจยังไม่มี tag `odoo:20.0` — กรณีนั้น build image เองจาก [odoo/docker](https://github.com/odoo/docker/tree/master/20.0) + nightly deb (เช็ค sha1 ใน Dockerfile)

### รันชุดทดสอบ

```bash
# smoke tests ของ official l10n_th + capability checks
docker compose exec odoo bash /workspace/test/official_smoke_test.sh

# ติดตั้ง + รันเทสต์โมดูลใด ๆ บน db ใหม่ (DEMO=1 เพื่อโหลด demo data)
DEMO=1 bash test/run_install_test.sh ocaacc thaiacc
```

## สถานะ: E20-001→006 สำเร็จครบ (27 ก.ย. 2026)

บน build `20.0.20260926`: 24 โมดูลเทสต์ของ ThaiACC + official `l10n_th` regression 15/15 — เขียวหมด รายละเอียด slice-by-slice พร้อม commit refs อยู่ใน [MIGRATION-20.0.md](MIGRATION-20.0.md) §1

งานที่เหลือ (Later bucket, รอทิศทาง): utility OCA bridge packaging, ThaiACC extras, expense redesign, full 19→20 data migration, upstream convergence automation

## เส้นทาง 18/19/20

ตามนโยบายข้ามเวอร์ชันของทีม: branch `18.0`/`19.0` = stable/maintenance (bug + compliance fixes), branch `20.0` = official-first future architecture — feature ใหม่ออกแบบบน 20 ก่อนแล้ว backport เฉพาะความจำเป็น

## สัญญาอนุญาต

- **ocaacc**, **thaiacc**: [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html)
- **โมดูลอื่นทั้งหมด**: [AGPL-3](https://www.gnu.org/licenses/agpl-3.0.html)

## เครดิต

- [Ecosoft Co., Ltd](https://ecosoft.co.th/) — ผู้พัฒนาโมดูลต้นฉบับ
- ผู้ร่วมพัฒนา [OCA/l10n-thailand](https://github.com/OCA/l10n-thailand)
- [OCA ACC](https://sumana.online) — migrate และจัดแพ็คเกจสำหรับ Odoo 19 และสถาปัตยกรรม official-first บน Odoo 20
