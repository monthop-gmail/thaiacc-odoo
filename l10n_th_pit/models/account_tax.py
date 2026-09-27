# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_th_is_pit = fields.Boolean(
        string="Progressive PIT",
        help="Withholding amount for this tax is computed from the Thai "
        "progressive personal income tax table (marginal on the payee's "
        "yearly income) instead of the flat tax percentage. Requires "
        "'Withholding Tax' to be set.",
    )
