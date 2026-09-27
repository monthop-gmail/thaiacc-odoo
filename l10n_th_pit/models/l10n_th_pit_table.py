# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
# Progressive withholding logic ported from the proven OCA l10n_th_account_tax
# implementation (personal_income_tax.calculate_rate_wht).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class L10nThPitTable(models.Model):
    _name = "l10n_th.pit.table"
    _description = "Thai PIT Rate Table"
    _rec_name = "calendar_year"

    calendar_year = fields.Char(
        required=True,
        default=lambda self: fields.Date.context_today(self).strftime("%Y"),
        copy=False,
    )
    rate_ids = fields.One2many(
        comodel_name="l10n_th.pit.rate",
        inverse_name="table_id",
        string="Rates",
        copy=True,
    )
    active = fields.Boolean(default=True)

    _calendar_year_unique = models.Constraint(
        "UNIQUE(calendar_year)",
        "Only one rate table per calendar year.",
    )

    @api.constrains("rate_ids")
    def _check_rate_ids(self):
        for table in self:
            previous_to = 0.0
            for i, rate in enumerate(table.rate_ids.sorted("sequence")):
                if i == 0 and not float_is_zero(rate.income_from, 2):
                    raise UserError(
                        self.env._("The first bracket must start from 0.0"),
                    )
                if i > 0 and float_compare(rate.income_from, previous_to, 2) != 0:
                    raise UserError(
                        self.env._(
                            "Discontinued income range! Income From must equal "
                            "the previous Income To.",
                        ),
                    )
                previous_to = rate.income_to

    @api.model
    def _get_table(self, pit_date):
        table = self.search(
            [("calendar_year", "=", pit_date.strftime("%Y"))],
            limit=1,
        ) or self.search([("calendar_year", "<", pit_date.strftime("%Y"))], limit=1)
        if not table:
            raise UserError(
                self.env._(
                    "No PIT rate table found for %s. Create one under "
                    "ThaiACC / PIT Rate Tables.",
                    pit_date.strftime("%Y"),
                ),
            )
        return table

    def _total_tax(self, income):
        """Progressive tax over a yearly income, summing every bracket."""
        self.ensure_one()
        tax = 0.0
        for rate in self.rate_ids.sorted("sequence"):
            if float_compare(income, rate.income_from, 2) <= 0:
                break
            taxable = min(income, rate.income_to) - rate.income_from
            tax += taxable * (rate.tax_rate / 100)
        return tax

    def _marginal_wht(self, total_income, increment, company_currency):
        """Withholding on `increment` given the payee's accumulated
        `total_income` for the year: full-year progressive tax on the new
        total minus the tax already accrued on the accumulated amount."""
        self.ensure_one()
        if float_is_zero(increment, 2):
            return 0.0
        expected = self._total_tax(total_income + increment) - self._total_tax(
            total_income,
        )
        return company_currency.round(expected)

    def _compute_expected_wht(
        self,
        partner,
        base_amount,
        pit_date,
        currency,
        company,
        exclude_payment=None,
    ):
        """Marginal PIT for one payment line: the payee's yearly accumulated
        base (read from the official withholding lines — no extra ledger) plus
        this payment's base, taxed progressively; only the increment's share
        is withheld now."""
        self.ensure_one()
        base_company = currency._convert(
            base_amount, company.currency_id, company, pit_date,
        )
        yearly = self._get_yearly_base(
            partner, pit_date, company, exclude_payment=exclude_payment,
        )
        # _marginal_wht adds the increment internally: total_before is the
        # payee's accumulated base, the increment is this payment's base.
        expected = self._marginal_wht(
            yearly, base_company, company.currency_id,
        )
        if currency != company.currency_id:
            expected = company.currency_id._convert(
                expected, currency, company, pit_date,
            )
        return expected

    def _get_yearly_base(self, partner, pit_date, company, exclude_payment=None):
        """Sum the official payment withholding lines of this payee for the
        calendar year — official data is the single source of truth."""
        PaymentLine = self.env["account.payment.withholding.line"]
        year_start = pit_date.replace(month=1, day=1)
        year_end = pit_date.replace(month=12, day=31)
        domain = [
            ("tax_id.l10n_th_is_pit", "=", True),
            ("payment_id.partner_id", "=", partner.id),
            ("payment_id.date", ">=", fields.Date.to_date(year_start)),
            ("payment_id.date", "<=", fields.Date.to_date(year_end)),
            ("payment_id.company_id", "=", company.id),
            # Only already-posted payments count: the payment currently
            # being computed is still in draft, which keeps it out of its
            # own accumulation without relying on exclude_payment.
            ("payment_id.move_id.state", "=", "posted"),
        ]
        if exclude_payment:
            domain.append(("payment_id", "!=", exclude_payment.id))
        lines = PaymentLine.search(domain)
        total = 0.0
        for line in lines:
            line_currency = line.comodel_currency_id or line.comodel_company_currency_id
            total += line_currency._convert(
                line.base_amount, company.currency_id, company, line.comodel_date or pit_date,
            )
        return total


class L10nThPitRate(models.Model):
    _name = "l10n_th.pit.rate"
    _description = "Thai PIT Rate Line"
    _order = "sequence, id"

    table_id = fields.Many2one(
        comodel_name="l10n_th.pit.table",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    income_from = fields.Float(string="Income From", required=True)
    income_to = fields.Float(string="Income To", required=True)
    tax_rate = fields.Float(string="Rate %", required=True)
