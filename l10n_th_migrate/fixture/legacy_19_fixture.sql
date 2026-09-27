-- ThaiACC 19.0 legacy fixture — deterministic representative subset of the
-- legacy thaiacc stack schema, containing exactly the evidence classes the
-- 20.0 migration contract maps (see l10n_th_migrate/MIGRATION-CONTRACT.md).
-- Applied to a dedicated database (default: thaiacc19_fixture); the migration
-- runner connects READ-ONLY. Deterministic: same file -> same rows.

DROP SCHEMA IF EXISTS legacy19 CASCADE;
CREATE SCHEMA legacy19;

-- Row 1: legacy account.withholding.tax (positive percents, income_tax_form)
CREATE TABLE legacy19.account_withholding_tax (
    id integer PRIMARY KEY,
    name varchar NOT NULL,
    amount numeric NOT NULL,
    income_tax_form varchar,
    account_id integer
);
INSERT INTO legacy19.account_withholding_tax (id, name, amount, income_tax_form) VALUES
    (1, 'WHT 3% ค่าบริการ/จ้างทำของ', 3.0, 'pnd2'),
    (2, 'WHT 5% ค่าเช่า', 5.0, 'pnd3');

-- Row 5: legacy res.partner.company_registry (Thai branch code)
CREATE TABLE legacy19.res_partner (
    id integer PRIMARY KEY,
    name varchar NOT NULL,
    vat varchar,
    company_registry varchar
);
INSERT INTO legacy19.res_partner (id, name, vat, company_registry) VALUES
    (100, 'บริษัท สมชาย เทรดดิ้ง จำกัด', '0105560123456', '7'),
    (101, 'นายวิชัย ใจดี', '1234567890123', NULL);

-- Row 6: legacy l10n_th_company_novat flag
CREATE TABLE legacy19.res_company_novat (
    company_id integer PRIMARY KEY,
    novat boolean NOT NULL DEFAULT false
);
INSERT INTO legacy19.res_company_novat (company_id, novat) VALUES (1, true);

-- Row 2: legacy account.withholding.move (+ lines) — per-payment WHT evidence
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
    (11, 100, '2026-09-01', 'posted', 200000.0, 10000.0, 2, 'BILL/2026/09/0002');

-- Row 4: legacy tax invoice evidence carried on bills
CREATE TABLE legacy19.account_tax_invoice_evidence (
    id integer PRIMARY KEY,
    bill_reference varchar NOT NULL,
    tax_invoice_number varchar NOT NULL,
    tax_invoice_date date NOT NULL
);
INSERT INTO legacy19.account_tax_invoice_evidence (id, bill_reference, tax_invoice_number, tax_invoice_date) VALUES
    (20, 'BILL/2026/08/0001', 'V-TI-2569-0001', '2026-08-01');

-- Row 3: legacy personal.income.tax table (progressive PIT)
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
INSERT INTO legacy19.personal_income_tax (id, calendar_year) VALUES (1, '2569');
INSERT INTO legacy19.personal_income_tax_rate (id, pit_id, sequence, income_from, income_to, tax_rate) VALUES
    (1, 1, 1, 0.0, 150000.0, 0.0),
    (2, 1, 2, 150000.0, 300000.0, 5.0),
    (3, 1, 3, 300000.0, 500000.0, 10.0);
