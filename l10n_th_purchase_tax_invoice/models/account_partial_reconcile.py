# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def _create_tax_cash_basis_moves(self):
        res = super()._create_tax_cash_basis_moves()
        # Official flow only builds tax invoices for sales-side CABA entries;
        # build the purchase mirror (input VAT on payment) right after.
        res._create_l10n_th_vendor_tax_invoices_from_caba_entries()
        return res
