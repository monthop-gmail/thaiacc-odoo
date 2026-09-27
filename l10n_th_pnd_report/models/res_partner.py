# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_th_pnd_entity_type = fields.Selection(
        selection=[("person", "Individual"), ("company", "Company")],
        help="Explicit Thai withholding classification. Odoo 20 is_company "
             "is derived from VAT presence and can classify an individual "
             "with a tax number as a company.",
    )
