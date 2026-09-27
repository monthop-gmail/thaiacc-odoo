# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Thai Localization - PIT",
    "version": "20.0.1.0.0",
    "category": "Localization / Accounting",
    "summary": "Progressive personal income tax withholding on the official "
               "account.tax.is_withholding_tax engine",
    "author": "ThaiACC, Odoo Community Association (OCA)",
    "website": "https://github.com/monthop-gmail/thaiacc-odoo",
    "license": "AGPL-3",
    "depends": ["l10n_th"],
    "data": [
        "security/ir.access.csv",
        "data/pit_rate_data.xml",
        "views/account_tax_views.xml",
        "views/l10n_th_pit_table_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["monthop-gmail"],
}
