# Copyright 2025 Accsumana
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestThaiaccDemoData(TransactionCase):
    """Test that thaiacc demo data is loaded correctly on Odoo 20."""

    def test_demo_vendor_exists(self):
        """The shop vendor demo partner should exist."""
        vendor = self.env.ref("thaiacc.demo_vendor_novat")
        self.assertEqual(vendor.vat, "0993560456789")
        self.assertTrue(vendor.supplier_rank > 0)

    def test_demo_products_have_default_wht(self):
        """Products carry the ThaiACC default WHT (official engine)."""
        product = self.env.ref("thaiacc.demo_product_consulting")
        wht = self.env.ref("ocaacc.demo_wht_3_service")
        self.assertEqual(product.l10n_th_supplier_wht_tax_id, wht)

        rent = self.env.ref("thaiacc.demo_product_rent")
        self.assertEqual(
            rent.l10n_th_supplier_wht_tax_id,
            self.env.ref("ocaacc.demo_wht_5_rent"),
        )

    def test_demo_pit_tax_flagged(self):
        """The suite ships a progressive PIT tax (l10n_th_pit)."""
        tax = self.env.ref("thaiacc.demo_wht_pit_progressive")
        self.assertTrue(tax.is_withholding_tax)
        self.assertTrue(tax.l10n_th_is_pit)
