-- Apply only to an isolated Odoo 19 clone. The migration runner reads these
-- views with a read-only credential; it never writes to the source.
-- Set exactly one source company in legacy19.scope before running the mapper.
CREATE SCHEMA IF NOT EXISTS legacy19;
CREATE TABLE IF NOT EXISTS legacy19.scope (company_id integer PRIMARY KEY);

CREATE OR REPLACE VIEW legacy19.account_withholding_tax AS
SELECT t.id, t.name, t.amount, t.income_tax_form, t.is_pit
FROM public.account_withholding_tax t
JOIN legacy19.scope s ON s.company_id = t.company_id;

CREATE OR REPLACE VIEW legacy19.account_withholding_move AS
SELECT w.id, w.partner_id, w.date,
       CASE WHEN w.cancelled THEN 'cancelled' ELSE 'posted' END AS state,
       w.amount_income AS base_amount, w.amount_wht AS wht_amount,
       w.wht_tax_id AS withholding_tax_id,
       COALESCE(m.ref, m.name) AS bill_reference
FROM public.account_withholding_move w
JOIN legacy19.scope s ON s.company_id = w.company_id
LEFT JOIN public.account_move m ON m.id = w.move_id;

CREATE OR REPLACE VIEW legacy19.res_partner AS
SELECT p.id, p.name, p.vat, p.is_company, p.company_registry
FROM public.res_partner p
WHERE p.id IN (
    SELECT partner_id FROM legacy19.account_withholding_move
    UNION SELECT partner_id FROM public.account_move am
          JOIN legacy19.scope s ON s.company_id = am.company_id
);

CREATE OR REPLACE VIEW legacy19.res_company_novat AS
SELECT c.id AS company_id, c.novat
FROM public.res_company c JOIN legacy19.scope s ON s.company_id = c.id;

CREATE OR REPLACE VIEW legacy19.account_move AS
SELECT m.id, COALESCE(m.ref, m.name) AS ref, m.move_type, m.state,
       m.partner_id, m.date, m.amount_total
FROM public.account_move m
JOIN legacy19.scope s ON s.company_id = m.company_id
WHERE m.move_type IN ('in_invoice', 'in_receipt', 'out_invoice', 'out_refund');

CREATE OR REPLACE VIEW legacy19.account_move_line AS
SELECT l.id, l.move_id,
       a.code_store ->> l.company_id::text AS account_code,
       l.debit, l.credit
FROM public.account_move_line l
JOIN legacy19.account_move m ON m.id = l.move_id
LEFT JOIN public.account_account a ON a.id = l.account_id;

CREATE OR REPLACE VIEW legacy19.account_tax_invoice_evidence AS
SELECT ti.id, COALESCE(origin.ref, m.ref, m.name) AS bill_reference,
       ti.tax_invoice_number, ti.tax_invoice_date,
       (m.tax_cash_basis_origin_move_id IS NOT NULL) AS is_cash_basis,
       ABS(ti.balance) AS vat_amount
FROM public.account_move_tax_invoice ti
JOIN public.account_move m ON m.id = ti.move_id
LEFT JOIN public.account_move origin ON origin.id = m.tax_cash_basis_origin_move_id
JOIN legacy19.scope s ON s.company_id = ti.company_id
WHERE ti.tax_invoice_number IS NOT NULL AND ti.tax_invoice_date IS NOT NULL;

CREATE OR REPLACE VIEW legacy19.personal_income_tax AS
SELECT id, calendar_year FROM public.personal_income_tax;
CREATE OR REPLACE VIEW legacy19.personal_income_tax_rate AS
SELECT id, pit_id, sequence, income_from, income_to, tax_rate
FROM public.personal_income_tax_rate;

CREATE OR REPLACE VIEW legacy19.partner_bank AS
SELECT b.id, b.partner_id, b.acc_number, rb.name AS bank_name,
       b.proxy_value AS promptpay_id
FROM public.res_partner_bank b
LEFT JOIN public.res_bank rb ON rb.id = b.bank_id
WHERE b.partner_id IN (SELECT id FROM legacy19.res_partner);

CREATE OR REPLACE VIEW legacy19.account_withholding_cert AS
SELECT c.id, w.id AS withholding_move_id, c.number AS cert_number,
       c.income_tax_form AS income_type
FROM public.withholding_tax_cert c
JOIN legacy19.scope s ON s.company_id = c.company_id
LEFT JOIN public.account_withholding_move w
       ON w.move_id = c.move_id AND w.partner_id = c.partner_id;
