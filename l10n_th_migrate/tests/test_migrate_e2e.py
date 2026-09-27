# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

import os

import psycopg2
from odoo import Command, fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import config

FIXTURE_SQL = os.path.join(
    os.path.dirname(__file__), "..", "fixture", "legacy_19_fixture.sql",
)
LEGACY_DB = "thaiacc19_fixture"


@tagged("post_install", "-at_install")
class TestMigrateEndToEnd(TransactionCase):
    """Real end-to-end migration: a deterministic legacy 19.0 fixture
    database is created (and left untouched), the contract runs against it,
    and the evidence reconciles before vs after."""

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
        cls.vendor = cls.env["res.partner"].create({
            "name": "บริษัท สมชาย เทรดดิ้ง จำกัด",
            "vat": "0105560123456",
            "supplier_rank": 1,
        })

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
        """Row counts per legacy table — proves the source DB is untouched."""
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

    def _create_mirror_accounting(self, events):
        """The migrated accounting: the same business events, posted on the
        20.0 side with the mapped withholding taxes (fresh-install path never
        sees any of this)."""
        for ref, price, wht_tax in events:
            bill = self.env["account.move"].create({
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "ref": ref,
                "invoice_date": fields.Date.to_date("2026-09-15"),
                "invoice_line_ids": [
                    Command.create({
                        "quantity": 1,
                        "price_unit": price,
                        "tax_ids": [Command.set(wht_tax.ids)],
                    }),
                ],
            })
            bill.action_post()
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=bill.ids,
            ).create({})._create_payments()

    def test_01_master_data_migration(self):
        """Run 1: taxes, PIT tables, branch identifiers."""
        before = self._legacy_fingerprint()
        run = self.env["l10n_th.migrate.run"].create({"source_dsn": self.legacy_dsn})
        run.action_run()

        self.assertEqual(run.state, "done", f"run.error_message={run.error_message} stats={run.stats}")
        self.assertEqual(run.stats["withholding_taxes"]["mapped"], 2)
        self.assertEqual(run.stats["pit_tables"]["mapped"], 1)
        self.assertEqual(run.stats["branch_identifiers"]["mapped"], 1)

        wht = self.env["account.tax"].search(
            [("name", "=", "WHT 3% ค่าบริการ/จ้างทำของ")],
        )
        self.assertTrue(wht.is_withholding_tax)
        self.assertEqual(wht.amount, -3.0)

        table = self.env["l10n_th.pit.table"].search(
            [("calendar_year", "=", "2569")],
        )
        self.assertEqual(len(table.rate_ids), 3)

        self.vendor.invalidate_recordset(["additional_identifiers"])
        self.assertEqual(
            self.vendor.additional_identifiers["TH_BRANCH_CODE"], "00007",
        )

        # legacy-only evidence archived verbatim (2 WHT moves + 1 novat)
        self.assertEqual(run.stats["archived_rows"], 3)

        # source DB untouched
        self.assertEqual(self._legacy_fingerprint(), before)

        # keep the mapped tax for the accounting test
        self.env["ir.config_parameter"].sudo().set_str(
            "l10n_th_migrate.test_wht_tax_id", str(wht.id),
        )

    def test_02_accounting_and_reconciliation(self):
        """Run 2 (after the migrated accounting is posted): tax invoice
        evidence lands on the matching bills and the withholding totals
        reconcile before vs after."""
        self.test_01_master_data_migration()
        wht = self.env["account.tax"].browse(
            int(self.env["ir.config_parameter"].sudo().get_str(
                "l10n_th_migrate.test_wht_tax_id",
            )),
        )
        rent = self.env["account.tax"].search([("name", "=", "WHT 5% ค่าเช่า")], limit=1)
        self._create_mirror_accounting([
            ("BILL/2026/08/0001", 100000.0, wht),
            ("BILL/2026/09/0002", 200000.0, rent),
        ])

        run = self.env["l10n_th.migrate.run"].create({"source_dsn": self.legacy_dsn})
        run.action_run()

        self.assertEqual(run.state, "done", f"run.error_message={run.error_message} stats={run.stats}")
        self.assertEqual(run.stats["tax_invoice_evidence"]["mapped"], 1)

        bill = self.env["account.move"].search(
            [
                ("ref", "=", "BILL/2026/08/0001"),
                ("move_type", "in", ("in_invoice", "in_receipt")),
            ],
        )
        self.assertEqual(
            bill.l10n_th_vendor_tax_invoice_number, "V-TI-2569-0001",
        )

        # reconciliation: legacy WHT evidence == official withholding lines
        self.assertEqual(
            run.stats["reconciliation"]["legacy_wht_total"], 13000.0,
        )
        self.assertEqual(
            run.stats["reconciliation"]["official_wht_total"], 13000.0,
        )
        self.assertTrue(run.stats["reconciliation"]["matched"])

        # archive holds the legacy-only rows (2 WHT moves + 1 novat), twice
        # archived because both runs archive
        self.assertEqual(
            self.env["l10n_th.migrate.archive"].search_count([]), 6,
        )
