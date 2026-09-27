# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nTHPIT(AccountTestInvoicingCommon):
    """Progressive PIT withholding on the official WHT engine."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('th')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_th_is_vat_registered = True

        cls.pit_table = cls.env['l10n_th.pit.table'].create({
            'calendar_year': '2099',
            'rate_ids': [
                Command.create({'sequence': 1, 'income_from': 0.0, 'income_to': 150000.0, 'tax_rate': 0.0}),
                Command.create({'sequence': 2, 'income_from': 150000.0, 'income_to': 300000.0, 'tax_rate': 5.0}),
                Command.create({'sequence': 3, 'income_from': 300000.0, 'income_to': 500000.0, 'tax_rate': 10.0}),
            ],
        })

        cls.pit_tax = cls.env['account.tax'].create({
            'name': 'WHT PIT (progressive)',
            'amount_type': 'percent',
            'amount': -3.0,  # placeholder percent; PIT computation overrides it
            'type_tax_use': 'purchase',
            'is_withholding_tax': True,
            'l10n_th_is_pit': True,
        })
        cls.flat_tax = cls.env['account.tax'].create({
            'name': 'WHT 3% flat',
            'amount_type': 'percent',
            'amount': -3.0,
            'type_tax_use': 'purchase',
            'is_withholding_tax': True,
        })
        cls.individual = cls.env['res.partner'].create({'name': 'PIT Contractor'})
        cls.company = cls.env.company

    def _create_bill(self, partner, price_unit, tax):
        return self._create_invoice(
            move_type='in_invoice',
            invoice_date=fields.Date.to_date('2099-03-01'),
            partner_id=partner.id,
            invoice_line_ids=[
                Command.create({'quantity': 1, 'price_unit': price_unit, 'tax_ids': [Command.set(tax.ids)]}),
            ],
        )

    def _register_payment(self, move):
        return self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({})._create_payments()

    def _wht_lines(self, payment):
        return payment.withholding_line_ids

    def test_marginal_wht_math(self):
        """150k accumulated + 100k increment: the whole increment sits in the
        5% bracket = 5,000."""
        self.assertEqual(
            self.pit_table._marginal_wht(150000.0, 100000.0, self.company.currency_id),
            5000.0,
        )
        # 250k accumulated + 100k increment crosses the 300k line:
        # 50k at 5% + 50k at 10% = 7,500.
        self.assertEqual(
            self.pit_table._marginal_wht(250000.0, 100000.0, self.company.currency_id),
            7500.0,
        )
        # First ever payment inside the 0% bracket withholds nothing.
        self.assertEqual(
            self.pit_table._marginal_wht(0.0, 100000.0, self.company.currency_id),
            0.0,
        )

    def test_pit_withholding_first_payment(self):
        """First payment of 200k to a fresh payee: 50k at 5% = 2,500 withheld
        (progressive), not the flat 3% (6,000)."""
        bill = self._create_bill(self.individual, 200000.0, self.pit_tax)
        bill.action_post()
        payment = self._register_payment(bill)

        lines = self._wht_lines(payment)
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines.amount, 2500.0, 2)

    def test_pit_withholding_accumulates_yearly(self):
        """Second payment in the same year: marginal on top of the first
        payment's base, read back from the official withholding lines."""
        bill1 = self._create_bill(self.individual, 200000.0, self.pit_tax)
        bill1.action_post()
        self._register_payment(bill1)

        bill2 = self._create_bill(self.individual, 100000.0, self.pit_tax)
        bill2.invoice_date = fields.Date.to_date('2099-06-01')
        bill2.action_post()
        payment2 = self._register_payment(bill2)

        lines = self._wht_lines(payment2)
        self.assertEqual(len(lines), 1)
        # 200k accumulated + 100k increment = 300k total; the increment
        # 200k->300k sits entirely in the 5% bracket -> 5,000.
        self.assertAlmostEqual(lines.amount, 5000.0, 2)

    def test_flat_wht_unchanged(self):
        """Non-PIT withholding keeps the flat engine behavior."""
        bill = self._create_bill(self.individual, 200000.0, self.flat_tax)
        bill.action_post()
        payment = self._register_payment(bill)

        lines = self._wht_lines(payment)
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines.amount, 6000.0, 2)
