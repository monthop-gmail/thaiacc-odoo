# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Thai Localization - WHT Defaults",
    "version": "20.0.1.0.0",
    "category": "Localization / Accounting",
    "summary": "Product-level default withholding tax for vendor bills on "
               "the official account.tax.is_withholding_tax engine",
    "author": "ThaiACC, Odoo Community Association (OCA)",
    "website": "https://github.com/monthop-gmail/thaiacc-odoo",
    "license": "AGPL-3",
    "depends": ["l10n_th"],
    "data": [
        "views/product_template_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["monthop-gmail"],
}
