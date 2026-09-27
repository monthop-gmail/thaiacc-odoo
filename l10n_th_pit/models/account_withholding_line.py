# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, models


class AccountWithholdingLine(models.AbstractModel):
    """Progressive PIT on the official withholding lines: taxes flagged
    ``l10n_th_is_pit`` replace the flat-percentage amount with the marginal
    computation from the Thai PIT rate table."""

    _inherit = "account.withholding.line"

    def _compute_amount(self):
        super()._compute_amount()
        pit_lines = self.filtered(
            lambda line: line.tax_id.l10n_th_is_pit and line.base_amount,
        )
        if not pit_lines:
            return
        for line in pit_lines:
            partner = line._get_comodel_partner()
            comodel_date = line.comodel_date
            currency = line.comodel_currency_id or line.comodel_company_currency_id
            company = line.comodel_company_currency_id and line.company_id or line.company_id
            if not partner or not comodel_date:
                continue
            table = self.env["l10n_th.pit.table"]._get_table(comodel_date)
            expected = table._compute_expected_wht(
                partner,
                line.base_amount,
                comodel_date,
                currency,
                line.company_id,
                exclude_payment=getattr(line, "payment_id", None) or None,
            )
            # The engine carries withholding magnitudes positive on the
            # lines; signs are applied when the AMLs are created.
            line.amount = abs(expected)
