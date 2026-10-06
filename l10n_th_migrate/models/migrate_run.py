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
    "payment_evidence": "SELECT p.id, p.amount, p.state, p.invoice_move_id, m.ref AS bill_reference FROM legacy19.account_payment_evidence p JOIN legacy19.account_move m ON m.id = p.invoice_move_id ORDER BY p.id",
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
    caba_policy_decision = fields.Char(
        string="CABA Policy Decision",
        default="dec-24252acf",
        help="ai-collab decision record that authorizes the "
        "official-canonical CABA over-claim policy for this run.",
    )
    caba_policy_decided_by = fields.Char(
        string="CABA Policy Decided By",
        default="owner",
    )

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

    def _caba_policy(self):
        """Approved policy for legacy CABA over-claims (dec-24252acf): the
        official Odoo 20 CABA result is canonical; legacy rows are archived
        evidence with a cross-reference, never rebooked on the target."""
        return self.env["ir.config_parameter"].sudo().get_str(
            "l10n_th_migrate.caba_over_claim_policy", "",
        )

    def _legacy_payment_evidence(self, conn):
        """Posted legacy payments per bill reference when the source exposes
        payment evidence; ``None`` when it does not, in which case full
        settlement on the target carries the payment check alone."""
        try:
            rows = self._fetch_legacy(conn, "payment_evidence")
        except Exception:  # noqa: BLE001 — a source without payment views
            conn.rollback()
            return None
        paid = {}
        for row in rows:
            if row["state"] == "posted":
                paid[row["bill_reference"]] = (
                    paid.get(row["bill_reference"], 0.0)
                    + abs(float(row["amount"] or 0.0))
                )
        return paid

    def _accept_caba_over_claims(self, conn, report):
        """dec-24252acf: with the ``official_canonical`` policy parameter set
        and the run's decision binding present, a legacy CABA row is accepted
        as over-claim evidence only when the per-bill arithmetic proves the
        over-claim:

        * the target bill is unique, posted and fully settled;
        * the legacy payments for the bill migrated with it (when the
          source exposes payment evidence);
        * legacy CABA VAT for the bill minus the official target CABA VAT
          equals the VAT of that bill's remaining unresolved rows — that
          difference is the recorded over-claim, never a hidden missing
          payment.

        The accepted over-claim must then exactly explain the run's VAT
        delta or the run stays in manual review. The books are not touched."""
        caba = report["caba_tax_invoices"]
        if not caba["unresolved"] or self._caba_policy() != "official_canonical":
            return
        if not self.caba_policy_decision:
            return
        rows = {
            row["id"]: row
            for row in self._fetch_legacy(conn, "tax_invoice_evidence")
        }
        legacy_paid = self._legacy_payment_evidence(conn)
        per_bill = {}
        for legacy_id in caba["unresolved"]:
            row = rows.get(legacy_id)
            if row:
                per_bill.setdefault(row["bill_reference"], []).append(
                    (legacy_id, row),
                )
        accepted = []
        accepted_over_claim_total = 0.0
        for bill_ref, items in per_bill.items():
            bills = self.env["account.move"].search([
                ("ref", "=", bill_ref),
                ("move_type", "in", ("in_invoice", "in_receipt")),
                ("state", "=", "posted"),
                ("company_id", "=", self.env.company.id),
            ])
            if len(bills) != 1:
                continue
            bill = bills
            if abs(bill.amount_residual) > 0.01:
                # A partially settled bill cannot prove an over-claim: an
                # unresolved row may simply be a payment that never
                # migrated, and accepting it would hide the gap.
                continue
            if legacy_paid is not None:
                target_paid = bill.amount_total - bill.amount_residual
                if abs(target_paid - legacy_paid.get(bill_ref, 0.0)) > 0.01:
                    continue
            bill_rows = [
                row for row in rows.values()
                if row["bill_reference"] == bill_ref and row["is_cash_basis"]
            ]
            legacy_vat = sum(
                abs(float(row["vat_amount"] or 0.0)) for row in bill_rows
            )
            target_invoices = bill.l10n_th_tax_invoice_ids.filtered(
                lambda ti: ti.payment_move_id and ti.state == "posted",
            )
            target_vat = sum(abs(ti.vat_amount) for ti in target_invoices)
            over_claim = round(legacy_vat - target_vat, 2)
            unresolved_vat = round(sum(
                abs(float(row["vat_amount"] or 0.0)) for _, row in items
            ), 2)
            if over_claim <= 0 or abs(over_claim - unresolved_vat) > 0.01:
                continue
            archives = [
                self.env["l10n_th.migrate.archive"].search([
                    ("run_id", "=", self.id),
                    ("source_table", "=",
                     "legacy19.account_tax_invoice_evidence"),
                    ("legacy_id", "=", legacy_id),
                ], limit=1)
                for legacy_id, _row in items
            ]
            if not all(archives):
                continue
            for (legacy_id, row), archive in zip(items, archives):
                archive.write({
                    "xref_model": "account.move",
                    "xref_res_id": bill.id,
                    "over_claim_amount": over_claim,
                    "note": (
                        "Legacy CABA over-claim: legacy evidence VAT %s "
                        "against official CABA VAT %s on this bill — "
                        "over-claim %s (the legacy engine re-claimed VAT "
                        "on a payment). The official Odoo 20 CABA result "
                        "is canonical per %s — evidence only, not "
                        "rebooked." % (
                            row["vat_amount"], target_vat, over_claim,
                            self.caba_policy_decision,
                        )
                    ),
                })
                accepted.append(legacy_id)
            accepted_over_claim_total += over_claim
        report["caba_tax_invoices"].update({
            "policy": "official_canonical",
            "decision": self.caba_policy_decision,
            "decided_by": self.caba_policy_decided_by,
            "accepted_over_claim_ids": accepted,
            "accepted_over_claim_total": round(accepted_over_claim_total, 2),
        })

    def _flag_pnd_form_review(self, conn, report):
        """dec-a92c38dc: the legacy income_tax_form selection (pnd1/2/3/
        3a/53) cannot express pnd1a, so no row may be auto-filed as PND1A.
        Posted PIT withholding moves are queued for manual form
        classification on the target; the archive keeps them verbatim."""
        taxes = {
            row["id"]: row
            for row in self._fetch_legacy(conn, "withholding_taxes")
        }
        pit_move_ids = [
            row["id"]
            for row in self._fetch_legacy(conn, "withholding_moves")
            if row["state"] == "posted"
            and taxes.get(row["withholding_tax_id"], {}).get("is_pit")
        ]
        report["pnd_form_review_queue"] = {
            "decision": "dec-a92c38dc",
            "reason": "legacy income_tax_form cannot express pnd1a",
            "legacy_rows": len(pit_move_ids),
            "move_ids": pit_move_ids,
            "auto_filed_pnd1a": 0,
        }

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
            ("move_type", "in", ["in_invoice", "in_receipt", "out_invoice",
                                 "out_refund", "in_refund"]),
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
        caba = report["caba_tax_invoices"]
        accepted_ids = set(caba.get("accepted_over_claim_ids", []))
        accepted_total = caba.get("accepted_over_claim_total", 0.0)
        # dec-24252acf waiver: the accepted over-claims must cover every
        # unresolved row AND exactly explain the VAT delta, otherwise the
        # run keeps its manual-review flag.
        caba_waived = (
            bool(accepted_ids)
            and set(caba["unresolved"]) <= accepted_ids
            and abs(caba["vat_delta"] + accepted_total) < 0.01
        )
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
            "unresolved_caba_tax_invoice_ids": caba["unresolved"],
            "caba_vat_delta": caba["vat_delta"],
            "caba_over_claim_policy": caba.get("policy") or False,
            "caba_over_claim_decision": caba.get("decision") or False,
            "caba_over_claim_total": accepted_total,
            "caba_over_claim_waived": caba_waived,
            "pnd_form_review_queue": report.get(
                "pnd_form_review_queue", {}).get("legacy_rows", 0),
            "duplicate_tax_names": report["duplicate_taxes"],
            "requires_manual_review": bool(
                balance["target_missing_refs"]
                or balance["debit_delta"]
                or balance["credit_delta"]
                or not wht["matched"]
                or report["pnd_entity_types"]["unresolved"]
                or report["banks"]["unresolved"]
                or report["tax_invoice_evidence"]["unresolved"]
                or (caba["unresolved"] and not caba_waived)
                or (caba["vat_delta"] and not caba_waived)
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
                    run._accept_caba_over_claims(conn, report)
                    run._archive_certificates(conn, report)
                    run._flag_pnd_form_review(conn, report)
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
