# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Thai Localization - Purchase Tax Invoice",
    "version": "20.0.1.0.0",
    "category": "Localization / Accounting",
    "summary": "Vendor tax invoice evidence and purchase-side payment tax "
               "invoices on the official l10n_th.tax.invoice model",
    "author": "ThaiACC, Odoo Community Association (OCA)",
    "website": "https://github.com/monthop-gmail/thaiacc-odoo",
    "license": "AGPL-3",
    "depends": ["l10n_th"],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["monthop-gmail"],
}
