#!/bin/bash
# E20-002: official-capability smoke tests for the Odoo 20 official-only baseline.
#
# Run from inside the odoo container of the compose stack:
#   docker compose exec odoo bash /workspace/test/official_smoke_test.sh
#
# What it does:
#   1. Creates a scratch database and installs the official l10n_th chart.
#   2. Runs the official l10n_th test suite (tax invoices on payments, WTH
#      payments, EMV/PromptPay QR, 50 Tawi PDF, partner VAT checks).
#   3. Asserts the headline capabilities a fresh install must provide.
# Exit code is non-zero if any official test or capability check fails.
set -uo pipefail

DB="thaiacc_smoke"
PGARGS=(-h db -U odoo)

echo "=== ThaiACC official smoke tests (Odoo $(odoo --version 2>/dev/null | awk '{print $3}')) ==="

export PGPASSWORD=odoo
dropdb "${PGARGS[@]}" --if-exists "$DB"
createdb "${PGARGS[@]}" "$DB"

run_odoo() {
    odoo -d "$DB" --db_host=db --db_user=odoo --db_password=odoo \
        --http-interface=127.0.0.1 --max-cron-threads=0 --stop-after-init "$@"
}

# Odoo 20 validates -i names against ir_module_module, which a virgin db
# only fills after the first boot — so install base first, then l10n_th.
echo "--- boot 1: init base ---"
run_odoo -i base

echo "--- boot 2: install l10n_th + run official tests ---"
run_odoo -i l10n_th --without-demo=False --test-enable --test-tags /l10n_th
OFFICIAL_TESTS=$?

echo "--- capability checks ---"
SHELL_PROBE='
checks = []

def check(label, cond):
    checks.append((label, bool(cond)))
    print(("PASS " if cond else "FAIL ") + label)

# A fresh db has no chart applied to the company yet — load it the way a
# real deployment does, then check what the official chart provides.
company = env["res.company"].search([], limit=1)
if not company:
    company = env["res.company"].create({"name": "Smoke TH", "country_id": env.ref("base.th").id})
env["account.chart.template"].try_loading("th", company)
check("chart template th loaded onto company", bool(company.account_fiscal_country_id))

vat = env["account.tax"].search([("amount", "=", 7)])
check("VAT 7% taxes present", len(vat) >= 2)

wht = env["account.tax"].search([("is_withholding_tax", "=", True)])
check("withholding taxes present (account.tax.is_withholding_tax)", len(wht) >= 5)

try:
    env.ref("l10n_th.report_50_tawi")
    check("50 Tawi report exists (l10n_th.report_50_tawi)", True)
except ValueError:
    check("50 Tawi report exists (l10n_th.report_50_tawi)", False)

names = env["res.partner.bank"]._get_emv_qr_code_names()
check("PromptPay EMV QR registered for TH", "TH" in names)

cur = env["res.currency"].search([("name", "=", "THB")], limit=1)
try:
    text = cur.amount_to_text(1234.56)
    check("amount_to_text works for THB (got %r)" % text[:40], bool(text))
except Exception as e:
    check("amount_to_text works for THB (%s)" % e, False)

check("official sales tax invoice model present", bool(env["ir.model"].search([("model", "=", "l10n_th.tax.invoice")], limit=1)))
check("l10n_th_tax_invoice_ids field on account.move", bool(env["ir.model.fields"].search([("model", "=", "account.move"), ("name", "=", "l10n_th_tax_invoice_ids")], limit=1)))
try:
    env.ref("l10n_th.report_tax_invoice")
    check("tax invoice report exists (l10n_th.report_tax_invoice)", True)
except ValueError:
    check("tax invoice report exists (l10n_th.report_tax_invoice)", False)

failed = [label for label, ok in checks if not ok]
print("SMOKE RESULT: %d/%d passed" % (len(checks) - len(failed), len(checks)))
if failed:
    print("SMOKE FAILED: " + "; ".join(failed))
    raise SystemExit(1)
'

set +e
echo "$SHELL_PROBE" | odoo shell -d "$DB" --db_host=db --db_user=odoo --db_password=odoo --max-cron-threads=0 --no-http 2>/dev/null | grep -E "^(PASS|FAIL|SMOKE)"
CAP_TESTS=$?
set -e

echo "=== summary ==="
echo "official odoo tests exit: $OFFICIAL_TESTS"
echo "capability checks exit: $CAP_TESTS"
if [ "$OFFICIAL_TESTS" = "0" ] && [ "$CAP_TESTS" = "0" ]; then
    echo "SMOKE: ALL PASSED"
    exit 0
fi
echo "SMOKE: FAILED"
exit 1
