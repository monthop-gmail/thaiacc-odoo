# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nTHPurchaseTaxInvoice(AccountTestInvoicingCommon):
    """Purchase-side Thai tax invoices: vendor document evidence on bills and
    payment-time tax invoices from cash-basis entries."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('th')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_th_is_vat_registered = True

        cls.vat_on_invoice = cls.env['account.tax'].create({
            'name': 'Purchase VAT On Invoice',
            'amount_type': 'percent',
            'amount': 7.0,
            'type_tax_use': 'purchase',
            'tax_exigibility': 'on_invoice',
        })
        cls.vat_on_payment = cls.env['account.tax'].create({
            'name': 'Purchase VAT On Payment',
            'amount_type': 'percent',
            'amount': 7.0,
            'type_tax_use': 'purchase',
            'tax_exigibility': 'on_payment',
        })

        cls.bill = cls._create_invoice(
            move_type='in_invoice',
            invoice_date='2026-08-01',
            partner_id=cls.partner_a.id,
            invoice_line_ids=[],
        )
        cls.bill.l10n_th_vendor_tax_invoice_number = 'V-TI-2569-0001'
        cls.bill.l10n_th_vendor_tax_invoice_date = fields.Date.to_date('2026-08-01')

    def test_vendor_tax_invoice_created_for_on_invoice_tax(self):
        """Posting a vendor bill with on-invoice VAT records the vendor's
        document details on a tax invoice."""
        # The vendor's number is recorded verbatim — no internal sequence runs.
        sequence_code = 'l10n_th.tax.invoice.tax_invoice_number'
        sequences = self.env['ir.sequence'].search([('code', '=', sequence_code)])
        before = {s.id: s.number_next_actual for s in sequences}

        self.bill.invoice_line_ids = [
            self._prepare_invoice_line(
                price_unit=1000,
                tax_ids=self.vat_on_invoice,
            ),
        ]
        self.bill.action_post()
        after = {s.id: s.number_next_actual for s in sequences}
        self.assertEqual(before, after)

        tax_invoices = self.bill.l10n_th_tax_invoice_ids
        self.assertEqual(len(tax_invoices), 1)
        tax_invoice = tax_invoices

        self.assertRecordValues(tax_invoice, [{
            'tax_invoice_number': 'V-TI-2569-0001',
            'date': fields.Date.to_date('2026-08-01'),
            'reference': False,
            'total_amount': 1070.0,
            'vat_amount': 70.0,
            'payment_move_id': False,
            'state': 'posted',
        }])

        # Drafting the bill re-opens the vendor tax invoice.
        self.bill.button_draft()
        self.assertEqual(tax_invoice.state, 'draft')
        self.bill.action_post()
        self.assertEqual(tax_invoice.state, 'posted')

        # Cancelling cancels it.
        self.bill.button_cancel()
        self.assertEqual(tax_invoice.state, 'cancel')

    def test_vendor_tax_invoice_without_document_number_stays_empty(self):
        """A missing vendor document number must not be auto-generated."""
        self.bill.l10n_th_vendor_tax_invoice_number = False
        self.bill.invoice_line_ids = [
            self._prepare_invoice_line(
                price_unit=500,
                tax_ids=self.vat_on_invoice,
            ),
        ]
        self.bill.action_post()

        tax_invoice = self.bill.l10n_th_tax_invoice_ids
        self.assertEqual(len(tax_invoice), 1)
        self.assertFalse(tax_invoice.tax_invoice_number)

    def test_no_vendor_tax_invoice_without_vat(self):
        """Bills without any VAT keep no tax invoice evidence."""
        self.bill.invoice_line_ids = [
            self._prepare_invoice_line(price_unit=1000, tax_ids=False),
        ]
        self.bill.action_post()
        self.assertFalse(self.bill.l10n_th_tax_invoice_ids)

    def test_payment_tax_invoice_created_for_on_payment_tax(self):
        """Paying a cash-basis vendor bill creates the input-VAT tax invoice
        at payment time (the purchase mirror of the official sales flow)."""
        self.bill.invoice_line_ids = [
            self._prepare_invoice_line(
                price_unit=2000,
                tax_ids=self.vat_on_payment,
            ),
        ]
        self.bill.action_post()
        self.assertFalse(self.bill.l10n_th_tax_invoice_ids)

        self._register_payment(self.bill)
        self.assertEqual(len(self.bill.l10n_th_tax_invoice_ids), 1)
        tax_invoice = self.bill.l10n_th_tax_invoice_ids

        self.assertRecordValues(tax_invoice, [{
            'reference': self.bill.tax_cash_basis_created_move_ids.name,
            'state': 'posted',
            'total_amount': 2140.0,
            'vat_amount': 140.0,
        }])
        # payment_move_id points at the cash-basis entry, which originates
        # from this vendor bill.
        self.assertEqual(
            tax_invoice.payment_move_id.tax_cash_basis_origin_move_id,
            self.bill,
        )

    def test_partial_payment_tax_invoices(self):
        """Two partial payments create two payment tax invoices with the
        right paid ratio."""
        self.bill.invoice_line_ids = [
            self._prepare_invoice_line(
                price_unit=2000,
                tax_ids=self.vat_on_payment,
            ),
        ]
        self.bill.action_post()

        self._register_payment(self.bill, amount=1070.0)
        first_caba = self.bill.tax_cash_basis_created_move_ids

        self._register_payment(self.bill, amount=1070.0)
        second_caba = self.bill.tax_cash_basis_created_move_ids.filtered(
            lambda caba: caba.id != first_caba.id,
        )

        tax_invoices = self.bill.l10n_th_tax_invoice_ids.filtered(
            lambda ti: ti.payment_move_id,
        )
        self.assertEqual(len(tax_invoices), 2)
        self.assertAlmostEqual(sum(tax_invoices.mapped('total_amount')), 2140.0, 2)
        self.assertAlmostEqual(sum(tax_invoices.mapped('vat_amount')), 140.0, 2)


# --- Superseded official expectation -----------------------------------------
# Official l10n_th asserts that NO tax invoice is created for vendor bill
# payments. E20-003 deliberately changes exactly that: purchase-side payment
# tax invoices are the whole point of this module. Replace the official test
# method with the new expectation, on the official class, so the official
# suite documents the new behavior instead of failing against it.

from odoo.addons.l10n_th.tests import test_l10n_th_tax_invoice as _official  # noqa: E402


def _test_vendor_bill_payment_creates_tax_invoice(self):
    """Vendor bill payments create the input-VAT tax invoice (E20-003)."""

    self.tax_on_payment.type_tax_use = 'purchase'

    self.invoice.move_type = 'in_invoice'
    self.invoice.invoice_line_ids = [
        self._prepare_invoice_line(
            price_unit=1000,
            tax_ids=self.tax_on_payment,
        ),
    ]
    self.invoice.action_post()

    self._register_payment(
        self.invoice,
        amount=1070.0,
    )

    self.assertEqual(
        len(self.invoice.tax_cash_basis_created_move_ids),
        1,
        "A cash basis journal entry should be created after the payment is reconciled.",
    )

    tax_invoices = self.invoice.l10n_th_tax_invoice_ids
    self.assertEqual(len(tax_invoices), 1)
    self.assertEqual(tax_invoices.vat_amount, 70.0)
    self.assertEqual(tax_invoices.total_amount, 1070.0)
    self.assertEqual(tax_invoices.state, 'posted')


_official.TestL10nTHTaxInvoice.test_no_tax_invoice_created_for_vendor_bill_payment = (
    _test_vendor_bill_payment_creates_tax_invoice
)
