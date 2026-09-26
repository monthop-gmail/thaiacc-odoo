{
    "name": "ThaiACC - Thai Accounting Complete Suite",
    "version": "20.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "All Thai accounting modules + optional extras in one click",
    "author": "Accsumana",
    "website": "https://sumana.online",
    "license": "LGPL-3",
    "depends": [
        # Core OCA Thai Accounting
        "ocaacc",
        # Expense Tax Invoice + WHT
        "l10n_th_account_tax_expense",
        # Company/Partner VAT/NOVAT setup
        "l10n_th_company_novat",
        # Sequence with Company Branch
        "l10n_th_sequence_branch",
        # PromptPay QR code on website
        "l10n_th_promptpay",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
}
