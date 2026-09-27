# Copyright 2025 Accsumana
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

{
    "name": "ThaiACC - Thai Accounting Complete Suite",
    "version": "20.0.1.0.0",
    "category": "Localization / Accounting",
    "summary": "One-click Thai accounting on Odoo 20: official stack + "
               "ThaiACC gap modules (purchase tax invoice, WHT defaults, "
               "PIT, PND report)",
    "author": "Accsumana, Odoo Community Association (OCA)",
    "website": "https://github.com/monthop-gmail/thaiacc-odoo",
    "license": "LGPL-3",
    "description": """
Official-first Thai accounting suite for Odoo 20.

Included: the official Thai localization (via ocaacc) plus the ThaiACC
modules that cover the proven Thai gaps — purchase/vendor tax invoices,
product-level WHT defaults, progressive PIT, and the normalized PND
report — together with the Thai sequence legends and PromptPay QR on the
custom payment provider.

Not included (still blocked on OCA 20.0 branches — see MIGRATION-20.0.md
bridge inventory): l10n_th_company_novat, l10n_th_sequence_branch,
l10n_th_account_tax_expense.
""",
    "depends": [
        "ocaacc",
        "hr_expense",
        "l10n_th_base_sequence",
        "l10n_th_promptpay",
        "l10n_th_purchase_tax_invoice",
        "l10n_th_wht_defaults",
        "l10n_th_pit",
        "l10n_th_pnd_report",
    ],
    "demo": ["demo/demo_data.xml"],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["monthop-gmail"],
}
