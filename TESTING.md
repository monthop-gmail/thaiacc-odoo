# ThaiACC - คู่มือทดสอบ

> Branch `20.0` (Odoo 20, official-only baseline): รันชุดทดสอบอัตโนมัติได้ด้วย `test/official_smoke_test.sh` และ `test/run_install_test.sh <modules>`; สถานะ E20 ดูที่ MIGRATION-20.0.md — ส่วนด้านล่างเป็นคู่มือทดสอบ manual ของชุด 19.0 เดิม


## สถานะการติดตั้ง

| รายการ | สถานะ |
|--------|--------|
| Odoo 19.0 | OK |
| PostgreSQL 16 | OK |
| OCA Dependencies (gitaggregate) | OK |
| ThaiACC Modules (107 modules) | OK |
| Demo Data (vendors, WHT rates, products) | OK |

---

## วิธี Start ระบบทดสอบ

### วิธี A: GitHub Codespaces (แนะนำ)

1. กดปุ่ม **Code > Codespaces > Create codespace on 19.0** บน GitHub
2. รอ build (~3-5 นาที) — ทุกอย่างจะ start อัตโนมัติ
3. เปิด browser ที่ port 8069 → Login: **admin / admin**

### วิธี B: Docker Compose (Local)

```bash
git clone -b 19.0 https://github.com/monthop-gmail/thaiacc-odoo.git
cd thaiacc-odoo
docker compose up -d --build
```

รอประมาณ 2-3 นาที — `entrypoint.sh` จะ:
1. ดึง OCA dependencies ด้วย gitaggregate (ถ้ายังไม่มี)
2. Start Odoo พร้อม addons-path ที่ถูกต้อง

ดู log:
```bash
docker compose logs -f odoo
```

### เปิดใช้งาน

- **URL:** http://localhost:8069
- **Database:** thaiacc
- **Username:** admin
- **Password:** admin

---

## Demo Data ที่มีให้ทดสอบ

ติดตั้งด้วย `--without-demo=False` จะได้ข้อมูลตัวอย่างพร้อมใช้:

### จาก ocaacc

| ประเภท | รายการ |
|--------|--------|
| **Vendor ไทย** | บจก.สมชาย เทรดดิ้ง (0105560123456), หจก.รุ่งเรือง (0103560789012), นายวิชัย ใจดี (1234567890123) |
| **Customer ไทย** | บมจ.ลูกค้าไทย (0107550345678) |
| **บัญชี WHT** | 215300 ภาษีหัก ณ ที่จ่ายค้างจ่าย |
| **อัตรา WHT** | 1% ขนส่ง, 2% โฆษณา, 3% บริการ (PND53+PND3), 5% เช่า, PIT เงินเดือน |
| **Products** | ค่าที่ปรึกษา (10,000), ค่าเช่าสำนักงาน (25,000), ค่าขนส่ง (5,000), ค่าโฆษณา (15,000) |

### จาก thaiacc (เพิ่มเติม)

| ประเภท | รายการ |
|--------|--------|
| **Vendor ไม่จด VAT** | ร้านป้าแก้ว ขายของชำ (novat=True) |
| **Products สำหรับ Expense** | ค่าซ่อมบำรุง (8,000), ค่าจัดส่งพัสดุ (1,500) |

---

## Modules ที่ติดตั้ง (ThaiACC + OCA)

| Module | ชื่อ | หมายเหตุ |
|--------|------|----------|
| `thaiacc` | ThaiACC - Thai Accounting Complete Suite | Meta-package ติดตั้งทุกอย่าง |
| `ocaacc` | OCA ACC - Thai Accounting Suite | OCA modules รวม |
| `l10n_th` | Thai - Accounting | ผังบัญชีไทย |
| `l10n_th_account_tax` | Thai Localization - Tax | ภาษีซื้อ/ขาย + WHT |
| `l10n_th_account_tax_report` | Thai Localization - Tax Report | รายงานภาษี + WHT |
| `l10n_th_account_wht_cert_form` | Thai Localization - WHT Certificate Form | แบบฟอร์มหนังสือรับรองหัก ณ ที่จ่าย |
| `l10n_th_account_tax_expense` | Thai Localization - Expense Tax | ภาษี/WHT บน Expense |
| `l10n_th_company_novat` | Thai Localization - Company/Partner NOVAT | บริษัทไม่จด VAT |
| `l10n_th_partner` | Thai Localization - Partner | ข้อมูล Partner ไทย |
| `l10n_th_amount_to_text` | Thai Localization - Amount to Text | แปลงจำนวนเงินเป็นภาษาไทย |
| `l10n_th_base_utils` | Thai Localization - Base Utils | ฟอนต์ไทย + utilities |
| `l10n_th_base_sequence` | Thai Localization - Base Sequence | เลขลำดับ (พ.ศ., ไตรมาส ฯลฯ) |
| `l10n_th_sequence_branch` | Thai Localization - Sequence with Branch | เลขลำดับแยกสาขา |
| `l10n_th_mis_report` | Thai Localization - MIS Report | งบการเงิน MIS |
| `l10n_th_tier_department` | Thai Localization - Tier Department | ระบบอนุมัติตามแผนก |
| `l10n_th_promptpay` | Thai Localization - PromptPay | QR Code พร้อมเพย์ |
| `report_xlsx` / `report_xlsx_helper` | XLSX Reports | รายงาน Excel |
| `base_tier_validation` | Base Tier Validation | ระบบอนุมัติหลายระดับ |
| `mis_builder` | MIS Builder | เครื่องมือสร้างงบการเงิน |
| `partner_company_type` | Partner Company Type | ประเภทบริษัท |

---

## รายการทดสอบ: รายงานหัก ณ ที่จ่าย (WHT)

> **หมายเหตุ:** Odoo Community ใช้เมนู **Invoicing** (ไม่ใช่ Accounting)

### Test 1: เข้าถึงเมนูรายงาน WHT

1. ไปที่ **Invoicing > Reporting > Thai Accounting Reports > WHT Income Tax Report**
2. ตรวจสอบว่า wizard แสดงขึ้นมา
3. เลือกประเภทรายงาน: ภ.ง.ด.1, ภ.ง.ด.1ก, ภ.ง.ด.2, ภ.ง.ด.3, ภ.ง.ด.53
4. กด Print

### Test 2: สร้าง Vendor Bill พร้อมหัก ณ ที่จ่าย (ใช้ demo data)

1. ไปที่ **Invoicing > Vendors > Bills**
2. สร้าง Bill ใหม่ เลือก Vendor: **บริษัท สมชาย เทรดดิ้ง จำกัด**
3. เพิ่ม Product: **ค่าที่ปรึกษา** (10,000 บาท) — WHT 3% จะถูกตั้งให้อัตโนมัติ
4. Confirm bill
5. ลงทะเบียนจ่ายเงิน (Register Payment)
6. ตรวจสอบว่า WHT Certificate ถูกสร้างอัตโนมัติ

### Test 3: พิมพ์หนังสือรับรองหัก ณ ที่จ่าย

1. ไปที่ **Invoicing > Vendors > WHT Certificates**
2. เปิด WHT Certificate ที่สร้างจาก Test 2
3. กดปุ่ม **Print > WHT Certificates (pdf)**
4. ตรวจสอบแบบฟอร์มว่าข้อมูลถูกต้อง (ชื่อ, เลขประจำตัวผู้เสียภาษี, จำนวนเงิน)

### Test 4: รายงาน WHT Excel

1. ไปที่ **Invoicing > Reporting > Thai Accounting Reports > WHT Income Tax Report**
2. เลือกช่วงเวลาและประเภทรายงาน
3. กด **Export XLSX**
4. ตรวจสอบไฟล์ Excel ที่ดาวน์โหลด

### Test 5: WHT บน Expense (ใช้ demo data)

1. ไปที่ **Expenses > My Expenses**
2. สร้าง Expense ใหม่ เลือก Product: **ค่าซ่อมบำรุง** (8,000 บาท)
3. กรอก Tax Details: Vendor = **บจก.สมชาย**, เลขที่ใบกำกับภาษี, วันที่
4. Withholding Tax จะถูกตั้งให้อัตโนมัติ (WHT 3%)
5. Submit > Approve > Post Journal Entry
6. ตรวจสอบว่ามี WHT line ใน Journal Entry

### Test 6: ทดสอบ Vendor ไม่จด VAT

1. สร้าง Vendor Bill เลือก Vendor: **ร้านป้าแก้ว ขายของชำ** (novat=True)
2. ตรวจสอบว่าระบบไม่ใส่ภาษีซื้อให้
3. ถ้าบริษัทตั้งค่า novat=True ด้วย ระบบจะ block การใส่ภาษี

### Test 7: รายงานภาษีซื้อ/ขาย

1. ไปที่ **Invoicing > Reporting > Thai Accounting Reports > Thai Tax Report**
2. เลือกช่วงเวลา
3. กด View / Export PDF / Export XLSX

---

## เมนูหลักทั้งหมดที่เกี่ยวข้อง

| เมนู | ใช้ทำอะไร |
|------|----------|
| **Invoicing > Vendors > Bills** | สร้าง Vendor Bill พร้อม WHT |
| **Invoicing > Vendors > WHT Certificates** | ดู/พิมพ์หนังสือรับรองหัก ณ ที่จ่าย |
| **Invoicing > Reporting > Thai Accounting Reports > WHT Income Tax Report** | รายงาน ภ.ง.ด.1, 1ก, 2, 3, 53 |
| **Invoicing > Reporting > Thai Accounting Reports > Thai Tax Report** | รายงานภาษีซื้อ/ขาย |
| **Invoicing > Reporting > Thai Accounting Reports > Personal Income Tax** | รายงาน PIT |
| **Invoicing > Configuration > Withholding Tax** | ตั้งค่าอัตรา WHT |
| **Invoicing > Configuration > WHT Income Code** | รหัสประเภทเงินได้ |
| **Invoicing > Accounting > Tax Invoices** | ดูใบกำกับภาษี |
| **Invoicing > Accounting > Withholding Tax Move** | ดูรายการเคลื่อนไหว WHT |
| **Expenses > My Expenses** | สร้าง Expense พร้อม WHT |

---

## ปัญหาที่เคยพบ (แก้ไขแล้วใน commit `b70ebc5` และ `e6c7966`)

> สำหรับผู้ที่ download repo เวอร์ชันก่อนหน้า อาจเจอปัญหาเหล่านี้:

| ปัญหา | สาเหตุ | สถานะ |
|--------|--------|--------|
| `Permission denied` ตอน gitaggregate | Volume mount เป็น root แต่ container ใช้ user `odoo` | แก้แล้ว — Dockerfile เพิ่ม `chown /workspace` |
| `Committer identity unknown` | Git config set ตอนเป็น root ไม่ persist ให้ user `odoo` | แก้แล้ว — ย้าย `git config` ไปอยู่หลัง `USER odoo` |
| `report_xlsx_helper not available` | `reporting-engine` ไม่ได้อยู่ใน `repos.yml` | แก้แล้ว — เพิ่ม `reporting-engine` ใน repos.yml |
| `l10n_th_base_utils` หายถ้าลบ branch อื่น | ติดมา implicit จาก branch `l10n_th_account_tax` | แก้แล้ว — เพิ่ม explicit ใน repos.yml |
| เมนู Accounting หาไม่เจอ | Odoo Community ใช้ชื่อ **Invoicing** ไม่ใช่ Accounting | ระบุถูกต้องในคู่มือแล้ว |

---

## คำสั่งที่มีประโยชน์

```bash
# ดู log แบบ real-time
docker compose logs -f odoo

# Restart Odoo (หลังแก้ code)
docker compose restart odoo

# Update module เฉพาะตัว
docker compose exec odoo odoo -d thaiacc \
  --db_host=db --db_user=odoo --db_password=odoo \
  --http-interface=0.0.0.0 \
  -u l10n_th_account_tax_report --stop-after-init

# Run tests
docker compose exec odoo odoo -d test_db \
  --db_host=db --db_user=odoo --db_password=odoo \
  -i thaiacc --test-enable --test-tags /thaiacc --stop-after-init --without-demo=False

# Stop ทุกอย่าง
docker compose down

# Stop แล้วลบ database ด้วย (เริ่มใหม่หมด)
docker compose down -v
```
