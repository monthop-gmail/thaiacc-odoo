# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

import os

import psycopg2
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import config

FIXTURE_SQL = os.path.join(
    os.path.dirname(__file__), "..", "fixture", "legacy_19_fixture.sql",
)
LEGACY_DB = os.environ.get("THAIACC_LEGACY_FIXTURE_DB", "thaiacc19_fixture")


@tagged("post_install", "-at_install")
class TestMigrateEndToEnd(TransactionCase):
    """Real end-to-end migration: a deterministic legacy 19.0 fixture
    database is created (and left untouched), the contract runs against it,
    and every evidence class reconciles before vs after.

    Acceptance matrix (discussion seq 13):
      1 trial balance        2 customer/output VAT      3 PIT accumulated
      4 PND by form/period   5 cancelled/reversed       6 partial CABA
      7 PromptPay/bank       8 50 Tawi certificates     9 meta after migration
     10 no duplicates       11 consolidated report     12 docs updated
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.legacy_dsn = (
            f"host={config['db_host']} port={config['db_port'] or 5432} "
            f"user={config['db_user']} password={config['db_password']} "
            f"dbname={LEGACY_DB}"
        )
        cls.admin_dsn = (
            f"host={config['db_host']} port={config['db_port'] or 5432} "
            f"user={config['db_user']} password={config['db_password']} "
            f"dbname=postgres"
        )
        cls._create_fixture_db()

        company = cls.env.company
        company.l10n_th_is_vat_registered = True
        company.tax_exigibility = True
        company.account_fiscal_country_id = cls.env.ref("base.th")
        company.country_id = cls.env.ref("base.th")

        # 20.0-side partners matching the legacy fixture (by VAT)
        cls.vendor = cls.env.ref("ocaacc.demo_vendor_somchai")
        cls.individual = cls.env.ref("ocaacc.demo_vendor_wichai")
        cls.salary_person = cls.env["res.partner"].create({
            "name": "นายสมศักดิ์ มั่นคง",
            "supplier_rank": 1,
        })
        cls.customer = cls.env.ref("ocaacc.demo_customer_thai")

    # ------------------------------------------------------------- helpers

    @classmethod
    def _create_fixture_db(cls):
        admin = psycopg2.connect(cls.admin_dsn)
        admin.set_session(autocommit=True)
        try:
            with admin.cursor() as cr:
                cr.execute(f'DROP DATABASE IF EXISTS "{LEGACY_DB}"')
                cr.execute(f'CREATE DATABASE "{LEGACY_DB}"')
        finally:
            admin.close()
        conn = psycopg2.connect(cls.legacy_dsn)
        conn.autocommit = True  # DDL via multi-statement script
        try:
            with conn.cursor() as cr:
                cr.execute(open(FIXTURE_SQL).read())
        finally:
            conn.close()

    def _legacy_fingerprint(self):
        conn = psycopg2.connect(self.legacy_dsn)
        conn.set_session(readonly=True, autocommit=True)
        try:
            with conn.cursor() as cr:
                cr.execute(
                    "SELECT relname, n_live_tup FROM pg_stat_user_tables "
                    "WHERE schemaname = 'legacy19' ORDER BY relname",
                )
                return dict(cr.fetchall())
        finally:
            conn.close()

    def _tax_by_name(self, name):
        return self.env["account.tax"].search([("name", "=", name)], limit=1)

    def _create_bill(self, partner, ref, price, taxes, extra_taxes=()):
        extra = list(extra_taxes.ids) if hasattr(extra_taxes, "ids") else list(extra_taxes)
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "ref": ref,
            "invoice_date": fields.Date.to_date("2026-09-15"),
            "invoice_line_ids": [
                Command.create({
                    "quantity": 1,
                    "price_unit": price,
                    "tax_ids": [Command.set(list(taxes.ids) + extra)],
                }),
            ],
        })
        bill.action_post()
        return bill

    def _pay(self, bill, amount=None):
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=bill.ids,
        ).create({**({"amount": amount} if amount else {})})
        return wizard._create_payments()

    def _run_migration(self):
        run = self.env["l10n_th.migrate.run"].create({
            "source_dsn": self.legacy_dsn,
        })
        run.action_run()
        self.assertEqual(run.state, "done", run.error_message)
        return run

    # ----------------------------------------------------------- the runs

    def test_01_master_data_and_controls(self):
        """Run 1 + matrix 1/7/8/10: trial balance, banks, certificates,
        no duplicates, source untouched."""
        before = self._legacy_fingerprint()
        run = self._run_migration()
        after = self._legacy_fingerprint()

        # matrix 1: legacy trial balance is balanced and reported
        tb = run.stats["trial_balance"]
        self.assertTrue(tb["debit_credit_equal"])
        self.assertEqual(tb["legacy_debit"], 903000.0)
        self.assertEqual(tb["legacy_credit"], 903000.0)
        self.assertEqual(tb["unbalanced_moves"], [])

        # matrix 7: bank/PromptPay data mapped to official res.partner.bank
        self.assertEqual(run.stats["banks"]["mapped"], 1)
        bank = self.env["res.partner.bank"].search(
            [
                ("account_number", "=", "1234567890"),
                ("partner_id", "=", self.vendor.id),
            ],
        )
        self.assertEqual(bank.partner_id, self.vendor)
        self.assertEqual(bank.proxy_type, "merchant_tax_id")
        self.assertEqual(bank.proxy_value, "0105560123456")

        # matrix 8: certificates archived verbatim (no official equivalent)
        self.assertEqual(run.stats["certificates_archived"], 2)
        certs = self.env["l10n_th.migrate.archive"].search(
            [
                ("source_table", "=", "legacy19.account_withholding_cert"),
                ("run_id", "=", run.id),
            ],
        )
        self.assertEqual(
            sorted(c.payload["cert_number"] for c in certs),
            ["CERT-2569-001", "CERT-2569-002"],
        )

        # matrix 10: no duplicate canonical taxes after mapping
        self.assertEqual(run.stats["duplicate_taxes"], [])

        # source DB untouched
        self.assertEqual(after, before)

        # mapped master data reused by later tests
        self.env["ir.config_parameter"].sudo().set_str(
            "l10n_th_migrate.test_wht_service_id",
            str(self._tax_by_name("WHT 3% ค่าบริการ/จ้างทำของ").id),
        )
        self.env["ir.config_parameter"].sudo().set_str(
            "l10n_th_migrate.test_wht_rent_id",
            str(self._tax_by_name("WHT 5% ค่าเช่า").id),
        )

    def test_02_vendor_accounting_reconciliation(self):
        """Matrix 1/2/11: vendor bills posted on the 20 side mirror the
        legacy posted accounting; official withholding lines reconcile with
        one explained delta (PIT first payment)."""
        self.test_01_master_data_and_controls()
        wht_service = self._tax_by_name("WHT 3% ค่าบริการ/จ้างทำของ")
        wht_rent = self._tax_by_name("WHT 5% ค่าเช่า")

        # mirror the legacy posted vendor bills
        bills = [
            self._create_bill(self.vendor, "BILL/2026/08/0001", 100000.0, wht_service),
            self._create_bill(self.vendor, "BILL/2026/09/0002", 200000.0, wht_rent),
            self._create_bill(self.individual, "BILL/2026/11/0006", 50000.0, wht_service),
            self._create_bill(self.individual, "BILL/2026/11/0007", 20000.0, wht_rent),
            self._create_bill(self.vendor, "BILL/2026/10/0003", 100000.0, wht_service),
        ]
        salary_bill = self._create_bill(
            self.salary_person, "BILL/2026/11/0008", 200000.0,
            self._tax_by_name("WHT เงินเดือน (ตามตาราง)"),
        )
        salary_bill2 = self._create_bill(
            self.salary_person, "BILL/2026/11/0009", 100000.0,
            self._tax_by_name("WHT เงินเดือน (ตามตาราง)"),
        )
        for bill in (*bills, salary_bill, salary_bill2):
            self._pay(bill)

        run = self._run_migration()
        self.assertEqual(
            self.individual.l10n_th_pnd_entity_type, "person",
            run.stats["pnd_entity_types"],
        )

        # matrix 1 after-side: 20.0 posted vendor totals == legacy posted
        legacy_vendor_total = 100000.0 + 200000.0 + 100000.0 + 50000.0 + 20000.0 + 200000.0 + 100000.0
        mirror_total = sum(
            self.env["account.move"]
            .search([
                ("move_type", "=", "in_invoice"),
                ("ref", "in", [
                    "BILL/2026/08/0001", "BILL/2026/09/0002",
                    "BILL/2026/10/0003", "BILL/2026/11/0006",
                    "BILL/2026/11/0007", "BILL/2026/11/0008", "BILL/2026/11/0009",
                ]),
            ])
            .mapped("amount_untaxed"),
        )
        self.assertEqual(mirror_total, legacy_vendor_total)
        tb = run.stats["trial_balance"]
        self.assertTrue(tb["target_debit_credit_equal"])
        self.assertEqual(tb["target_moves"], 7)
        self.assertEqual(tb["target_missing_refs"], ["INV/2026/09/0004"])
        self.assertTrue(run.stats["reconciliation_summary"]["requires_manual_review"])

        # PIT is 2,500 on the first 200k and 5,000 on the next 100k.
        recon = run.stats["reconciliation"]
        self.assertEqual(recon["legacy_wht_total"], 26000.0)
        self.assertEqual(recon["official_wht_total"], 26000.0)

        # salary PIT line exists with the progressive first-payment amount
        pit_line = self.env["account.payment.withholding.line"].search(
            [("tax_id.l10n_th_is_pit", "=", True)],
        )
        self.assertEqual(len(pit_line), 2)
        self.assertEqual(sorted(pit_line.mapped("amount")), [2500.0, 5000.0])
        self.assertEqual(sum(pit_line.mapped("base_amount")), 300000.0)
        official_lines_before = self.env["account.payment.withholding.line"].search_count([])
        second = self._run_migration()
        self.assertEqual(
            self.env["account.payment.withholding.line"].search_count([]),
            official_lines_before,
        )
        self.assertEqual(second.stats["reconciliation"]["official_wht_total"], 26000.0)

    def test_03_customer_invoices_and_cancel(self):
        """Matrix 2/5: output VAT customer invoice gets an official sales TI;
        a cancelled invoice's TI is cancelled too."""
        self.test_01_master_data_and_controls()
        group = self.env["account.tax.group"].search([], limit=1) or \
            self.env["account.tax.group"].create({"name": "VAT"})
        output_vat = self.env["account.tax"].create({
            "name": "Output VAT 7%",
            "amount_type": "percent",
            "amount": 7.0,
            "type_tax_use": "sale",
            "country_id": self.env.ref("base.th").id,
            "tax_group_id": group.id,
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.customer.id,
            "ref": "INV/2026/09/0004",
            "invoice_date": fields.Date.to_date("2026-09-10"),
            "invoice_line_ids": [
                Command.create({
                    "quantity": 1,
                    "price_unit": 100000.0,
                    "tax_ids": [Command.set(output_vat.ids)],
                }),
            ],
        })
        invoice.action_post()
        self.assertEqual(len(invoice.l10n_th_tax_invoice_ids), 1)
        self.assertAlmostEqual(invoice.amount_tax, 7000.0, 2)

        # the invoice carries output VAT so an official TI exists; cancelling
        # the invoice must cancel its TI (matrix 5)
        cancelled = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.customer.id,
            "ref": "INV/2026/09/0005",
            "invoice_date": fields.Date.to_date("2026-09-11"),
            "invoice_line_ids": [
                Command.create({
                    "quantity": 1,
                    "price_unit": 5000.0,
                    "tax_ids": [Command.set(output_vat.ids)],
                }),
            ],
        })
        cancelled.action_post()
        cancelled.button_cancel()
        self.assertEqual(
            cancelled.l10n_th_tax_invoice_ids[0].state, "cancel",
        )

        run = self._run_migration()
        # customer TI existence reconciled against legacy evidence
        self.assertEqual(run.stats["customer_tax_invoices"]["with_official_ti"], 1)

    def test_04_partial_caba(self):
        """Matrix 6: partial payments on an on-payment bill create prorated
        CABA tax invoices; withholding lines are prorated too."""
        self.test_01_master_data_and_controls()
        wht_service = self._tax_by_name("WHT 3% ค่าบริการ/จ้างทำของ")
        group = self.env["account.tax.group"].search([], limit=1) or \
            self.env["account.tax.group"].create({"name": "VAT"})
        vat_on_payment = self.env["account.tax"].create({
            "name": "Purchase VAT 7% On Payment",
            "amount_type": "percent",
            "amount": 7.0,
            "type_tax_use": "purchase",
            "tax_exigibility": "on_payment",
            "tax_group_id": group.id,
        })
        bill = self._create_bill(
            self.vendor, "BILL/2026/10/0003", 100000.0, vat_on_payment,
            extra_taxes=wht_service,
        )
        self._pay(bill, amount=42800.0)  # 40% of 107,000
        self._pay(bill, amount=64200.0)  # 60%

        caba_tis = bill.l10n_th_tax_invoice_ids.filtered(
            lambda ti: ti.payment_move_id,
        )
        self.assertEqual(len(caba_tis), 2)
        self.assertAlmostEqual(
            sum(caba_tis.mapped("total_amount")), 107000.0, 2,
        )

        wht_lines = self.env["account.payment.withholding.line"].search([
            ("payment_id.partner_id", "=", self.vendor.id),
            ("tax_id", "=", wht_service.id),
        ])
        self.assertAlmostEqual(sum(wht_lines.mapped("amount")), 3000.0, 2)

        run = self._run_migration()
        caba = run.stats["caba_tax_invoices"]
        self.assertEqual(caba["mapped"], 2)
        self.assertEqual(caba["unresolved"], [])
        self.assertEqual(caba["source_vat"], 7000.0)
        self.assertEqual(caba["target_vat"], 7000.0)
        self.assertEqual(
            sorted(caba_tis.mapped("tax_invoice_number")),
            ["V-CABA-2569-40", "V-CABA-2569-60"],
        )

    def test_05_pnd_report_by_form(self):
        """Matrix 4: PND normalized totals by form and period."""
        self.test_02_vendor_accounting_reconciliation()
        report = self.env["l10n_th.pnd.report"].create({
            "date_from": fields.Date.to_date("2026-08-01"),
            "date_to": fields.Date.to_date("2026-12-31"),
        })
        report.action_generate()

        def line_for(pnd_type):
            return report.line_ids.filtered(lambda l: l.pnd_type == pnd_type)

        def total(pnd_type, field_name):
            return sum(line_for(pnd_type).mapped(field_name))

        # corporate payee -> PND53 (bills 08/09/10: 400k base, 16k withheld)
        self.assertAlmostEqual(total("pnd53", "base_amount"), 400000.0, 2)
        self.assertAlmostEqual(total("pnd53", "tax_amount"), 16000.0, 2)
        # individual services -> PND2 (50k / 1,500)
        self.assertAlmostEqual(total("pnd2", "base_amount"), 50000.0, 2)
        self.assertAlmostEqual(total("pnd2", "tax_amount"), 1500.0, 2)
        # individual rentals -> PND3 (20k / 1,000)
        self.assertAlmostEqual(total("pnd3", "base_amount"), 20000.0, 2)
        self.assertAlmostEqual(total("pnd3", "tax_amount"), 1000.0, 2)
        # individual salary (na) -> PND1 (300k base, progressive PIT 7,500)
        self.assertAlmostEqual(total("pnd1", "base_amount"), 300000.0, 2)
        self.assertAlmostEqual(total("pnd1", "tax_amount"), 7500.0, 2)

    def test_06_no_duplicates_and_meta_after_migration(self):
        """Matrix 9/10: migration is idempotent; the meta package stays
        installed and the registry keeps loading after the migration."""
        self.test_01_master_data_and_controls()
        self._run_migration()  # second full run — must not duplicate

        self.assertEqual(
            self.env["account.tax"].search_count(
                [("name", "=", "WHT 3% ค่าบริการ/จ้างทำของ")],
            ),
            1,
        )
        thaiacc = self.env["ir.module.module"].search([("name", "=", "thaiacc")])
        self.assertEqual(thaiacc.state, "installed")
        self.env["l10n_th.pnd.report"].search_count([])  # registry live

    def test_07_caba_acceptance_and_pnd1a_queue(self):
        """dec-24252acf + dec-a92c38dc: with the approved policy parameter,
        an unresolved legacy CABA row (over-claimed VAT) is archived with a
        cross-reference to the canonical target bill — never synthesized —
        and PIT withholding rows land in the manual PND1A review queue
        instead of being auto-filed."""
        self.test_01_master_data_and_controls()
        wht_service = self._tax_by_name("WHT 3% ค่าบริการ/จ้างทำของ")
        self.env["ir.config_parameter"].sudo().set_str(
            "l10n_th_migrate.caba_over_claim_policy", "official_canonical",
        )
        group = self.env["account.tax.group"].search([], limit=1) or \
            self.env["account.tax.group"].create({"name": "VAT"})
        vat_on_payment = self.env["account.tax"].create({
            "name": "Purchase VAT 7% On Payment",
            "amount_type": "percent",
            "amount": 7.0,
            "type_tax_use": "purchase",
            "tax_exigibility": "on_payment",
            "tax_group_id": group.id,
        })
        bill = self._create_bill(
            self.vendor, "BILL/2026/10/0003", 100000.0, vat_on_payment,
            extra_taxes=wht_service,
        )
        self._pay(bill, amount=42800.0)  # 40% only → target TI 2,800 only

        run = self._run_migration()
        caba = run.stats["caba_tax_invoices"]
        # legacy fixture rows are 2,800 + 4,200; the target produced only
        # the 2,800 slice, so the second legacy row stays unmatched
        self.assertEqual(caba["mapped"], 1)
        self.assertEqual(len(caba["unresolved"]), 1)
        self.assertEqual(caba["policy"], "official_canonical")
        self.assertEqual(caba["decision"], "dec-24252acf")
        # dec-24252acf with per-bill proof: a 40%-settled bill cannot prove
        # an over-claim — the 4,200 row may simply be a payment that never
        # migrated, so nothing is accepted and the run keeps manual review
        self.assertEqual(caba["accepted_over_claim_ids"], [])
        self.assertEqual(caba["accepted_over_claim_total"], 0.0)

        archive = self.env["l10n_th.migrate.archive"].search([
            ("run_id", "=", run.id),
            ("source_table", "=", "legacy19.account_tax_invoice_evidence"),
            ("legacy_id", "in", caba["unresolved"]),
        ])
        self.assertEqual(len(archive), 1)
        self.assertFalse(archive.xref_model)
        self.assertFalse(archive.over_claim_amount)

        summary = run.stats["reconciliation_summary"]
        self.assertEqual(
            summary["caba_over_claim_policy"], "official_canonical",
        )
        self.assertFalse(summary["caba_over_claim_waived"])
        self.assertTrue(summary["requires_manual_review"])

        # dec-a92c38dc: PIT rows queued for manual form classification,
        # nothing auto-filed as PND1A
        queue = run.stats["pnd_form_review_queue"]
        self.assertEqual(queue["decision"], "dec-a92c38dc")
        self.assertGreater(queue["legacy_rows"], 0)
        self.assertEqual(queue["auto_filed_pnd1a"], 0)
        self.assertEqual(self.env["l10n_th.pnd.report"].search_count([]), 0)

    def _delete_legacy_over_claim_row(self):
        conn = psycopg2.connect(self.legacy_dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cr:
                cr.execute(
                    "DELETE FROM legacy19.account_tax_invoice_evidence "
                    "WHERE id = 24",
                )
        finally:
            conn.close()

    def test_08_caba_over_claim_proven_acceptance(self):
        """dec-24252acf with per-bill proof: when the bill is fully settled,
        the legacy payments migrated with it, and legacy CABA VAT minus the
        official target CABA VAT equals the remaining unresolved row, that
        row is accepted as over-claim evidence with the amount recorded —
        and the accepted total must exactly explain the VAT delta."""
        self.test_01_master_data_and_controls()
        wht_service = self._tax_by_name("WHT 3% ค่าบริการ/จ้างทำของ")
        self.env["ir.config_parameter"].sudo().set_str(
            "l10n_th_migrate.caba_over_claim_policy", "official_canonical",
        )
        group = self.env["account.tax.group"].search([], limit=1) or \
            self.env["account.tax.group"].create({"name": "VAT"})
        vat_on_payment = self.env["account.tax"].create({
            "name": "Purchase VAT 7% On Payment",
            "amount_type": "percent",
            "amount": 7.0,
            "type_tax_use": "purchase",
            "tax_exigibility": "on_payment",
            "tax_group_id": group.id,
        })
        bill = self._create_bill(
            self.vendor, "BILL/2026/10/0003", 100000.0, vat_on_payment,
            extra_taxes=wht_service,
        )
        self._pay(bill, amount=42800.0)
        self._pay(bill, amount=64200.0)  # fully settled

        # extra legacy evidence row: the draft-reset engine re-claimed the
        # first payment's VAT (2,800 booked twice for one 40% slice)
        conn = psycopg2.connect(self.legacy_dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cr:
                cr.execute(
                    "INSERT INTO legacy19.account_tax_invoice_evidence "
                    "(id, bill_reference, tax_invoice_number, "
                    "tax_invoice_date, is_cash_basis, vat_amount) VALUES "
                    "(24, 'BILL/2026/10/0003', 'V-CABA-2569-40-DUP', "
                    "'2026-10-25', true, 2800.0)",
                )
        finally:
            conn.close()
        self.addCleanup(self._delete_legacy_over_claim_row)

        run = self._run_migration()
        caba = run.stats["caba_tax_invoices"]
        # rows 22 + 23 map onto the two payment TIs; row 24 (the duplicate
        # 2,800 claim) is the proven over-claim
        self.assertEqual(caba["mapped"], 2)
        self.assertEqual(caba["unresolved"], [24])
        self.assertEqual(caba["accepted_over_claim_ids"], [24])
        self.assertEqual(caba["accepted_over_claim_total"], 2800.0)
        self.assertEqual(caba["vat_delta"], -2800.0)
        self.assertEqual(caba["decision"], "dec-24252acf")
        self.assertEqual(caba["decided_by"], "owner")

        summary = run.stats["reconciliation_summary"]
        self.assertTrue(summary["caba_over_claim_waived"])
        self.assertEqual(summary["caba_over_claim_decision"], "dec-24252acf")
        self.assertEqual(summary["caba_over_claim_total"], 2800.0)

        archive = self.env["l10n_th.migrate.archive"].search([
            ("run_id", "=", run.id),
            ("source_table", "=", "legacy19.account_tax_invoice_evidence"),
            ("legacy_id", "=", 24),
        ])
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive.xref_model, "account.move")
        self.assertEqual(archive.xref_res_id, bill.id)
        self.assertEqual(archive.over_claim_amount, 2800.0)
        self.assertIn("over-claim 2800.0", archive.note)

        # the archive's source fields mirror the legacy evidence verbatim
        # and are immutable, even for admins
        with self.assertRaises(UserError):
            archive.write({"payload": {"id": 24}})
