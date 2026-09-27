# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

import json

import psycopg2
import psycopg2.extras

from odoo import api, Command, fields, models

from .mapping import (
    map_branch_identifier,
    map_pit_table,
    map_tax_invoice,
    map_withholding_tax,
)

# Every legacy read goes through this view of the tables — the runner never
# issues anything but SELECTs against the source database.
LEGACY_QUERIES = {
    "withholding_taxes": "SELECT id, name, amount, income_tax_form FROM legacy19.account_withholding_tax ORDER BY id",
    "partners": "SELECT id, name, vat, company_registry FROM legacy19.res_partner WHERE company_registry IS NOT NULL AND company_registry <> '' ORDER BY id",
    "company_novat": "SELECT company_id, novat FROM legacy19.res_company_novat ORDER BY company_id",
    "withholding_moves": "SELECT id, partner_id, date, state, base_amount, wht_amount, withholding_tax_id, bill_reference FROM legacy19.account_withholding_move ORDER BY id",
    "tax_invoice_evidence": "SELECT id, bill_reference, tax_invoice_number, tax_invoice_date FROM legacy19.account_tax_invoice_evidence ORDER BY id",
    "pit_tables": "SELECT id, calendar_year FROM legacy19.personal_income_tax ORDER BY id",
    "pit_rates": "SELECT id, pit_id, sequence, income_from, income_to, tax_rate FROM legacy19.personal_income_tax_rate ORDER BY pit_id, sequence",
}


class L10nThMigrateRun(models.Model):
    """One end-to-end execution of the 19→20 migration contract against a
    read-only legacy database. Produces: mapped official records, an archive
    of legacy-only evidence, and a reconciliation report."""

    _name = "l10n_th.migrate.run"
    _description = "Thai 19.0 → 20.0 Migration Run"
    _order = "id desc"

    source_dsn = fields.Char(
        string="Legacy DB DSN",
        required=True,
        help="libpq DSN of the legacy 19.0 database. Connected READ-ONLY.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("done", "Migrated"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
    )
    stats = fields.Json(string="Reconciliation Report", readonly=True)
    archive_ids = fields.One2many(
        comodel_name="l10n_th.migrate.archive",
        inverse_name="run_id",
        string="Archived Legacy Rows",
    )
    error_message = fields.Text(readonly=True)

    # --- source access -------------------------------------------------

    def _connect_source(self):
        """Read-only connection to the legacy database."""
        conn = psycopg2.connect(self.source_dsn)
        conn.set_session(readonly=True, autocommit=True)
        return conn

    @api.model
    def _fetch_legacy(self, conn, key):
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cr:
            cr.execute(LEGACY_QUERIES[key])
            return [dict(row) for row in cr.fetchall()]

    # --- mapping steps (contract rows) ---------------------------------

    def _map_withholding_taxes(self, conn, report):
        rows = self._fetch_legacy(conn, "withholding_taxes")
        Tax = self.env["account.tax"]
        created = {}
        for row in rows:
            existing = Tax.search(
                [("name", "=", row["name"]), ("is_withholding_tax", "=", True)],
                limit=1,
            )
            if existing:
                created[row["id"]] = existing
                continue
            vals = map_withholding_tax(row, self.env.company.id)
            created[row["id"]] = Tax.create(vals)
        report["withholding_taxes"] = {
            "legacy_rows": len(rows),
            "mapped": len(created),
        }
        return created

    def _map_pit_tables(self, conn, report):
        tables = self._fetch_legacy(conn, "pit_tables")
        rates = self._fetch_legacy(conn, "pit_rates")
        PitTable = self.env["l10n_th.pit.table"]
        report["pit_tables"] = {"legacy_rows": len(tables), "mapped": 0}
        for table in tables:
            legacy = {
                "calendar_year": table["calendar_year"],
                "rate_ids": [
                    r for r in rates if r["pit_id"] == table["id"]
                ],
            }
            existing = PitTable.search(
                [("calendar_year", "=", str(table["calendar_year"]))], limit=1,
            )
            if existing:
                report["pit_tables"]["mapped"] += 1
                continue
            vals = map_pit_table(legacy)
            PitTable.create(
                {
                    **vals,
                    "rate_ids": [
                        Command.create(r) for r in vals["rate_ids"]
                    ],
                },
            )
            report["pit_tables"]["mapped"] += 1

    def _map_branch_identifiers(self, conn, report):
        rows = self._fetch_legacy(conn, "partners")
        Partner = self.env["res.partner"]
        mapped = 0
        for row in rows:
            partner = Partner.search([("vat", "=", row["vat"])], limit=1)
            if not partner:
                continue
            identifiers = map_branch_identifier(row["company_registry"])
            if identifiers:
                partner.write({"additional_identifiers": identifiers})
                mapped += 1
        report["branch_identifiers"] = {
            "legacy_rows": len(rows),
            "mapped": mapped,
        }

    def _map_tax_invoice_evidence(self, conn, report):
        rows = self._fetch_legacy(conn, "tax_invoice_evidence")
        Move = self.env["account.move"]
        mapped = 0
        for row in rows:
            move = Move.search(
                [
                    ("ref", "=", row["bill_reference"]),
                    ("move_type", "in", ("in_invoice", "in_receipt")),
                ],
                limit=1,
            )
            if not move:
                continue
            move.write(
                {
                    "l10n_th_vendor_tax_invoice_number": row[
                        "tax_invoice_number"
                    ],
                    "l10n_th_vendor_tax_invoice_date": row["tax_invoice_date"],
                },
            )
            mapped += 1
        report["tax_invoice_evidence"] = {
            "legacy_rows": len(rows),
            "mapped": mapped,
        }

    def _archive_legacy_only(self, conn, report):
        """Contract rows whose engines are not revived: legacy withholding
        moves and the novat flags are archived verbatim."""
        Archive = self.env["l10n_th.migrate.archive"]
        count = 0
        for row in self._fetch_legacy(conn, "withholding_moves"):
            Archive.create(
                {
                    "run_id": self.id,
                    "source_table": "legacy19.account_withholding_move",
                    "legacy_id": row["id"],
                    "payload": json.loads(json.dumps(row, default=str)),
                },
            )
            count += 1
        for row in self._fetch_legacy(conn, "company_novat"):
            Archive.create(
                {
                    "run_id": self.id,
                    "source_table": "legacy19.res_company_novat",
                    "legacy_id": row["company_id"],
                    "payload": dict(row),
                },
            )
            count += 1
        report["archived_rows"] = count

    # --- reconciliation -------------------------------------------------

    def _reconcile(self, conn, wht_map, report):
        """Before vs after: legacy withholding evidence vs official lines on
        the migrated company."""
        legacy_total = sum(
            float(row["wht_amount"])
            for row in self._fetch_legacy(conn, "withholding_moves")
            if row["state"] == "posted"
        )
        wht_tax_ids = [tax.id for tax in wht_map.values()]
        official_total = sum(
            self.env["account.payment.withholding.line"]
            .search(
                [
                    ("tax_id", "in", wht_tax_ids),
                    ("payment_id.move_id.state", "=", "posted"),
                ],
            )
            .mapped("amount"),
        )
        report["reconciliation"] = {
            "legacy_wht_total": legacy_total,
            "official_wht_total": official_total,
            "matched": abs(legacy_total - official_total) < 0.01,
        }

    # --- entry point -----------------------------------------------------

    def action_run(self):
        for run in self:
            report = {}
            try:
                conn = run._connect_source()
                try:
                    wht_map = run._map_withholding_taxes(conn, report)
                    run._map_pit_tables(conn, report)
                    run._map_branch_identifiers(conn, report)
                    run._map_tax_invoice_evidence(conn, report)
                    run._archive_legacy_only(conn, report)
                    run._reconcile(conn, wht_map, report)
                finally:
                    conn.close()
                run.write({"state": "done", "stats": report, "error_message": False})
            except Exception as exc:  # noqa: BLE001 — report and keep evidence
                run.write({"state": "failed", "error_message": str(exc)})
        return True
