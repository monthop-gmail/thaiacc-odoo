# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nTHWHTDefaults(AccountTestInvoicingCommon):
    """Product-level default withholding tax on vendor bills."""

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
            'tax_exigibility': 'on_invoice',
        })
        cls.vat = cls.env['account.tax'].create({
            'name': 'Purchase VAT 7%',
            'amount_type': 'percent',
            'amount': 7.0,
            'type_tax_use': 'purchase',
            'tax_exigibility': 'on_invoice',
        })
        # The default lives on the template: set it there directly (a
        # create() vals entry on product.product is dropped for template
        # fields, and the template record is what the view edits).
        cls.product_service = cls.env['product.product'].create({
            'name': 'Consulting (WHT 3%)',
        })
        cls.product_service.product_tmpl_id.l10n_th_supplier_wht_tax_id = cls.wht_service
        cls.product_plain = cls.env['product.product'].create({
            'name': 'Goods (no default WHT)',
        })

    def _create_bill(self, product):
        return self._create_invoice(
            move_type='in_invoice',
            invoice_date=fields.Date.today(),
            partner_id=self.partner_a.id,
            invoice_line_ids=[
                Command.create({
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': 1000.0,
                }),
            ],
        )

    def test_default_wht_appended_on_vendor_bill_line(self):
        bill = self._create_bill(self.product_service)
        line = bill.invoice_line_ids

        self.assertIn(self.wht_service, line.tax_ids)
        # The regular purchase VAT keeps coming from the product/company
        # default — the WHT is appended, not a replacement.
        self.assertNotEqual(line.tax_ids, self.wht_service)

    def test_no_default_wht_without_product_setting(self):
        bill = self._create_bill(self.product_plain)
        self.assertNotIn(self.wht_service, bill.invoice_line_ids.tax_ids)

    def test_default_wht_not_duplicated(self):
        bill = self._create_bill(self.product_plain)
        line = bill.invoice_line_ids
        line.tax_ids = [Command.set((line.tax_ids | self.wht_service).ids)]
        # Switching product re-triggers the tax computation; the manually
        # added WHT must not be added twice.
        line.product_id = self.product_service
        self.assertEqual(
            len(line.tax_ids.filtered(lambda t: t == self.wht_service)), 1,
        )

    def test_default_wht_not_applied_on_customer_invoice(self):
        invoice = self._create_invoice(
            move_type='out_invoice',
            invoice_date=fields.Date.today(),
            partner_id=self.partner_a.id,
            invoice_line_ids=[
                Command.create({
                    'product_id': self.product_service.id,
                    'quantity': 1,
                    'price_unit': 1000.0,
                }),
            ],
        )
        self.assertNotIn(
            self.wht_service, invoice.invoice_line_ids.tax_ids,
        )
