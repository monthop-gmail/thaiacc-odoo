# Copyright 2025 Accsumana
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestOcaaccDemoData(TransactionCase):
    """Test that ocaacc demo data is loaded correctly on Odoo 20."""

    def test_demo_vendors_exist(self):
        """Thai vendor partners should exist with correct tax IDs."""
        vendor1 = self.env.ref("ocaacc.demo_vendor_somchai")
        self.assertEqual(vendor1.vat, "0105560123456")
        self.assertTrue(vendor1.supplier_rank > 0)
        # Odoo 20.0 semantics: is_company = own commercial entity AND has_vat.
        self.assertTrue(vendor1.is_company)

        vendor2 = self.env.ref("ocaacc.demo_vendor_rungrueang")
        self.assertEqual(vendor2.vat, "0103560789012")
        self.assertTrue(vendor2.is_company)

        # A person with a VAT number computes as a company under the 20.0
        # heuristic (own commercial entity + valid VAT) — the pre-20.0
        # expectation `is_company == False` no longer holds.
        vendor3 = self.env.ref("ocaacc.demo_vendor_wichai")
        self.assertEqual(vendor3.vat, "1234567890123")
        self.assertTrue(vendor3.is_company)

    def test_demo_customer_exists(self):
        """Thai customer partner should exist."""
        customer = self.env.ref("ocaacc.demo_customer_thai")
        self.assertEqual(customer.vat, "0107550345678")
        self.assertTrue(customer.customer_rank > 0)

    def test_withholding_taxes_are_official_account_taxes(self):
        """Demo WHT records are official account.tax with withholding."""
        for xmlid, amount, income_type in [
            ("ocaacc.demo_wht_1_transport", -1.0, "transportation"),
            ("ocaacc.demo_wht_2_advertising", -2.0, "advertising"),
            ("ocaacc.demo_wht_3_service", -3.0, "service"),
            ("ocaacc.demo_wht_5_rent", -5.0, "rentals"),
        ]:
            tax = self.env.ref(xmlid)
            self.assertTrue(tax.is_withholding_tax)
            self.assertEqual(tax.amount, amount)
            self.assertEqual(tax.type_tax_use, "purchase")
            self.assertEqual(tax.l10n_th_income_tax_type, income_type)

    def test_withholding_base_account_set_on_company(self):
        company = self.env.ref("base.main_company")
        self.assertTrue(company.withholding_tax_base_account_id)
