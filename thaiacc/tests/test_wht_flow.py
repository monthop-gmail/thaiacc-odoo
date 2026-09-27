# Copyright 2025 Accsumana
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestThaiaccWhtFlow(TransactionCase):
    """Suite-level flow: a demo product's default WHT lands on the vendor
    bill line and reaches the official payment withholding lines."""

    def test_demo_product_default_wht_reaches_payment(self):
        self.env.company.country_id = self.env.ref("base.th")
        self.env.company.account_fiscal_country_id = self.env.ref("base.th")
        product = self.env.ref("thaiacc.demo_product_consulting").product_variant_id
        product.product_tmpl_id.supplier_taxes_id = False
        vendor = self.env.ref("ocaacc.demo_vendor_somchai")

        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": vendor.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": product.id,
                    "quantity": 10,
                    "price_unit": 10000.0,
                }),
            ],
        })
        line = bill.invoice_line_ids
        self.assertIn(
            self.env.ref("ocaacc.demo_wht_3_service"),
            line.tax_ids,
            "Product default WHT should be suggested on the bill line",
        )

        bill.action_post()
        payment = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=bill.ids,
        ).create({})._create_payments()

        wht_lines = payment.withholding_line_ids
        self.assertEqual(len(wht_lines), 1)
        self.assertAlmostEqual(wht_lines.amount, 3000.0, 2)
