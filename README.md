# ThaiACC — โมดูลบัญชีไทยสำหรับ Odoo 20 (official-first)

ThaiACC บน Odoo 20 สร้างตามสถาปัตยกรรม **official-first**: ใช้โมดูล official ของ Odoo 20 (`l10n_th`, WHT engine, tax invoice) เป็นหลัก แล้วเสริมเฉพาะช่องว่างของไทยด้วยโมดูลของ ThaiACC — สถานะและรายละเอียดดูที่ [MIGRATION-20.0.md](MIGRATION-20.0.md)

## Quick Start (GitHub Codespaces)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/monthop-gmail/thaiacc-odoo?ref=20.0)

1. กดปุ่มด้านบน หรือไปที่ **Code > Codespaces > Create codespace on 20.0**
2. รอ build (~3-5 นาที) — ระบบจะ start Odoo 20 + PostgreSQL และติดตั้ง `l10n_th` official ให้อัตโนมัติ (โปรไฟล์ official-only; โปรไฟล์ aggregate เดิมยังอยู่ผ่าน `THAIACC_PROFILE=aggregate`)
3. เปิด browser ที่ port 8069 — พร้อมใช้งาน!
4. Login: **admin / admin**

> ไม่ต้องพิมพ์ command เพิ่มเติม — ทุกอย่างถูกจัดการผ่าน docker-in-docker โดยอัตโนมัติ

## ติดตั้งด่วน

| โมดูล | สิ่งที่ได้ |
|--------|-----------|
| **thaiacc** | ทุกอย่างด้านล่างในคลิกเดียว (แนะนำ) |
| **ocaacc** | เฉพาะโมดูลหลัก OCA Thai เท่านั้น |

## เปรียบเทียบ ocaacc vs thaiacc

| ฟีเจอร์ | ocaacc | thaiacc |
|---------|:---------:|:-------:|
| **โมดูลหลัก OCA** | | |
| ผังบัญชีไทย (l10n_th) | :white_check_mark: | :white_check_mark: |
| ภาษีซื้อ/ขาย + ใบกำกับภาษี (l10n_th_account_tax) | :white_check_mark: | :white_check_mark: |
| รายงานภาษี (l10n_th_account_tax_report) | :white_check_mark: | :white_check_mark: |
| หนังสือรับรองหัก ณ ที่จ่าย (l10n_th_account_wht_cert_form) | :white_check_mark: | :white_check_mark: |
| แปลงจำนวนเงินเป็นตัวอักษรไทย (l10n_th_amount_to_text) | :white_check_mark: | :white_check_mark: |
| เลขที่เอกสาร พ.ศ./ไตรมาส (l10n_th_base_sequence) | :white_check_mark: | :white_check_mark: |
| ฟอนต์ไทย + ยูทิลิตี้ (l10n_th_base_utils) | :white_check_mark: | :white_check_mark: |
| รายงาน MIS (l10n_th_mis_report) | :white_check_mark: | :white_check_mark: |
| ข้อมูลคู่ค้าไทย สาขา/สำนักงานใหญ่ (l10n_th_partner) | :white_check_mark: | :white_check_mark: |
| อนุมัติตามแผนก (l10n_th_tier_department) | :white_check_mark: | :white_check_mark: |
| **โมดูลเสริม** | | |
| ใบกำกับภาษี + WHT บน Expense (l10n_th_account_tax_expense) | | :white_check_mark: |
| ตั้งค่าบริษัท จด/ไม่จด VAT (l10n_th_company_novat) | | :white_check_mark: |
| เลขที่เอกสารตามสาขา (l10n_th_sequence_branch) | | :white_check_mark: |
| QR Code พร้อมเพย์ (l10n_th_promptpay) | | :white_check_mark: |
| **รวม** | **10 โมดูล** | **14 โมดูล** |

## รายชื่อโมดูล

### โมดูลเสริม (รวมอยู่ใน thaiacc)

| โมดูล | รายละเอียด | Migrate จาก |
|--------|-----------|-------------|
| **l10n_th_account_tax_expense** | ใบกำกับภาษีค่าใช้จ่าย + ภาษีหัก ณ ที่จ่ายบน Expense | PR #498 (18.0) |
| **l10n_th_company_novat** | ตั้งค่าบริษัท/คู่ค้า จด/ไม่จด VAT, บล็อคภาษีสำหรับบริษัทไม่จด VAT | OCA 14.0 |
| **l10n_th_base_sequence** | เลขที่เอกสาร: พ.ศ., ไตรมาส, ช่วงวันที่ | monthop fork 19.0 |
| **l10n_th_sequence_branch** | เลขที่เอกสารตามสาขาบริษัท `%(b1-b5)s` | OCA 14.0 |
| **l10n_th_promptpay** | QR Code พร้อมเพย์บนหน้าชำระเงิน Website | OCA 16.0 |

### โมดูล OCA ที่ต้องใช้ (ดึงผ่าน gitaggregate)

ดึงจาก OCA repositories โดยใช้ `repos.yml`:

| Repo | โมดูลหลัก | Fork |
|------|----------|------|
| [l10n-thailand](https://github.com/OCA/l10n-thailand) | l10n_th_account_tax, l10n_th_partner, l10n_th_mis_report, ... | [monthop-gmail](https://github.com/monthop-gmail/l10n-thailand) |
| [partner-contact](https://github.com/OCA/partner-contact) | partner_company_type | [monthop-gmail](https://github.com/monthop-gmail/partner-contact) |
| [server-ux](https://github.com/OCA/server-ux) | base_tier_validation | [monthop-gmail](https://github.com/monthop-gmail/server-ux) |
| [mis-builder](https://github.com/OCA/mis-builder) | mis_builder | [versada](https://github.com/versada/mis-builder) |
| [reporting-engine](https://github.com/OCA/reporting-engine) | report_xlsx, report_xlsx_helper | OCA (upstream) |

## วิธีติดตั้ง

### วิธี A: GitHub Codespaces (แนะนำ)

กดปุ่ม **Code > Codespaces > Create codespace on 20.0** บน GitHub แล้วรอ — ได้ Odoo 20 + PostgreSQL + `l10n_th` official พร้อมใช้เลย ไม่ต้องพิมพ์ command เพิ่มเติม

เปิด browser ที่ port 8069 → Login: **admin / admin**

### วิธี B: ติดตั้งเองด้วย gitaggregate

```bash
# Clone repo นี้
git clone -b 20.0 https://github.com/monthop-gmail/thaiacc-odoo.git
cd thaiacc-odoo

# ติดตั้ง gitaggregate แล้วดึง OCA dependencies
pip install git-aggregator promptpay
gitaggregate -c repos.yml

# เพิ่มใน addons_path ใน odoo.conf:
addons_path = /path/to/thaiacc-odoo,/path/to/thaiacc-odoo/l10n-thailand,/path/to/thaiacc-odoo/partner-contact,/path/to/thaiacc-odoo/server-ux,/path/to/thaiacc-odoo/mis-builder,/path/to/thaiacc-odoo/reporting-engine
```

### วิธี C: Docker Compose (สำหรับทดสอบ)

```bash
git clone -b 20.0 https://github.com/monthop-gmail/thaiacc-odoo.git
cd thaiacc-odoo
docker compose up -d --build
```

Odoo จะ start พร้อม OCA dependencies อัตโนมัติผ่าน entrypoint — เปิด browser: `http://localhost:8069`

ดูคู่มือทดสอบฉบับเต็มที่ **[TESTING.md](TESTING.md)** — มี demo data, เมนูที่ต้องไป, และรายการทดสอบ WHT ครบ

## สถานะการ Migrate

### เสร็จแล้ว (อยู่ใน repo นี้)

- [x] l10n_th_account_tax_expense (Part 1: ใบกำกับภาษี + ภาษีหัก ณ ที่จ่าย)
- [x] l10n_th_company_novat
- [x] l10n_th_base_sequence
- [x] l10n_th_sequence_branch
- [x] l10n_th_promptpay
- [x] thaiacc (meta-package)

### รอดำเนินการ

- [ ] l10n_th_account_tax_expense Part 2 (สร้าง JV ภาษีหัก ณ ที่จ่ายสำหรับเคลียร์เงินทดรอง) — รอ `hr_expense_advance_clearing` บน 19.0
- [ ] l10n_th_google_fonts — มีเฉพาะ third-party ไม่อยู่ใน OCA

### ไม่ต้องทำ (รวมอยู่ในโมดูล OCA แล้ว)

- ~~l10n_th_sequence_be~~ → รวมเข้า `l10n_th_base_sequence` แล้ว
- ~~l10n_th_sequence_preview~~ → รวมเข้า `l10n_th_base_sequence` แล้ว
- ~~l10n_th_sequence_qoy~~ → รวมเข้า `l10n_th_base_sequence` แล้ว
- ~~l10n_th_sequence_range_end~~ → รวมเข้า `l10n_th_base_sequence` แล้ว
- ~~l10n_th_expense_tax_invoice~~ → รวมเข้า `l10n_th_account_tax_expense` แล้ว
- ~~l10n_th_expense_withholding_tax~~ → รวมเข้า `l10n_th_account_tax_expense` แล้ว
- ~~l10n_th_fonts~~ → ถูกแทนที่ด้วย `l10n_th_base_utils`

## สัญญาอนุญาต

- **ocaacc**, **thaiacc**: [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html)
- **โมดูลอื่นทั้งหมด**: [AGPL-3](https://www.gnu.org/licenses/agpl-3.0.html)

## เครดิต

- [Ecosoft Co., Ltd](https://ecosoft.co.th/) — ผู้พัฒนาโมดูลต้นฉบับ
- ผู้ร่วมพัฒนา [OCA/l10n-thailand](https://github.com/OCA/l10n-thailand)
- [OCA ACC](https://sumana.online) — migrate และจัดแพ็คเกจสำหรับ Odoo 19
