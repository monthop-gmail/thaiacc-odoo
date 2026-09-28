-- ThaiACC 19.0 legacy fixture — deterministic representative subset of the
-- legacy thaiacc stack schema, containing exactly the evidence classes the
-- 20.0 migration contract maps (see l10n_th_migrate/MIGRATION-CONTRACT.md).
-- Applied to a dedicated database (default: thaiacc19_fixture); the migration
-- runner connects READ-ONLY. Deterministic: same file -> same rows.

DROP SCHEMA IF EXISTS legacy19 CASCADE;
CREATE SCHEMA legacy19;

-- ---------------------------------------------------------------- partners
CREATE TABLE legacy19.res_partner (
    id integer PRIMARY KEY,
    name varchar NOT NULL,
    vat varchar,
    is_company boolean NOT NULL DEFAULT false,
    company_registry varchar
);
INSERT INTO legacy19.res_partner (id, name, vat, is_company, company_registry) VALUES
    (100, 'บริษัท สมชาย เทรดดิ้ง จำกัด', '0105560123456', true, '7'),
    (101, 'นายวิชัย ใจดี', '1234567890123', false, NULL),
    (102, 'บริษัท ลูกค้าไทย จำกัด (มหาชน)', '0107550345678', true, NULL),
    (103, 'นายสมศักดิ์ มั่นคง', NULL, false, NULL);

CREATE TABLE legacy19.res_company_novat (
    company_id integer PRIMARY KEY,
    novat boolean NOT NULL DEFAULT false
);
INSERT INTO legacy19.res_company_novat (company_id, novat) VALUES (1, true);

-- PromptPay / bank data on the vendor (PromptPay QR disposition, matrix 7)
CREATE TABLE legacy19.partner_bank (
    id integer PRIMARY KEY,
    partner_id integer NOT NULL REFERENCES legacy19.res_partner(id),
    acc_number varchar NOT NULL,
    bank_name varchar,
    promptpay_id varchar
);
INSERT INTO legacy19.partner_bank (id, partner_id, acc_number, bank_name, promptpay_id) VALUES
    (1, 100, '1234567890', 'ธนาคารกสิกรไทย', '0105560123456');

-- --------------------------------------------------- legacy WHT master data
CREATE TABLE legacy19.account_withholding_tax (
    id integer PRIMARY KEY,
    name varchar NOT NULL,
    amount numeric NOT NULL,
    income_tax_form varchar,
    is_pit boolean NOT NULL DEFAULT false,
    account_id integer
);
INSERT INTO legacy19.account_withholding_tax (id, name, amount, income_tax_form, is_pit) VALUES
    (1, 'WHT 3% ค่าบริการ/จ้างทำของ', 3.0, 'pnd2', false),
    (2, 'WHT 5% ค่าเช่า', 5.0, 'pnd3', false),
    (3, 'WHT เงินเดือน (ตามตาราง)', 0.0, 'pnd1', true);

-- ------------------------------------------- legacy posted accounting (TB)
CREATE TABLE legacy19.account_move (
    id integer PRIMARY KEY,
    ref varchar NOT NULL,
    move_type varchar NOT NULL,
    state varchar NOT NULL,
    partner_id integer NOT NULL REFERENCES legacy19.res_partner(id),
    date date NOT NULL,
    amount_total numeric NOT NULL
);
CREATE TABLE legacy19.account_move_line (
    id integer PRIMARY KEY,
    move_id integer NOT NULL REFERENCES legacy19.account_move(id),
    account_code varchar NOT NULL,
    debit numeric NOT NULL DEFAULT 0,
    credit numeric NOT NULL DEFAULT 0
);

-- vendor bill 1: 100,000 + WHT 3,000 withheld -> net payable 97,000
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (1, 'BILL/2026/08/0001', 'in_invoice', 'posted', 100, '2026-08-01', 100000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (1, 1, '511000', 100000.0, 0), (2, 1, '213999', 3000.0, 0), (3, 1, '211000', 0, 103000.0);

-- vendor bill 2: 200,000 + WHT 10,000 -> net payable 190,000
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (2, 'BILL/2026/09/0002', 'in_invoice', 'posted', 100, '2026-09-01', 200000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (4, 2, '511000', 200000.0, 0), (5, 2, '213999', 10000.0, 0), (6, 2, '211000', 0, 210000.0);

-- vendor bill 3: partial-payment example, 100,000 paid in 40%/60%
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (3, 'BILL/2026/10/0003', 'in_invoice', 'posted', 100, '2026-10-01', 100000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (7, 3, '511000', 100000.0, 0), (8, 3, '213999', 3000.0, 0), (9, 3, '211000', 0, 103000.0);

-- customer invoice: 100,000 + output VAT 7,000
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (4, 'INV/2026/09/0004', 'out_invoice', 'posted', 102, '2026-09-10', 107000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (10, 4, '113000', 107000.0, 0), (11, 4, '411000', 0, 100000.0), (12, 4, '141100', 0, 7000.0);

-- customer invoice cancelled
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (5, 'INV/2026/09/0005', 'out_invoice', 'cancelled', 102, '2026-09-11', 5350.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (13, 5, '113000', 5350.0, 0), (14, 5, '411000', 0, 5000.0), (15, 5, '141100', 0, 350.0);

-- vendor bill for PND3 (rentals)
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (6, 'BILL/2026/11/0007', 'in_invoice', 'posted', 101, '2026-11-01', 20000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (16, 6, '511000', 20000.0, 0), (17, 6, '213999', 1000.0, 0), (18, 6, '211000', 0, 21000.0);

-- vendor bill for PND2 (services, individual)
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (8, 'BILL/2026/11/0006', 'in_invoice', 'posted', 101, '2026-11-01', 50000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (22, 8, '511000', 50000.0, 0), (23, 8, '213999', 1500.0, 0), (24, 8, '211000', 0, 51500.0);

-- two PND1 payments: progressive PIT 2,500 then 5,000 on accumulated base
INSERT INTO legacy19.account_move (id, ref, move_type, state, partner_id, date, amount_total) VALUES
    (7, 'BILL/2026/11/0008', 'in_invoice', 'posted', 103, '2026-11-02', 200000.0),
    (9, 'BILL/2026/11/0009', 'in_invoice', 'posted', 103, '2026-11-03', 100000.0);
INSERT INTO legacy19.account_move_line (id, move_id, account_code, debit, credit) VALUES
    (19, 7, '511000', 200000.0, 0), (20, 7, '213999', 2500.0, 0), (21, 7, '211000', 0, 202500.0),
    (25, 9, '511000', 100000.0, 0), (26, 9, '213999', 5000.0, 0), (27, 9, '211000', 0, 105000.0);

-- ------------------------------------------------- legacy WHT move evidence
CREATE TABLE legacy19.account_withholding_move (
    id integer PRIMARY KEY,
    partner_id integer NOT NULL,
    date date NOT NULL,
    state varchar NOT NULL,
    base_amount numeric NOT NULL,
    wht_amount numeric NOT NULL,
    withholding_tax_id integer NOT NULL REFERENCES legacy19.account_withholding_tax(id),
    bill_reference varchar
);
INSERT INTO legacy19.account_withholding_move (id, partner_id, date, state, base_amount, wht_amount, withholding_tax_id, bill_reference) VALUES
    (10, 100, '2026-08-01', 'posted', 100000.0, 3000.0, 1, 'BILL/2026/08/0001'),
    (11, 100, '2026-09-01', 'posted', 200000.0, 10000.0, 2, 'BILL/2026/09/0002'),
    (12, 100, '2026-10-05', 'posted', 40000.0, 1200.0, 1, 'BILL/2026/10/0003'),
    (13, 100, '2026-10-25', 'posted', 60000.0, 1800.0, 1, 'BILL/2026/10/0003'),
    (14, 100, '2026-10-26', 'cancelled', 50000.0, 1500.0, 1, 'BILL/2026/10/0009'),
    (15, 101, '2026-11-01', 'posted', 50000.0, 1500.0, 1, 'BILL/2026/11/0006'),
    (16, 103, '2026-11-02', 'posted', 200000.0, 2500.0, 3, 'BILL/2026/11/0008'),
    (17, 101, '2026-11-03', 'posted', 20000.0, 1000.0, 2, 'BILL/2026/11/0007'),
    (18, 103, '2026-11-03', 'posted', 100000.0, 5000.0, 3, 'BILL/2026/11/0009');

-- legacy tax invoice evidence (vendor bills + customer invoices)
CREATE TABLE legacy19.account_tax_invoice_evidence (
    id integer PRIMARY KEY,
    bill_reference varchar NOT NULL,
    tax_invoice_number varchar NOT NULL,
    tax_invoice_date date NOT NULL,
    is_cash_basis boolean NOT NULL DEFAULT false,
    vat_amount numeric
);
INSERT INTO legacy19.account_tax_invoice_evidence (id, bill_reference, tax_invoice_number, tax_invoice_date) VALUES
    (20, 'BILL/2026/08/0001', 'V-TI-2569-0001', '2026-08-01'),
    (21, 'INV/2026/09/0004', 'TINV-2569-0007', '2026-09-10');
INSERT INTO legacy19.account_tax_invoice_evidence
    (id, bill_reference, tax_invoice_number, tax_invoice_date, is_cash_basis, vat_amount) VALUES
    (22, 'BILL/2026/10/0003', 'V-CABA-2569-40', '2026-10-25', true, 2800.0),
    (23, 'BILL/2026/10/0003', 'V-CABA-2569-60', '2026-10-26', true, 4200.0);

-- ------------------------------------------------- legacy PIT (matrix 3)
CREATE TABLE legacy19.personal_income_tax (
    id integer PRIMARY KEY,
    calendar_year varchar NOT NULL
);
CREATE TABLE legacy19.personal_income_tax_rate (
    id integer PRIMARY KEY,
    pit_id integer NOT NULL REFERENCES legacy19.personal_income_tax(id),
    sequence integer NOT NULL,
    income_from numeric NOT NULL,
    income_to numeric NOT NULL,
    tax_rate numeric NOT NULL
);
INSERT INTO legacy19.personal_income_tax (id, calendar_year) VALUES (1, '2026');
INSERT INTO legacy19.personal_income_tax_rate (id, pit_id, sequence, income_from, income_to, tax_rate) VALUES
    (1, 1, 1, 0.0, 150000.0, 0.0),
    (2, 1, 2, 150000.0, 300000.0, 5.0),
    (3, 1, 3, 300000.0, 500000.0, 10.0);

-- ------------------------------------- legacy WHT certificates (matrix 8)
-- No official 20.0 equivalent: archived read-only, engines not revived.
CREATE TABLE legacy19.account_withholding_cert (
    id integer PRIMARY KEY,
    withholding_move_id integer NOT NULL REFERENCES legacy19.account_withholding_move(id),
    cert_number varchar NOT NULL,
    income_type varchar NOT NULL
);
INSERT INTO legacy19.account_withholding_cert (id, withholding_move_id, cert_number, income_type) VALUES
    (1, 10, 'CERT-2569-001', '1'),
    (2, 11, 'CERT-2569-002', '2');
