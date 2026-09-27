# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nTHPndReport(AccountTestInvoicingCommon):
    """Normalized PND adapter over official payment withholding lines."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('th')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_th_is_vat_registered = True

        cls.wht_service = cls.env['account.tax'].create({
            'name': 'WHT 3% Services',
            'amount_type': 'percent',
            'amount': -3.0,
            'type_tax_use': 'purchase',
            'is_withholding_tax': True,
            'l10n_th_income_tax_type': 'service',
        })
        cls.wht_rental = cls.env['account.tax'].create({
            'name': 'WHT 5% Rentals',
            'amount_type': 'percent',
            'amount': -5.0,
            'type_tax_use': 'purchase',
            'is_withholding_tax': True,
            'l10n_th_income_tax_type': 'rentals',
        })
        cls.individual = cls.env['res.partner'].create({'name': 'PND Contractor'})
        # Odoo 20.0: is_company is a stored compute = own commercial entity
        # AND a valid VAT — a plain is_company=True in vals is ignored.
        cls.corporate = cls.env['res.partner'].create({
            'name': 'PND Corp Co., Ltd.', 'vat': '0105558000000',
        })

    def _pay_bill(self, partner, tax, price_unit):
        bill = self._create_invoice(
            move_type='in_invoice',
            invoice_date=fields.Date.today(),
            partner_id=partner.id,
            invoice_line_ids=[
                Command.create({'quantity': 1, 'price_unit': price_unit, 'tax_ids': [Command.set(tax.ids)]}),
            ],
        )
        bill.action_post()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bill.ids,
        ).create({})._create_payments()

    def test_report_classification_and_totals(self):
        self._pay_bill(self.individual, self.wht_service, 100000.0)
        self._pay_bill(self.corporate, self.wht_rental, 200000.0)

        report = self.env['l10n_th.pnd.report'].create({
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today(),
        })
        report.action_generate()

        self.assertEqual(report.state, 'done')
        self.assertEqual(len(report.line_ids), 2)

        service_line = report.line_ids.filtered(
            lambda l: l.partner_id == self.individual,
        )
        self.assertEqual(service_line.pnd_type, 'pnd2')
        self.assertAlmostEqual(service_line.base_amount, 100000.0, 2)
        self.assertAlmostEqual(service_line.tax_amount, 3000.0, 2)
        self.assertEqual(service_line.payment_count, 1)

        corporate_line = report.line_ids.filtered(
            lambda l: l.partner_id == self.corporate,
        )
        # Corporate payees go to PND53 regardless of income type.
        self.assertEqual(corporate_line.pnd_type, 'pnd53')
        self.assertAlmostEqual(corporate_line.tax_amount, 10000.0, 2)

        self.assertAlmostEqual(report.total_base_amount, 300000.0, 2)
        self.assertAlmostEqual(report.total_tax_amount, 13000.0, 2)

    def test_report_respects_period(self):
        self._pay_bill(self.individual, self.wht_service, 100000.0)

        report = self.env['l10n_th.pnd.report'].create({
            'date_from': fields.Date.to_date('2099-01-01'),
            'date_to': fields.Date.to_date('2099-12-31'),
        })
        report.action_generate()
        self.assertFalse(report.line_ids)

    def test_manual_reclassification(self):
        self._pay_bill(self.individual, self.wht_service, 100000.0)

        report = self.env['l10n_th.pnd.report'].create({
            'date_from': fields.Date.today(),
            'date_to': fields.Date.today(),
        })
        report.action_generate()
        line = report.line_ids
        self.assertEqual(line.pnd_type, 'pnd2')
        line.pnd_type = 'pnd3'
        self.assertEqual(line.pnd_type, 'pnd3')
