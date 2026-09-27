# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, models

_VENDOR_NUMBER_PLACEHOLDER = "_l10n_th_vendor_tax_invoice_"


class L10nThTaxInvoice(models.Model):
    _inherit = "l10n_th.tax.invoice"

    @api.model_create_multi
    def create(self, vals_list):
        """Vendor tax invoices carry the vendor's own document number, which
        is frequently not yet known when the bill posts. The official create()
        auto-generates a number from the company receipt sequence when it is
        empty — that must not happen here (it would both lie about the vendor
        document and consume sales sequence numbers), so fill a placeholder
        for the auto-number check and clear it right after creation."""

        is_vendor = self.env.context.get("l10n_th_vendor_tax_invoice")
        if is_vendor:
            for vals in vals_list:
                if not vals.get("tax_invoice_number"):
                    vals["tax_invoice_number"] = _VENDOR_NUMBER_PLACEHOLDER

        invoices = super().create(vals_list)

        if is_vendor:
            invoices.filtered(
                lambda ti: ti.tax_invoice_number == _VENDOR_NUMBER_PLACEHOLDER,
            ).tax_invoice_number = False

        return invoices
