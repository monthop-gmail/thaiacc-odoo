# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_computed_taxes(self):
        """EXTENDS account: append the product's default purchase withholding
        tax on vendor documents.

        Thai withholding depends on the kind of expense (service, rent,
        transport, ...), which products encode. The official WHT engine
        (l10n_account_withholding_tax) applies whichever withholding taxes
        are present on the line, so defaulting them here is all that is
        needed — no separate WHT engine."""
        tax_ids = super()._get_computed_taxes()
        if not self.move_id.is_purchase_document(include_receipts=True):
            return tax_ids

        product = self.product_id.sudo()
        wht_tax = product.product_tmpl_id.l10n_th_supplier_wht_tax_id
        if not wht_tax:
            return tax_ids

        company = self.move_id.company_id
        if wht_tax.company_id != company:
            return tax_ids

        current = tax_ids if tax_ids else self.env["account.tax"]
        if wht_tax in current.flatten_taxes_hierarchy():
            return tax_ids
        return current | wht_tax
