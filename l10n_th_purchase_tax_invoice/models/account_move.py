# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.float_utils import float_is_zero


class AccountMove(models.Model):
    """Purchase-side (vendor) Thai tax invoices.

    Official l10n_th only creates tax invoices for customer documents
    (out_invoice / out_receipt). Thai buyers must also keep the vendor's tax
    invoice (ใบกำกับภาษีซื้อ) as input-VAT evidence, and cash-basis purchase
    VAT needs a tax invoice at payment time — this module fills both gaps on
    the official l10n_th.tax.invoice model instead of introducing a new one.
    """

    _inherit = "account.move"

    l10n_th_vendor_tax_invoice_number = fields.Char(
        string="Vendor's Tax Invoice Number",
        copy=False,
        help="Tax invoice number as printed on the vendor's original document. "
        "Stored on the tax invoice record as evidence for input VAT.",
    )
    l10n_th_vendor_tax_invoice_date = fields.Date(
        string="Vendor's Tax Invoice Date",
        copy=False,
    )

    def _l10n_th_vendor_moves_domain(self, additional_domain=None):
        domain = self._get_th_moves_domain(
            Domain([("move_type", "in", ("in_invoice", "in_receipt"))]),
        )
        return Domain.AND([domain, additional_domain]) if additional_domain else domain

    def _update_or_create_l10n_th_vendor_tax_invoice(self):
        """Create or update the vendor tax invoice from the vendor's document
        details, using the official on-invoice computation helpers."""

        tax_invoice_vals = []

        for move in self:
            vendor_exigible_lines = move._get_exigible_invoice_lines(
                tax_exigibility="on_invoice",
            )
            tax_invoice = move.l10n_th_tax_invoice_ids.filtered(
                lambda ti: not ti.payment_move_id and ti.state != "cancel",
            )[:1]

            if not vendor_exigible_lines:
                tax_invoice.state = "cancel"
                continue

            base_lines = move._get_th_tax_invoice_base_lines(vendor_exigible_lines)
            tax_totals = move._get_th_tax_invoice_totals(
                base_lines,
                tax_exigibility="on_invoice",
            )

            tax_invoice_val = {
                "invoice_move_id": move.id,
                "date": move.l10n_th_vendor_tax_invoice_date or move.invoice_date,
                "tax_invoice_number": move.l10n_th_vendor_tax_invoice_number or False,
                "reference": False,
                "total_amount": tax_totals["total_amount"],
                "vat_amount": tax_totals["vat_amount"],
                "tax_group_amounts": tax_totals["tax_group_amounts"],
                "tax_invoice_lines": move._get_th_tax_invoice_line_data(
                    base_lines,
                    tax_exigibility="on_invoice",
                )[0],
            }

            if tax_invoice:
                tax_invoice.write(tax_invoice_val)
            else:
                tax_invoice_vals.append(tax_invoice_val)

        self.env["l10n_th.tax.invoice"].with_context(
            l10n_th_vendor_tax_invoice=True,
        ).create(tax_invoice_vals)

    def _create_l10n_th_vendor_tax_invoices_from_caba_entries(self):
        """Create Thai tax invoices for vendor-bill cash-basis (payment-time
        input VAT) entries — the purchase mirror of the official sales flow."""

        th_cash_basis_entries = self.filtered_domain(
            self._get_th_moves_domain(
                Domain(
                    "tax_cash_basis_origin_move_id.move_type",
                    "in",
                    ("in_invoice", "in_receipt"),
                ),
            ),
        )

        tax_invoice_vals = []

        ratio_per_partial = {
            partial_vals["partial"].id: partial_vals["percentage"]
            for move_values in th_cash_basis_entries.tax_cash_basis_rec_id._collect_tax_cash_basis_values().values()
            for partial_vals in move_values.get("partials", [])
        }

        for entry in th_cash_basis_entries:
            original_move = entry.tax_cash_basis_origin_move_id
            payment_exigible_lines = original_move._get_exigible_invoice_lines(
                "on_payment",
            )
            payment_exigible_base_lines = original_move._get_th_tax_invoice_base_lines(
                payment_exigible_lines,
            )
            tax_group_amounts = {}
            tax_amount = 0.0

            for line in entry.line_ids.filtered("tax_line_id"):
                tax_group = line.tax_line_id.tax_group_id
                tax_group_amounts.setdefault(
                    tax_group.id,
                    {
                        "group_name": tax_group.name,
                        "amount": 0.0,
                    },
                )
                tax_group_amounts[tax_group.id]["amount"] += abs(line.amount_currency)
                tax_amount += abs(line.amount_currency)

            ratio = ratio_per_partial.get(entry.tax_cash_basis_rec_id.id, 1.0)
            tax_invoice_lines, total_tax_included_amount = (
                original_move._get_th_tax_invoice_line_data(
                    payment_exigible_base_lines,
                    tax_exigibility="on_payment",
                    ratio=ratio,
                )
            )
            total_amount = abs(entry.amount_total_in_currency_signed)
            amount_paid = sum(
                ti.total_amount
                for ti in original_move.l10n_th_tax_invoice_ids
                if ti.payment_move_id and ti.state != "cancel"
            )

            tax_invoice_vals.append(
                {
                    "invoice_move_id": original_move.id,
                    "payment_move_id": entry.id,
                    "reference": entry.name,
                    "date": entry.date,
                    "total_amount": total_amount,
                    "vat_amount": tax_amount,
                    "amount_residual": total_tax_included_amount
                    - amount_paid
                    - total_amount,
                    "total_on_payment_amount": total_tax_included_amount,
                    "tax_group_amounts": list(tax_group_amounts.values()),
                    "is_partially_paid": not float_is_zero(
                        total_tax_included_amount - total_amount,
                        precision_digits=2,
                    ),
                    "tax_invoice_lines": tax_invoice_lines,
                    "state": "posted",
                },
            )

        self.env["l10n_th.tax.invoice"].with_context(
            l10n_th_vendor_tax_invoice=True,
        ).create(tax_invoice_vals)

    def _post(self, soft=True):
        res = super()._post(soft=soft)

        th_vendor_moves = self.filtered_domain(
            self._l10n_th_vendor_moves_domain(Domain([("state", "=", "posted")])),
        )
        th_vendor_moves._update_or_create_l10n_th_vendor_tax_invoice()
        th_vendor_moves.l10n_th_tax_invoice_ids.filtered(
            lambda tax_invoice: tax_invoice.state == "draft",
        ).state = "posted"

        return res

    def button_draft(self):
        th_vendor_moves = self.filtered_domain(self._l10n_th_vendor_moves_domain())
        th_vendor_moves.l10n_th_tax_invoice_ids.filtered(
            lambda tax_invoice: (
                tax_invoice.state == "posted" and not tax_invoice.payment_move_id
            ),
        ).state = "draft"

        return super().button_draft()

    def button_cancel(self):
        th_vendor_moves = self.filtered_domain(self._l10n_th_vendor_moves_domain())
        th_vendor_moves.l10n_th_tax_invoice_ids.filtered(
            lambda tax_invoice: (
                tax_invoice.state != "cancel" and not tax_invoice.payment_move_id
            ),
        ).state = "cancel"

        return super().button_cancel()

    def write(self, vals):
        res = super().write(vals)
        if {"l10n_th_vendor_tax_invoice_number", "l10n_th_vendor_tax_invoice_date"} & set(
            vals,
        ):
            posted_moves = self.filtered_domain(
                self._l10n_th_vendor_moves_domain(Domain("state", "=", "posted")),
            )
            for move in posted_moves:
                tax_invoice = move.l10n_th_tax_invoice_ids.filtered(
                    lambda ti: not ti.payment_move_id and ti.state != "cancel",
                )[:1]
                if tax_invoice:
                    tax_invoice.write(
                        {
                            "tax_invoice_number": move.l10n_th_vendor_tax_invoice_number
                            or False,
                            "date": move.l10n_th_vendor_tax_invoice_date
                            or move.invoice_date,
                        },
                    )
        return res
