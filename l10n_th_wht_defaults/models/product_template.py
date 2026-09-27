# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_th_supplier_wht_tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Default WHT (Vendor Bills)",
        domain=[
            ("is_withholding_tax", "=", True),
            ("type_tax_use", "=", "purchase"),
        ],
        help="Withholding tax suggested on vendor bill lines for this "
        "product. Withholding itself is handled by the official "
        "account.tax.is_withholding_tax engine.",
    )
