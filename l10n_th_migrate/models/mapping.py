# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
"""Deterministic 19.0 -> 20.0 mapping functions for Thai accounting evidence.

Every function takes a plain dict shaped like the legacy 19.0 record (the
fixture format, see tests/) and returns vals ready for the official Odoo 20
model. They are pure: no ORM writes happen here, so both the fresh-install
path (which never sees legacy data) and the migration path (which maps
legacy tables read-only) stay separate.
"""

INCOME_TYPE_BY_LEGACY_FORM = {
    # legacy account.withholding.tax.income_tax_form -> official
    # account.tax.l10n_th_income_tax_type (50 Tawi classification)
    "pnd1": "na",
    "pnd2": "service",
    "pnd3": "others",
    "pnd4": "na",
    "pnd53": "service",
}


def map_withholding_tax(legacy, company_id, tax_group_id=None):
    """Legacy ``account.withholding.tax`` vals -> official ``account.tax``
    vals (is_withholding_tax engine). Rate sign flips: the legacy engine
    stored positive percents; official withholding taxes carry negative
    amounts."""
    rate = float(legacy.get("amount", 0.0))
    form = legacy.get("income_tax_form") or "pnd3"
    is_pit = bool(legacy.get("is_pit"))
    return {
        "name": legacy["name"],
        "amount_type": "percent",
        # A nonzero placeholder lets the official engine create its payment
        # line. The PIT extension replaces it with the marginal amount.
        "amount": -abs(rate) if rate else (-1.0 if is_pit else 0.0),
        "type_tax_use": "purchase",
        "is_withholding_tax": True,
        "l10n_th_is_pit": is_pit,
        "l10n_th_income_tax_type": INCOME_TYPE_BY_LEGACY_FORM.get(form, "others"),
        "company_id": company_id,
        "tax_group_id": tax_group_id,
    }


def map_branch_identifier(company_registry):
    """Legacy ``res.partner.company_registry`` (Thai branch code) -> one
    entry of the official ``additional_identifiers`` JSON, using the core
    TH_BRANCH_CODE scheme."""
    value = (company_registry or "").strip()
    if not value:
        return {}
    return {"TH_BRANCH_CODE": value.zfill(5)}


def map_pit_table(legacy_table):
    """Legacy ``personal.income.tax`` + rate lines -> ``l10n_th.pit.table``
    vals (same bracket rows, same constraint of contiguity)."""
    return {
        "calendar_year": str(legacy_table["calendar_year"]),
        "rate_ids": [
            {
                "sequence": rate.get("sequence", i + 1),
                "income_from": float(rate["income_from"]),
                "income_to": float(rate["income_to"]),
                "tax_rate": float(rate["tax_rate"]),
            }
            for i, rate in enumerate(legacy_table.get("rate_ids", []))
        ],
    }


def map_tax_invoice(legacy_tax_invoice):
    """Legacy tax-invoice evidence (from the OCA 19.0 stack's
    tax_invoice_number/date records) -> official ``l10n_th.tax.invoice``
    vals for a vendor bill."""
    return {
        "tax_invoice_number": legacy_tax_invoice.get("tax_invoice_number"),
        "date": legacy_tax_invoice.get("tax_invoice_date")
        or legacy_tax_invoice.get("date"),
        "reference": legacy_tax_invoice.get("reference"),
    }
