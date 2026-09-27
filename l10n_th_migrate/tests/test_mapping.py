# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
"""Deterministic-mapping tests against recorded legacy-shaped fixtures.

The fixtures below are plain dicts shaped like the 19.0 records of the
legacy Thai stack (account.withholding.tax, personal.income.tax, tax
invoice evidence, company_registry). No legacy models are instantiated —
the migration contract maps dicts to official-model vals, so the
fresh-install path can never be affected.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_th_migrate.models.mapping import (
    map_branch_identifier,
    map_pit_table,
    map_tax_invoice,
    map_withholding_tax,
)


# --- fixtures: recorded shapes of the legacy 19.0 stack ----------------------

LEGACY_WHT_SERVICE = {
    "name": "WHT 3% ค่าบริการ/จ้างทำของ",
    "amount": 3.0,
    "account": "ACC/WHT",
    "income_tax_form": "pnd2",
}

LEGACY_WHT_RENT = {
    "name": "WHT 5% ค่าเช่า",
    "amount": 5.0,
    "income_tax_form": "pnd3",
}

LEGACY_PIT_TABLE = {
    "calendar_year": 2569,
    "rate_ids": [
        {"sequence": 1, "income_from": 0.0, "income_to": 150000.0, "tax_rate": 0.0},
        {"sequence": 2, "income_from": 150000.0, "income_to": 300000.0, "tax_rate": 5.0},
    ],
}

LEGACY_TAX_INVOICE = {
    "tax_invoice_number": "V-TI-2569-0001",
    "tax_invoice_date": "2026-08-01",
    "reference": "BILL/2026/08/0001",
}


@tagged("post_install", "-at_install")
class TestMappingContract(TransactionCase):
    """The 19→20 mapping contract is deterministic."""

    def test_withholding_tax_mapping(self):
        company = self.env.company
        vals = map_withholding_tax(LEGACY_WHT_SERVICE, company.id)

        self.assertEqual(vals["name"], "WHT 3% ค่าบริการ/จ้างทำของ")
        self.assertEqual(vals["amount"], -3.0)  # sign flips to official
        self.assertTrue(vals["is_withholding_tax"])
        self.assertEqual(vals["type_tax_use"], "purchase")
        # legacy pnd2 (hire of work) -> official 50 (2) service type
        self.assertEqual(vals["l10n_th_income_tax_type"], "service")
        self.assertEqual(vals["company_id"], company.id)

        # same legacy row always maps to the same vals (determinism)
        self.assertEqual(vals, map_withholding_tax(LEGACY_WHT_SERVICE, company.id))

    def test_withholding_tax_income_type_fallback(self):
        vals = map_withholding_tax(LEGACY_WHT_RENT, self.env.company.id)
        self.assertEqual(vals["amount"], -5.0)
        self.assertEqual(vals["l10n_th_income_tax_type"], "others")

    def test_pit_table_mapping(self):
        vals = map_pit_table(LEGACY_PIT_TABLE)
        # legacy stored a BE year string -> 20.0 table keys on the string
        self.assertEqual(vals["calendar_year"], "2569")
        self.assertEqual(len(vals["rate_ids"]), 2)
        self.assertEqual(vals["rate_ids"][1]["tax_rate"], 5.0)

        # the mapped brackets satisfy the 20.0 table constraint (contiguous)
        table = self.env["l10n_th.pit.table"].create({
            **vals,
            "rate_ids": [Command.create(r) for r in vals["rate_ids"]],
        })
        self.assertEqual(len(table.rate_ids), 2)

    def test_tax_invoice_mapping(self):
        vals = map_tax_invoice(LEGACY_TAX_INVOICE)
        self.assertEqual(vals["tax_invoice_number"], "V-TI-2569-0001")
        self.assertEqual(vals["date"], "2026-08-01")
        self.assertEqual(vals["reference"], "BILL/2026/08/0001")

    def test_branch_identifier_mapping(self):
        # 5-digit codes pass through; short codes zero-pad; empty -> none
        self.assertEqual(
            map_branch_identifier("00007"), {"TH_BRANCH_CODE": "00007"},
        )
        self.assertEqual(map_branch_identifier("314")["TH_BRANCH_CODE"], "00314")
        self.assertEqual(map_branch_identifier(""), {})
        self.assertEqual(map_branch_identifier(None), {})
