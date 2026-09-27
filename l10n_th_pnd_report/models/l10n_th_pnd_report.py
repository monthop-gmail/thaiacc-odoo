# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models
from odoo.fields import Domain

PND_TYPE_SELECTION = [
    ('pnd1', "P.N.D.1 - Salary (50 (1))"),
    ('pnd1a', "P.N.D.1A - One-time Salary (50 (1))"),
    ('pnd2', "P.N.D.2 - Hire of Work (50 (2))"),
    ('pnd3', "P.N.D.3 - Other Assessable Income (50 (3)-(8))"),
    ('pnd53', "P.N.D.53 - Corporate Payees (50 (1)(2)(3))"),
]

# Default classification of a withholding line into a PND form. Users can
# reclassify lines on the report; the mapping is only the starting point.
_INDIVIDUAL_TYPE_MAP = {
    'service': 'pnd2',
    'contract': 'pnd2',
    'hire_of_work': 'pnd2',
    'commission': 'pnd3',
    'royalties': 'pnd3',
    'interest': 'pnd3',
    'dividend': 'pnd3',
    'rentals': 'pnd3',
    'transportation': 'pnd3',
    'advertising': 'pnd3',
    'insurance': 'pnd3',
    'public_actor': 'pnd3',
    'prize': 'pnd3',
    'others': 'pnd3',
    'prof_fees': 'pnd3',
    'na': 'pnd1',
}


class L10nThPndReport(models.Model):
    _name = "l10n_th.pnd.report"
    _description = "Thai Withholding Tax Return (PND) Report"
    _check_company_auto = True
    _inherit = ["mail.thread", "mail.activity.mixin"]

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    line_ids = fields.One2many(
        comodel_name="l10n_th.pnd.report.line",
        inverse_name="report_id",
        string="Lines",
        copy=False,
    )
    state = fields.Selection(
        selection=[("draft", "Draft"), ("done", "Generated")],
        default="draft",
        required=True,
    )
    total_base_amount = fields.Monetary(compute="_compute_totals")
    total_tax_amount = fields.Monetary(compute="_compute_totals")

    _date_order_check = models.Constraint(
        "CHECK(date_from <= date_to)",
        "The period end date must be on or after the start date.",
    )

    @api.depends("line_ids.base_amount", "line_ids.tax_amount")
    def _compute_totals(self):
        for report in self:
            report.total_base_amount = sum(report.line_ids.mapped("base_amount"))
            report.total_tax_amount = sum(report.line_ids.mapped("tax_amount"))

    def _get_withholding_lines_domain(self):
        """Official payment withholding lines are the single source of truth:
        posted payments of the period with a withholding tax."""
        self.ensure_one()
        return Domain([
            ("payment_id.company_id", "=", self.company_id.id),
            ("payment_id.date", ">=", self.date_from),
            ("payment_id.date", "<=", self.date_to),
            ("payment_id.move_id.state", "=", "posted"),
            ("tax_id.is_withholding_tax", "=", True),
        ])

    def action_generate(self):
        self.ensure_one()
        self.line_ids.unlink()
        PaymentLine = self.env["account.payment.withholding.line"]
        lines = PaymentLine.search(self._get_withholding_lines_domain())

        grouped = {}
        for wline in lines:
            partner = wline.payment_id.partner_id
            tax = wline.tax_id
            pnd_type = self._default_pnd_type(partner, tax)
            key = (partner.id, tax.id, pnd_type)
            entry = grouped.setdefault(
                key,
                {
                    "partner_id": partner.id,
                    "tax_id": tax.id,
                    "pnd_type": pnd_type,
                    "payment_count": 0,
                    "base_amount": 0.0,
                    "tax_amount": 0.0,
                },
            )
            entry["payment_count"] += 1
            entry["base_amount"] += wline.base_amount
            entry["tax_amount"] += wline.amount

        self.env["l10n_th.pnd.report.line"].create(
            [
                {"report_id": self.id, **vals}
                for vals in grouped.values()
            ],
        )
        self.state = "done"
        return True

    @api.model
    def _default_pnd_type(self, partner, tax):
        if partner.l10n_th_pnd_entity_type == "company" or (
            not partner.l10n_th_pnd_entity_type and partner.is_company
        ):
            return "pnd53"
        income_type = tax.l10n_th_income_tax_type or "na"
        return _INDIVIDUAL_TYPE_MAP.get(income_type, "pnd3")


class L10nThPndReportLine(models.Model):
    _name = "l10n_th.pnd.report.line"
    _description = "Thai Withholding Tax Return (PND) Report Line"
    _check_company_auto = True

    report_id = fields.Many2one(
        comodel_name="l10n_th.pnd.report",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="report_id.company_id")
    currency_id = fields.Many2one(related="report_id.currency_id")
    pnd_type = fields.Selection(
        selection=PND_TYPE_SELECTION,
        required=True,
        help="Pre-filled from the payee type and the tax's income type; "
        "reclassify manually when needed.",
    )
    partner_id = fields.Many2one(comodel_name="res.partner", required=True)
    tax_id = fields.Many2one(comodel_name="account.tax")
    income_tax_type = fields.Selection(related="tax_id.l10n_th_income_tax_type")
    payment_count = fields.Integer(string="Payments")
    base_amount = fields.Monetary(string="Income Paid", sum="Total Income")
    tax_amount = fields.Monetary(string="Tax Withheld", sum="Total Withheld")
