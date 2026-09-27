# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    "name": "Thai Localization - PND Report",
    "version": "20.0.1.0.0",
    "category": "Localization / Accounting",
    "summary": "Normalized PND1/1A/2/3/53 withholding tax return adapter on "
               "official payment withholding data",
    "author": "ThaiACC, Odoo Community Association (OCA)",
    "website": "https://github.com/monthop-gmail/thaiacc-odoo",
    "license": "AGPL-3",
    "depends": ["l10n_th"],
    "data": [
        "security/ir.access.csv",
        "views/l10n_th_pnd_report_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "development_status": "Beta",
    "maintainers": ["monthop-gmail"],
}
