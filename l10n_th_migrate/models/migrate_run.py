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
    "withholding_taxes": "SELECT id, name, amount, income_tax_form, is_pit FROM legacy19.account_withholding_tax ORDER BY id",
    "partners": "SELECT id, name, vat, is_company, company_registry FROM legacy19.res_partner ORDER BY id",
    "company_novat": "SELECT company_id, novat FROM legacy19.res_company_novat ORDER BY company_id",
    "withholding_moves": "SELECT id, partner_id, date, state, base_amount, wht_amount, withholding_tax_id, bill_reference FROM legacy19.account_withholding_move ORDER BY id",
    "tax_invoice_evidence": "SELECT id, bill_reference, tax_invoice_number, tax_invoice_date, is_cash_basis, vat_amount FROM legacy19.account_tax_invoice_evidence ORDER BY id",
    "pit_tables": "SELECT id, calendar_year FROM legacy19.personal_income_tax ORDER BY id",
    "account_moves": "SELECT id, ref, move_type, state, partner_id, date, amount_total FROM legacy19.account_move ORDER BY id",
    "account_move_lines": "SELECT id, move_id, account_code, debit, credit FROM legacy19.account_move_line ORDER BY id",
    "banks": "SELECT id, partner_id, acc_number, bank_name, promptpay_id FROM legacy19.partner_bank ORDER BY id",
    "certs": "SELECT id, withholding_move_id, cert_number, income_type FROM legacy19.account_withholding_cert ORDER BY id",
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
        group = self.env["account.tax.group"].search(
            [("name", "ilike", "WHT")], limit=1,
        ) or self.env["account.tax.group"].create({"name": "Withholding Tax (WHT)"})
        created = {}
        for row in rows:
            existing = Tax.search(
                [("name", "=", row["name"]), ("is_withholding_tax", "=", True),
                 ("company_id", "=", self.env.company.id)],
                limit=1,
            )
            if existing:
                # align the fiscal country (an existing same-name tax may
                # predate the company's fiscal-country setting — e.g. demo)
                fiscal = self.env.company.account_fiscal_country_id
                if fiscal and existing.country_id != fiscal:
                    existing.country_id = fiscal.id
                created[row["id"]] = existing
                continue
            vals = map_withholding_tax(row, self.env.company.id, group.id)
            created[row["id"]] = Tax.create(vals)
            # mapped taxes must belong to the company's fiscal country.
            # Write AFTER create: country_id is a stored compute depending on
            # company_id, so an explicit value inside create vals gets
            # recomputed (create carries company_id) and silently lost.
            fiscal = self.env.company.account_fiscal_country_id
            if fiscal:
                created[row["id"]].country_id = fiscal.id
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
        classified = 0
        unresolved = []
        for row in rows:
            domain = [("vat", "=", row["vat"])] if row["vat"] else [
                ("name", "=", row["name"]),
            ]
            matches = Partner.search(domain)
            if len(matches) != 1:
                unresolved.append(row["id"])
                continue
            partner = matches
            partner.l10n_th_pnd_entity_type = (
                "company" if row["is_company"] else "person"
            )
            classified += 1
            identifiers = map_branch_identifier(row["company_registry"])
            if identifiers:
                partner.write({
                    "additional_identifiers": {
                        **(partner.additional_identifiers or {}), **identifiers,
                    },
                })
                mapped += 1
        report["branch_identifiers"] = {
            "legacy_rows": sum(bool(r["company_registry"]) for r in rows),
            "mapped": mapped,
        }
        report["pnd_entity_types"] = {
            "legacy_rows": len(rows), "mapped": classified, "unresolved": unresolved,
        }

    def _map_tax_invoice_evidence(self, conn, report):
        vendor_refs = {
            move["ref"] for move in self._fetch_legacy(conn, "account_moves")
            if move["move_type"] in ("in_invoice", "in_receipt")
            and move["state"] == "posted"
        }
        rows = [
            row for row in self._fetch_legacy(conn, "tax_invoice_evidence")
            if row["bill_reference"] in vendor_refs and not row["is_cash_basis"]
        ]
        Move = self.env["account.move"]
        mapped = 0
        unresolved = []
        for row in rows:
            matches = Move.search(
                [
                    ("ref", "=", row["bill_reference"]),
                    ("move_type", "in", ("in_invoice", "in_receipt")),
                    ("state", "=", "posted"),
                    ("company_id", "=", self.env.company.id),
                ],
            )
            if len(matches) != 1:
                unresolved.append(row["id"])
                continue
            matches.write(
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
            "unresolved": unresolved,
        }

    def _reconcile_caba_tax_invoices(self, conn, report):
        """Keep payment-time tax invoices distinct from bill-level evidence."""
        vendor_refs = {
            move["ref"] for move in self._fetch_legacy(conn, "account_moves")
            if move["move_type"] in ("in_invoice", "in_receipt")
            and move["state"] == "posted"
        }
        rows = [
            row for row in self._fetch_legacy(conn, "tax_invoice_evidence")
            if row["is_cash_basis"] and row["bill_reference"] in vendor_refs
        ]
        by_ref = {}
        for row in rows:
            by_ref.setdefault(row["bill_reference"], []).append(row)

        mapped = 0
        unresolved = []
        target_vat = 0.0
        for ref, source_invoices in by_ref.items():
            bills = self.env["account.move"].search([
                ("ref", "=", ref),
                ("move_type", "in", ("in_invoice", "in_receipt")),
                ("state", "=", "posted"),
                ("company_id", "=", self.env.company.id),
            ])
            if len(bills) != 1:
                unresolved.extend(row["id"] for row in source_invoices)
                continue
            target_invoices = bills.l10n_th_tax_invoice_ids.filtered(
                lambda ti: ti.payment_move_id and ti.state == "posted"
            )
            target_bill_vat = sum(abs(ti.vat_amount) for ti in target_invoices)
            target_vat += target_bill_vat
            unused = target_invoices
            for row in source_invoices:
                source_amount = abs(float(row["vat_amount"] or 0.0))
                candidates = unused.filtered(
                    lambda ti: abs(abs(ti.vat_amount) - source_amount) < 0.01
                )
                if len(candidates) != 1:
                    unresolved.append(row["id"])
                    continue
                candidates.write({
                    "tax_invoice_number": row["tax_invoice_number"],
                    "date": row["tax_invoice_date"],
                })
                unused -= candidates
                mapped += 1

        source_vat = sum(abs(float(row["vat_amount"] or 0.0)) for row in rows)
        report["caba_tax_invoices"] = {
            "legacy_rows": len(rows),
            "mapped": mapped,
            "unresolved": unresolved,
            "source_vat": round(source_vat, 2),
            "target_vat": round(target_vat, 2),
            "vat_delta": round(target_vat - source_vat, 2),
        }

    def _archive_legacy_only(self, conn, report):
        """Archive legacy WHT, novat, and CABA tax-invoice evidence."""
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
        for row in self._fetch_legacy(conn, "tax_invoice_evidence"):
            if row["is_cash_basis"]:
                Archive.create({
                    "run_id": self.id,
                    "source_table": "legacy19.account_tax_invoice_evidence",
                    "legacy_id": row["id"],
                    "payload": json.loads(json.dumps(row, default=str)),
                })
                count += 1
        report["archived_rows"] = count

    def _trial_balance(self, conn, report):
        """Matrix 1: posted source and target control totals by document ref.

        Source cancelled entries are excluded from the trial balance. Target
        payment entries are outside this document control and reconciled by
        the separate withholding check.
        """
        moves = [
            row for row in self._fetch_legacy(conn, "account_moves")
            if row["state"] == "posted"
        ]
        lines = self._fetch_legacy(conn, "account_move_lines")
        posted_ids = {move["id"] for move in moves}
        lines = [line for line in lines if line["move_id"] in posted_ids]
        debit = sum(float(l["debit"]) for l in lines)
        credit = sum(float(l["credit"]) for l in lines)
        unbalanced = []
        by_move = {}
        for line in lines:
            by_move.setdefault(line["move_id"], []).append(line)
        for move in moves:
            move_lines = by_move.get(move["id"], [])
            move_debit = sum(float(l["debit"]) for l in move_lines)
            move_credit = sum(float(l["credit"]) for l in move_lines)
            if abs(move_debit - move_credit) > 0.01:
                unbalanced.append(move["ref"])
        target_moves = self.env["account.move"].search([
            ("ref", "in", [move["ref"] for move in moves]),
            ("move_type", "in", ["in_invoice", "in_receipt", "out_invoice", "out_refund"]),
            ("state", "=", "posted"),
            ("company_id", "=", self.env.company.id),
        ])
        target_lines = target_moves.line_ids
        target_debit = sum(target_lines.mapped("debit"))
        target_credit = sum(target_lines.mapped("credit"))
        report["trial_balance"] = {
            "legacy_debit": debit,
            "legacy_credit": credit,
            "debit_credit_equal": abs(debit - credit) < 0.01,
            "moves": len(moves),
            "unbalanced_moves": unbalanced,
            "target_debit": target_debit,
            "target_credit": target_credit,
            "target_debit_credit_equal": abs(target_debit - target_credit) < 0.01,
            "target_moves": len(target_moves),
            "target_missing_refs": sorted(
                {move["ref"] for move in moves} - set(target_moves.mapped("ref")),
            ),
            "debit_delta": round(target_debit - debit, 2),
            "credit_delta": round(target_credit - credit, 2),
        }

    def _map_banks(self, conn, report):
        """Matrix 7: map account and PromptPay proxy to official bank fields."""
        rows = self._fetch_legacy(conn, "banks")
        Bank = self.env["res.partner.bank"]
        mapped = 0
        unresolved = []
        for row in rows:
            vat = self._partner_vat(conn, row["partner_id"])
            partners = self.env["res.partner"].search([("vat", "=", vat)]) if vat else self.env["res.partner"]
            if len(partners) != 1:
                unresolved.append(row["id"])
                continue
            partner = partners
            proxy = row["promptpay_id"]
            proxy_type = (
                "merchant_tax_id" if proxy and len(proxy) == 13 and proxy.isdigit()
                else "mobile" if proxy and len(proxy) == 10 and proxy.isdigit()
                else False
            )
            existing = Bank.search(
                [("account_number", "=", row["acc_number"]), ("partner_id", "=", partner.id)],
                limit=1,
            )
            if not existing:
                Bank.create({
                    "account_number": row["acc_number"],
                    "partner_id": partner.id,
                    "proxy_type": proxy_type,
                    "proxy_value": proxy if proxy_type else False,
                })
                mapped += 1
            elif proxy_type:
                existing.write({"proxy_type": proxy_type, "proxy_value": proxy})
                mapped += 1
            if proxy and not proxy_type:
                unresolved.append(row["id"])
        report["banks"] = {
            "legacy_rows": len(rows), "mapped": mapped, "unresolved": unresolved,
        }

    def _partner_vat(self, conn, legacy_partner_id):
        rows = self._fetch_legacy(conn, "partners")
        for row in rows:
            if row["id"] == legacy_partner_id:
                return row["vat"]
        return None

    def _archive_certificates(self, conn, report):
        """Matrix 8: legacy WHT certificates have no official 20.0
        equivalent — archived verbatim, read-only history."""
        Archive = self.env["l10n_th.migrate.archive"]
        count = 0
        for row in self._fetch_legacy(conn, "certs"):
            Archive.create({
                "run_id": self.id,
                "source_table": "legacy19.account_withholding_cert",
                "legacy_id": row["id"],
                "payload": dict(row),
            })
            count += 1
        report["certificates_archived"] = count

    def _no_duplicate_check(self, report, mapped_taxes):
        """Matrix 10: each MAPPED legacy tax must exist exactly once by name.
        The Thai chart legitimately ships several same-name taxes for
        different conditions, so only mapped names are checked."""
        dupes = []
        for tax in mapped_taxes:
            same = self.env["account.tax"].search_count(
                [("name", "=", tax.name), ("company_id", "=", tax.company_id.id),
                 ("is_withholding_tax", "=", True)],
            )
            if same > 1:
                dupes.append(tax.name)
        report["duplicate_taxes"] = dupes

    def _customer_invoice_reconcile(self, conn, report):
        """Matrix 2 (sales side): mirrored customer invoices get official
        sales tax invoices automatically on posting."""
        source_moves = {
            move["ref"] for move in self._fetch_legacy(conn, "account_moves")
            if move["move_type"] == "out_invoice" and move["state"] == "posted"
        }
        rows = [
            row for row in self._fetch_legacy(conn, "tax_invoice_evidence")
            if row["bill_reference"] in source_moves
        ]
        found = 0
        for row in rows:
            move = self.env["account.move"].search(
                [
                    ("ref", "=", row["bill_reference"]),
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )
            if move and move.l10n_th_tax_invoice_ids:
                found += 1
        report["customer_tax_invoices"] = {"legacy_rows": len(rows), "with_official_ti": found}

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

    def _summarize(self, report):
        """One audit view of the checks and the evidence still needed."""
        balance = report["trial_balance"]
        wht = report["reconciliation"]
        report["reconciliation_summary"] = {
            "source_balanced": balance["debit_credit_equal"] and not balance["unbalanced_moves"],
            "target_balanced": balance["target_debit_credit_equal"],
            "source_document_count": balance["moves"],
            "target_document_count": balance["target_moves"],
            "missing_document_refs": balance["target_missing_refs"],
            "document_debit_delta": balance["debit_delta"],
            "document_credit_delta": balance["credit_delta"],
            "wht_delta": round(wht["official_wht_total"] - wht["legacy_wht_total"], 2),
            "unresolved_partner_ids": report["pnd_entity_types"]["unresolved"],
            "unresolved_bank_ids": report["banks"]["unresolved"],
            "unresolved_vendor_tax_invoice_ids": report["tax_invoice_evidence"]["unresolved"],
            "unresolved_caba_tax_invoice_ids": report["caba_tax_invoices"]["unresolved"],
            "caba_vat_delta": report["caba_tax_invoices"]["vat_delta"],
            "duplicate_tax_names": report["duplicate_taxes"],
            "requires_manual_review": bool(
                balance["target_missing_refs"]
                or balance["debit_delta"]
                or balance["credit_delta"]
                or not wht["matched"]
                or report["pnd_entity_types"]["unresolved"]
                or report["banks"]["unresolved"]
                or report["tax_invoice_evidence"]["unresolved"]
                or report["caba_tax_invoices"]["unresolved"]
                or report["caba_tax_invoices"]["vat_delta"]
                or report["duplicate_taxes"]
            ),
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
                    run._map_banks(conn, report)
                    run._map_tax_invoice_evidence(conn, report)
                    run._reconcile_caba_tax_invoices(conn, report)
                    run._archive_legacy_only(conn, report)
                    run._archive_certificates(conn, report)
                    run._trial_balance(conn, report)
                    run._customer_invoice_reconcile(conn, report)
                    run._no_duplicate_check(report, wht_map.values())
                    run._reconcile(conn, wht_map, report)
                    run._summarize(report)
                finally:
                    conn.close()
                run.write({"state": "done", "stats": report, "error_message": False})
            except Exception as exc:  # noqa: BLE001 — report and keep evidence
                run.write({"state": "failed", "error_message": str(exc)})
        return True
