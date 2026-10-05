"""Seed a native Odoo 19 ThaiACC rehearsal cohort. Run via ``odoo shell`` stdin.

Recreates the 2026-09-28 seeded clone cohort (MIGRATION-RUNBOOK.md) so the
CABA decision-gate queries in CABA-VAT-DECISION-GATE.md can run against a
live source. Idempotent: every step asserts the expected pre-state and is
skipped when its document already exists.

Cohort (all 2026-09, company "ThaiACC 19 Rehearsal"):
- MIG-BILL-001: vendor bill 100,000, WHT 3% on the line, paid net 97,000,
  50 Tawi certificate issued.
- MIG-BILL-002: vendor bill 100,000 + on-invoice input VAT 7,000, tax
  invoice VAT-MIG-19-001, unpaid.
- MIG-INV-001: customer invoice 100,000 + output VAT 7,000, unpaid.
- MIG-INV-002: customer invoice, posted then cancelled.
- MIG-BILL-CABA: vendor bill 100,000 + on-payment input VAT 7,000, paid
  42,800 (40%) then 64,200 (60%), CABA tax invoices CABA-MIG-19-40 and
  CABA-MIG-19-60.

Never run this against a production database; it is for isolated clones.
"""

from odoo import Command

COMPANY_NAME = "ThaiACC 19 Rehearsal"


def log(msg):
    print("SEED: " + msg, flush=True)


# On Odoo 19.0 core the payment-register writeoff line loses partner_id
# (skip_account_move_synchronization path), so account.withholding.move
# create fails its not-null constraint. Fill the partner from the entry's
# partner when the writeoff line carries none. Accounting amounts untouched.
_orig_prepare_wht = type(env["account.move"])._prepare_withholding_move


def _prepare_wht_patched(self, wht_ml, pit_no_wht=False):
    vals = _orig_prepare_wht(self, wht_ml, pit_no_wht)
    if not vals.get("partner_id"):
        vals["partner_id"] = (
            wht_ml.move_id.partner_id or self.partner_id).id
    return vals


type(env["account.move"])._prepare_withholding_move = _prepare_wht_patched


company = env["res.company"].search([("name", "=", COMPANY_NAME)])
assert len(company) <= 1, "Ambiguous rehearsal company"
if not company:
    company = env["res.company"].create({
        "name": COMPANY_NAME, "country_id": env.ref("base.th").id,
        "currency_id": env.ref("base.THB").id,
    })
    env["account.chart.template"].try_loading("th", company)
    env.cr.commit()
log(f"company id={company.id}")

Partner = env["res.partner"].with_company(company)
Account = env["account.account"].with_company(company)
Tax = env["account.tax"].with_company(company)
Move = env["account.move"].with_company(company)
Wizard = env["account.payment.register"].with_company(company)


def get_partner(name, vat, is_company):
    found = Partner.search([("name", "=", name)])
    assert len(found) <= 1, f"Ambiguous partner {name}"
    if found:
        return found
    return Partner.with_context(no_vat_validation=True).create({
        "name": name, "vat": vat, "is_company": is_company,
        "country_id": env.ref("base.th").id,
    })


vendor = get_partner("Rehearsal Vendor Co., Ltd.", "1999999999991", True)
customer = get_partner("Rehearsal Customer Co., Ltd.", "1999999999992", True)
if not env["res.partner.bank"].with_company(company).search([
        ("partner_id", "=", vendor.id)]):
    bank = env["res.bank"].search([("bic", "=", "RHBKTHBK")]) or \
        env["res.bank"].create({"name": "Rehearsal Bank", "bic": "RHBKTHBK"})
    vals = {"acc_number": "0993000123456", "partner_id": vendor.id,
            "bank_id": bank.id}
    if "proxy_value" in env["res.partner.bank"]._fields:
        vals["proxy_value"] = "0819999999"
    env["res.partner.bank"].create(vals)
    log("vendor bank/proxy created")

# --- WHT account + withholding tax (name is propagated to target by runner)
wht_account = Account.search([("code", "=", "MIGWHT19")])
assert len(wht_account) <= 1, "Ambiguous MIGWHT19 account"
if not wht_account:
    wht_account = Account.create({
        "name": "Withholding Tax Payable (Migration)",
        "code": "MIGWHT19", "account_type": "liability_current",
        "wht_account": True,
    })
wht_tax = env["account.withholding.tax"].with_company(company).search([
    ("name", "=", "WHT 3%"), ("company_id", "=", company.id)])
assert len(wht_tax) <= 1, "Ambiguous WHT 3% withholding tax"
if not wht_tax:
    wht_tax = env["account.withholding.tax"].with_company(company).create({
        "name": "WHT 3%", "account_id": wht_account.id, "amount": 3.0,
        "income_tax_form": "pnd53", "wht_cert_income_type": "2",
    })
log(f"WHT tax id={wht_tax.id} account={wht_account.code}")

# --- CABA tax: copy of the chart's 7% purchase tax with a transition account
transition = Account.search([("code", "=", "114299")])
assert len(transition) <= 1, "Ambiguous 114299 transition account"
if not transition:
    transition = Account.create({
        "name": "Input VAT (CABA transition)", "code": "114299",
        "account_type": "asset_current", "reconcile": True,
    })
base_tax = Tax.search([
    ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
    ("amount", "=", 7.0), ("tax_exigibility", "=", "on_invoice")])
assert len(base_tax) == 1, f"Expected one 7% purchase tax, got {len(base_tax)}"
caba_tax = Tax.search([("company_id", "=", company.id),
                       ("tax_exigibility", "=", "on_payment"),
                       ("type_tax_use", "=", "purchase")])
assert len(caba_tax) <= 1, "Ambiguous CABA tax"
if not caba_tax:
    caba_tax = base_tax.copy({
        "name": "VAT7-ONPAYMENT", "tax_exigibility": "on_payment",
        "cash_basis_transition_account_id": transition.id,
    })
log(f"CABA tax id={caba_tax.id} transition={transition.code}")

input_vat = base_tax
output_vat = Tax.search([("company_id", "=", company.id),
                         ("type_tax_use", "=", "sale"),
                         ("amount", "=", 7.0),
                         ("tax_exigibility", "=", "on_invoice")])
assert len(output_vat) == 1, "Expected one 7% sale tax"
expense = Account.search([("code", "=", "611100")])
assert len(expense) == 1, "Chart must provide 611100"


def fill_tax_invoice_numbers(move, number):
    pending = move.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    pending.write({"tax_invoice_number": number,
                   "tax_invoice_date": move.invoice_date or move.date})
    log(f"TI {number} written on {len(pending)} row(s) of {move.ref}")


def post_bill(ref, move_type, partner, line_vals, ti_number=None):
    move = Move.search([("ref", "=", ref), ("move_type", "=", move_type),
                        ("company_id", "=", company.id)])
    assert len(move) <= 1, f"Ambiguous document {ref}"
    if move:
        log(f"{ref} already exists ({move.state})")
        return move
    move = Move.create({
        "move_type": move_type, "partner_id": partner.id, "ref": ref,
        "invoice_date": "2026-09-01", "date": "2026-09-01",
        "invoice_line_ids": [Command.create(vals) for vals in line_vals],
    })
    try:
        move.action_post()
    except Exception as exc:  # legacy asks for vendor TI info at post time
        log(f"post {ref} deferred ({exc}); filling TI {ti_number}")
        fill_tax_invoice_numbers(move, ti_number or "TI-" + ref)
        move.action_post()
    assert move.state == "posted", (ref, move.state)
    if ti_number and move.tax_invoice_ids:
        fill_tax_invoice_numbers(move, ti_number)
    log(f"{ref} posted, total={move.amount_total}")
    return move


def pay(move, amount, wht_tax=None, wht_base=None, label="",
        payment_date="2026-09-10"):
    wizard = Wizard.with_context(
        active_model="account.move", active_ids=[move.id]).create(
        {"payment_date": payment_date})
    if wht_tax:
        wizard.wht_tax_id = wht_tax
        wizard.wht_amount_base = wht_base
        wizard._onchange_wht()
        wizard.payment_difference_handling = "reconcile"
    else:
        wizard.amount = amount
    log(f"wizard: partner={wizard.partner_id.name} diff_handling="
        f"{wizard.payment_difference_handling} amount={wizard.amount}")
    assert abs(wizard.amount - amount) < 0.01, \
        (label, wizard.amount, amount)
    payments = wizard._create_payments()
    assert len(payments) == 1, (label, payments)
    payment = payments[0]
    log(f"{label}: payment {payment.amount}, to_clear_tax="
        f"{getattr(payment, 'to_clear_tax', False)}")
    return payment


bill_a = post_bill("MIG-BILL-001", "in_invoice", vendor, [{
    "name": "WHT bill service", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
    "wht_tax_id": wht_tax.id,
}])
if not bill_a.line_ids.mapped("wht_tax_id"):
    log("WARN: no wht_tax_id found on bill lines")

def payments_for(move):
    if move.move_type == "in_invoice":
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        ).matched_credit_ids.credit_move_id
    else:
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).matched_debit_ids.debit_move_id
    return env["account.payment"].search([
        ("move_id", "in", matched.move_id.ids),
        ("company_id", "=", company.id)])


payment_a = payments_for(bill_a)
if not payment_a:
    payment_a = pay(bill_a, 97000.0, wht_tax=wht_tax, wht_base=100000.0,
                    label="pay bill A net of WHT")
    cert = payment_a.create_wht_cert()
    log(f"WHT cert created: {cert}")

bill_b = post_bill("MIG-BILL-002", "in_invoice", vendor, [{
    "name": "VAT bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([input_vat.id])],
}], ti_number="VAT-MIG-19-001")

inv_a = post_bill("MIG-INV-001", "out_invoice", customer, [{
    "name": "Sales item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([output_vat.id])],
}])

inv_b = post_bill("MIG-INV-002", "out_invoice", customer, [{
    "name": "Cancelled sales item", "quantity": 1, "price_unit": 50000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
}])
if inv_b.state == "posted":
    inv_b.button_cancel()
    log("MIG-INV-002 cancelled")

bill_c = post_bill("MIG-BILL-CABA", "in_invoice", vendor, [{
    "name": "CABA bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([caba_tax.id])],
}], ti_number="CABA-BILL-TI")

def number_pending_tis():
    caba_moves = env["account.move"].search([
        ("tax_cash_basis_origin_move_id", "=", bill_c.id),
        ("company_id", "=", company.id)])
    numbers = iter(["CABA-MIG-19-40", "CABA-MIG-19-60"])
    for m in caba_moves.sorted("id"):
        pending = m.tax_invoice_ids.filtered(
            lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
        if pending:
            pending.write({"tax_invoice_number": next(numbers),
                           "tax_invoice_date": bill_c.date})
    return caba_moves


existing = payments_for(bill_c)
if len(existing) < 1:
    pay(bill_c, 42800.0, label="CABA installment 40%",
        payment_date="2026-09-15")
if len(existing) < 2:
    pay(bill_c, 64200.0, label="CABA installment 60%",
        payment_date="2026-09-20")

# Both installments are paid before any clear-tax step: this is the cohort
# state that reproduces the CABA VAT over-claim (2,800 + 7,000 = 9,800).
caba_moves = number_pending_tis()
to_clear = env["account.payment"].search([
    ("to_clear_tax", "=", True), ("company_id", "=", company.id)])
for payment in to_clear:
    try:
        payment.clear_tax_cash_basis()
        log(f"cleared tax on payment {payment.name}")
    except Exception as exc:
        log(f"clear tax failed on {payment.name}: {type(exc).__name__}: "
            f"{exc}")
        payment.write({"to_clear_tax": False})

# All CABA entries must end posted; post any the clear step left behind.
for m in caba_moves.filtered(lambda m: m.state != "posted"):
    try:
        m.action_post()
        log(f"posted leftover CABA entry {m.name}")
    except Exception as exc:
        log(f"post failed on {m.name}: {type(exc).__name__}: {exc}")

log("CABA entries: " + ", ".join(
    f"{m.name}(state={m.state})" for m in caba_moves))
for m in caba_moves:
    for ti in m.tax_invoice_ids:
        log(f"  TI {ti.tax_invoice_number} vat={abs(ti.balance)}")

env.cr.commit()
log(f"company id={company.id}")

Partner = env["res.partner"].with_company(company)
Account = env["account.account"].with_company(company)
Tax = env["account.tax"].with_company(company)
Move = env["account.move"].with_company(company)
Wizard = env["account.payment.register"].with_company(company)


def get_partner(name, vat, is_company):
    found = Partner.search([("name", "=", name)])
    assert len(found) <= 1, f"Ambiguous partner {name}"
    if found:
        return found
    return Partner.with_context(no_vat_validation=True).create({
        "name": name, "vat": vat, "is_company": is_company,
        "country_id": env.ref("base.th").id,
    })


vendor = get_partner("Rehearsal Vendor Co., Ltd.", "1999999999991", True)
customer = get_partner("Rehearsal Customer Co., Ltd.", "1999999999992", True)
if not env["res.partner.bank"].with_company(company).search([
        ("partner_id", "=", vendor.id)]):
    bank = env["res.bank"].search([("bic", "=", "RHBKTHBK")]) or \
        env["res.bank"].create({"name": "Rehearsal Bank", "bic": "RHBKTHBK"})
    vals = {"acc_number": "0993000123456", "partner_id": vendor.id,
            "bank_id": bank.id}
    if "proxy_value" in env["res.partner.bank"]._fields:
        vals["proxy_value"] = "0819999999"
    env["res.partner.bank"].create(vals)
    log("vendor bank/proxy created")

# --- WHT account + withholding tax (name is propagated to target by runner)
wht_account = Account.search([("code", "=", "MIGWHT19")])
assert len(wht_account) <= 1, "Ambiguous MIGWHT19 account"
if not wht_account:
    wht_account = Account.create({
        "name": "Withholding Tax Payable (Migration)",
        "code": "MIGWHT19", "account_type": "liability_current",
        "wht_account": True,
    })
wht_tax = env["account.withholding.tax"].with_company(company).search([
    ("name", "=", "WHT 3%"), ("company_id", "=", company.id)])
assert len(wht_tax) <= 1, "Ambiguous WHT 3% withholding tax"
if not wht_tax:
    wht_tax = env["account.withholding.tax"].with_company(company).create({
        "name": "WHT 3%", "account_id": wht_account.id, "amount": 3.0,
        "income_tax_form": "pnd53", "wht_cert_income_type": "2",
    })
log(f"WHT tax id={wht_tax.id} account={wht_account.code}")

# --- CABA tax: copy of the chart's 7% purchase tax with a transition account
transition = Account.search([("code", "=", "114299")])
assert len(transition) <= 1, "Ambiguous 114299 transition account"
if not transition:
    transition = Account.create({
        "name": "Input VAT (CABA transition)", "code": "114299",
        "account_type": "asset_current", "reconcile": True,
    })
base_tax = Tax.search([
    ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
    ("amount", "=", 7.0), ("tax_exigibility", "=", "on_invoice")])
assert len(base_tax) == 1, f"Expected one 7% purchase tax, got {len(base_tax)}"
caba_tax = Tax.search([("company_id", "=", company.id),
                       ("tax_exigibility", "=", "on_payment"),
                       ("type_tax_use", "=", "purchase")])
assert len(caba_tax) <= 1, "Ambiguous CABA tax"
if not caba_tax:
    caba_tax = base_tax.copy({
        "name": "VAT7-ONPAYMENT", "tax_exigibility": "on_payment",
        "cash_basis_transition_account_id": transition.id,
    })
log(f"CABA tax id={caba_tax.id} transition={transition.code}")

input_vat = base_tax
output_vat = Tax.search([("company_id", "=", company.id),
                         ("type_tax_use", "=", "sale"),
                         ("amount", "=", 7.0),
                         ("tax_exigibility", "=", "on_invoice")])
assert len(output_vat) == 1, "Expected one 7% sale tax"
expense = Account.search([("code", "=", "611100")])
assert len(expense) == 1, "Chart must provide 611100"


def fill_tax_invoice_numbers(move, number):
    pending = move.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    pending.write({"tax_invoice_number": number,
                   "tax_invoice_date": move.invoice_date or move.date})
    log(f"TI {number} written on {len(pending)} row(s) of {move.ref}")


def post_bill(ref, move_type, partner, line_vals, ti_number=None):
    move = Move.search([("ref", "=", ref), ("move_type", "=", move_type),
                        ("company_id", "=", company.id)])
    assert len(move) <= 1, f"Ambiguous document {ref}"
    if move:
        log(f"{ref} already exists ({move.state})")
        return move
    move = Move.create({
        "move_type": move_type, "partner_id": partner.id, "ref": ref,
        "invoice_date": "2026-09-01", "date": "2026-09-01",
        "invoice_line_ids": [Command.create(vals) for vals in line_vals],
    })
    try:
        move.action_post()
    except Exception as exc:  # legacy asks for vendor TI info at post time
        log(f"post {ref} deferred ({exc}); filling TI {ti_number}")
        fill_tax_invoice_numbers(move, ti_number or "TI-" + ref)
        move.action_post()
    assert move.state == "posted", (ref, move.state)
    if ti_number and move.tax_invoice_ids:
        fill_tax_invoice_numbers(move, ti_number)
    log(f"{ref} posted, total={move.amount_total}")
    return move


def pay(move, amount, wht_tax=None, wht_base=None, label="",
        payment_date="2026-09-10"):
    wizard = Wizard.with_context(
        active_model="account.move", active_ids=[move.id]).create(
        {"payment_date": payment_date})
    if wht_tax:
        wizard.wht_tax_id = wht_tax
        wizard.wht_amount_base = wht_base
        wizard._onchange_wht()
        wizard.payment_difference_handling = "reconcile"
    else:
        wizard.amount = amount
    log(f"wizard: partner={wizard.partner_id.name} diff_handling="
        f"{wizard.payment_difference_handling} amount={wizard.amount}")
    assert abs(wizard.amount - amount) < 0.01, \
        (label, wizard.amount, amount)
    payments = wizard._create_payments()
    assert len(payments) == 1, (label, payments)
    payment = payments[0]
    log(f"{label}: payment {payment.amount}, to_clear_tax="
        f"{getattr(payment, 'to_clear_tax', False)}")
    return payment


bill_a = post_bill("MIG-BILL-001", "in_invoice", vendor, [{
    "name": "WHT bill service", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
    "wht_tax_id": wht_tax.id,
}])
if not bill_a.line_ids.mapped("wht_tax_id"):
    log("WARN: no wht_tax_id found on bill lines")

def payments_for(move):
    if move.move_type == "in_invoice":
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        ).matched_credit_ids.credit_move_id
    else:
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).matched_debit_ids.debit_move_id
    return env["account.payment"].search([
        ("move_id", "in", matched.move_id.ids),
        ("company_id", "=", company.id)])


payment_a = payments_for(bill_a)
if not payment_a:
    payment_a = pay(bill_a, 97000.0, wht_tax=wht_tax, wht_base=100000.0,
                    label="pay bill A net of WHT")
    cert = payment_a.create_wht_cert()
    log(f"WHT cert created: {cert}")

bill_b = post_bill("MIG-BILL-002", "in_invoice", vendor, [{
    "name": "VAT bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([input_vat.id])],
}], ti_number="VAT-MIG-19-001")

inv_a = post_bill("MIG-INV-001", "out_invoice", customer, [{
    "name": "Sales item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([output_vat.id])],
}])

inv_b = post_bill("MIG-INV-002", "out_invoice", customer, [{
    "name": "Cancelled sales item", "quantity": 1, "price_unit": 50000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
}])
if inv_b.state == "posted":
    inv_b.button_cancel()
    log("MIG-INV-002 cancelled")

bill_c = post_bill("MIG-BILL-CABA", "in_invoice", vendor, [{
    "name": "CABA bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([caba_tax.id])],
}], ti_number="CABA-BILL-TI")

def number_and_clear(ti_number, label):
    caba_moves = env["account.move"].search([
        ("tax_cash_basis_origin_move_id", "=", bill_c.id),
        ("company_id", "=", company.id)])
    pending = caba_moves.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    if pending:
        pending.write({"tax_invoice_number": ti_number,
                       "tax_invoice_date": bill_c.date})
        log(f"numbered {len(pending)} CABA TI row(s) as {ti_number}")
    to_clear = env["account.payment"].search([
        ("to_clear_tax", "=", True), ("company_id", "=", company.id)])
    for payment in to_clear:
        try:
            payment.clear_tax_cash_basis()
            log(f"cleared tax on payment {payment.name}")
        except Exception as exc:
            log(f"clear tax failed on {payment.name}: {type(exc).__name__}: "
                f"{exc}")
            payment.write({"to_clear_tax": False})
    return caba_moves


existing = payments_for(bill_c)
if len(existing) < 1:
    pay(bill_c, 42800.0, label="CABA installment 40%",
        payment_date="2026-09-15")
    number_and_clear("CABA-MIG-19-40", "after 40%")
if len(existing) < 2:
    pay(bill_c, 64200.0, label="CABA installment 60%",
        payment_date="2026-09-20")
    number_and_clear("CABA-MIG-19-60", "after 60%")

# All CABA entries must end posted; post any the clear step left behind.
caba_moves = env["account.move"].search([
    ("tax_cash_basis_origin_move_id", "=", bill_c.id),
    ("company_id", "=", company.id)])
for m in caba_moves.filtered(lambda m: m.state != "posted"):
    try:
        m.action_post()
        log(f"posted leftover CABA entry {m.name}")
    except Exception as exc:
        log(f"post failed on {m.name}: {type(exc).__name__}: {exc}")

log("CABA entries: " + ", ".join(
    f"{m.name}(state={m.state})" for m in caba_moves))
for m in caba_moves:
    for ti in m.tax_invoice_ids:
        log(f"  TI {ti.tax_invoice_number} vat={abs(ti.balance)}")

env.cr.commit()
log(f"company id={company.id}")

Partner = env["res.partner"].with_company(company)
Account = env["account.account"].with_company(company)
Tax = env["account.tax"].with_company(company)
Move = env["account.move"].with_company(company)
Wizard = env["account.payment.register"].with_company(company)


def get_partner(name, vat, is_company):
    found = Partner.search([("name", "=", name)])
    assert len(found) <= 1, f"Ambiguous partner {name}"
    if found:
        return found
    return Partner.with_context(no_vat_validation=True).create({
        "name": name, "vat": vat, "is_company": is_company,
        "country_id": env.ref("base.th").id,
    })


vendor = get_partner("Rehearsal Vendor Co., Ltd.", "1999999999991", True)
customer = get_partner("Rehearsal Customer Co., Ltd.", "1999999999992", True)
if not env["res.partner.bank"].with_company(company).search([
        ("partner_id", "=", vendor.id)]):
    bank = env["res.bank"].search([("bic", "=", "RHBKTHBK")]) or \
        env["res.bank"].create({"name": "Rehearsal Bank", "bic": "RHBKTHBK"})
    vals = {"acc_number": "0993000123456", "partner_id": vendor.id,
            "bank_id": bank.id}
    if "proxy_value" in env["res.partner.bank"]._fields:
        vals["proxy_value"] = "0819999999"
    env["res.partner.bank"].create(vals)
    log("vendor bank/proxy created")

# --- WHT account + withholding tax (name is propagated to target by runner)
wht_account = Account.search([("code", "=", "MIGWHT19")])
assert len(wht_account) <= 1, "Ambiguous MIGWHT19 account"
if not wht_account:
    wht_account = Account.create({
        "name": "Withholding Tax Payable (Migration)",
        "code": "MIGWHT19", "account_type": "liability_current",
        "wht_account": True,
    })
wht_tax = env["account.withholding.tax"].with_company(company).search([
    ("name", "=", "WHT 3%"), ("company_id", "=", company.id)])
assert len(wht_tax) <= 1, "Ambiguous WHT 3% withholding tax"
if not wht_tax:
    wht_tax = env["account.withholding.tax"].with_company(company).create({
        "name": "WHT 3%", "account_id": wht_account.id, "amount": 3.0,
        "income_tax_form": "pnd53", "wht_cert_income_type": "2",
    })
log(f"WHT tax id={wht_tax.id} account={wht_account.code}")

# --- CABA tax: copy of the chart's 7% purchase tax with a transition account
transition = Account.search([("code", "=", "114299")])
assert len(transition) <= 1, "Ambiguous 114299 transition account"
if not transition:
    transition = Account.create({
        "name": "Input VAT (CABA transition)", "code": "114299",
        "account_type": "asset_current", "reconcile": True,
    })
base_tax = Tax.search([
    ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
    ("amount", "=", 7.0), ("tax_exigibility", "=", "on_invoice")])
assert len(base_tax) == 1, f"Expected one 7% purchase tax, got {len(base_tax)}"
caba_tax = Tax.search([("company_id", "=", company.id),
                       ("tax_exigibility", "=", "on_payment"),
                       ("type_tax_use", "=", "purchase")])
assert len(caba_tax) <= 1, "Ambiguous CABA tax"
if not caba_tax:
    caba_tax = base_tax.copy({
        "name": "VAT7-ONPAYMENT", "tax_exigibility": "on_payment",
        "cash_basis_transition_account_id": transition.id,
    })
log(f"CABA tax id={caba_tax.id} transition={transition.code}")

input_vat = base_tax
output_vat = Tax.search([("company_id", "=", company.id),
                         ("type_tax_use", "=", "sale"),
                         ("amount", "=", 7.0),
                         ("tax_exigibility", "=", "on_invoice")])
assert len(output_vat) == 1, "Expected one 7% sale tax"
expense = Account.search([("code", "=", "611100")])
assert len(expense) == 1, "Chart must provide 611100"


def fill_tax_invoice_numbers(move, number):
    pending = move.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    pending.write({"tax_invoice_number": number,
                   "tax_invoice_date": move.invoice_date or move.date})
    log(f"TI {number} written on {len(pending)} row(s) of {move.ref}")


def post_bill(ref, move_type, partner, line_vals, ti_number=None):
    move = Move.search([("ref", "=", ref), ("move_type", "=", move_type),
                        ("company_id", "=", company.id)])
    assert len(move) <= 1, f"Ambiguous document {ref}"
    if move:
        log(f"{ref} already exists ({move.state})")
        return move
    move = Move.create({
        "move_type": move_type, "partner_id": partner.id, "ref": ref,
        "invoice_date": "2026-09-01", "date": "2026-09-01",
        "invoice_line_ids": [Command.create(vals) for vals in line_vals],
    })
    try:
        move.action_post()
    except Exception as exc:  # legacy asks for vendor TI info at post time
        log(f"post {ref} deferred ({exc}); filling TI {ti_number}")
        fill_tax_invoice_numbers(move, ti_number or "TI-" + ref)
        move.action_post()
    assert move.state == "posted", (ref, move.state)
    if ti_number and move.tax_invoice_ids:
        fill_tax_invoice_numbers(move, ti_number)
    log(f"{ref} posted, total={move.amount_total}")
    return move


def pay(move, amount, wht_tax=None, wht_base=None, label="",
        payment_date="2026-09-10"):
    wizard = Wizard.with_context(
        active_model="account.move", active_ids=[move.id]).create(
        {"payment_date": payment_date})
    if wht_tax:
        wizard.wht_tax_id = wht_tax
        wizard.wht_amount_base = wht_base
        wizard._onchange_wht()
        wizard.payment_difference_handling = "reconcile"
    else:
        wizard.amount = amount
    log(f"wizard: partner={wizard.partner_id.name} diff_handling="
        f"{wizard.payment_difference_handling} amount={wizard.amount}")
    assert abs(wizard.amount - amount) < 0.01, \
        (label, wizard.amount, amount)
    payments = wizard._create_payments()
    assert len(payments) == 1, (label, payments)
    payment = payments[0]
    log(f"{label}: payment {payment.amount}, to_clear_tax="
        f"{getattr(payment, 'to_clear_tax', False)}")
    return payment


bill_a = post_bill("MIG-BILL-001", "in_invoice", vendor, [{
    "name": "WHT bill service", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
    "wht_tax_id": wht_tax.id,
}])
if not bill_a.line_ids.mapped("wht_tax_id"):
    log("WARN: no wht_tax_id found on bill lines")

def payments_for(move):
    if move.move_type == "in_invoice":
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        ).matched_credit_ids.credit_move_id
    else:
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).matched_debit_ids.debit_move_id
    return env["account.payment"].search([
        ("move_id", "in", matched.move_id.ids),
        ("company_id", "=", company.id)])


payment_a = payments_for(bill_a)
if not payment_a:
    payment_a = pay(bill_a, 97000.0, wht_tax=wht_tax, wht_base=100000.0,
                    label="pay bill A net of WHT")
    cert = payment_a.create_wht_cert()
    log(f"WHT cert created: {cert}")

bill_b = post_bill("MIG-BILL-002", "in_invoice", vendor, [{
    "name": "VAT bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([input_vat.id])],
}], ti_number="VAT-MIG-19-001")

inv_a = post_bill("MIG-INV-001", "out_invoice", customer, [{
    "name": "Sales item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([output_vat.id])],
}])

inv_b = post_bill("MIG-INV-002", "out_invoice", customer, [{
    "name": "Cancelled sales item", "quantity": 1, "price_unit": 50000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
}])
if inv_b.state == "posted":
    inv_b.button_cancel()
    log("MIG-INV-002 cancelled")

bill_c = post_bill("MIG-BILL-CABA", "in_invoice", vendor, [{
    "name": "CABA bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([caba_tax.id])],
}], ti_number="CABA-BILL-TI")

def settle_caba(amount, ti_number, label):
    payment = pay(bill_c, amount, label=label)
    caba_moves = env["account.move"].search([
        ("tax_cash_basis_origin_move_id", "=", bill_c.id),
        ("company_id", "=", company.id)])
    pending = caba_moves.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    if pending:
        pending.write({"tax_invoice_number": ti_number,
                       "tax_invoice_date": bill_c.date})
        log(f"numbered {len(pending)} CABA TI row(s) as {ti_number}")
    to_clear = env["account.payment"].search([
        ("to_clear_tax", "=", True), ("company_id", "=", company.id)])
    if to_clear:
        to_clear.clear_tax_cash_basis()
        log(f"cleared tax on {len(to_clear)} payment(s)")


existing = payments_for(bill_c)
if len(existing) < 1:
    settle_caba(42800.0, "CABA-MIG-19-40", "CABA installment 40%")
if len(existing) < 2:
    settle_caba(64200.0, "CABA-MIG-19-60", "CABA installment 60%")

caba_moves = env["account.move"].search([
    ("tax_cash_basis_origin_move_id", "=", bill_c.id),
    ("company_id", "=", company.id)])
log("CABA entries: " + ", ".join(
    f"{m.name}(state={m.state})" for m in caba_moves))
for m in caba_moves:
    for ti in m.tax_invoice_ids:
        log(f"  TI {ti.tax_invoice_number} vat={abs(ti.balance)}")

env.cr.commit()
log(f"company id={company.id}")

Partner = env["res.partner"].with_company(company)
Account = env["account.account"].with_company(company)
Tax = env["account.tax"].with_company(company)
Move = env["account.move"].with_company(company)
Wizard = env["account.payment.register"].with_company(company)


def get_partner(name, vat, is_company):
    found = Partner.search([("name", "=", name)])
    assert len(found) <= 1, f"Ambiguous partner {name}"
    if found:
        return found
    return Partner.with_context(no_vat_validation=True).create({
        "name": name, "vat": vat, "is_company": is_company,
        "country_id": env.ref("base.th").id,
    })


vendor = get_partner("Rehearsal Vendor Co., Ltd.", "1999999999991", True)
customer = get_partner("Rehearsal Customer Co., Ltd.", "1999999999992", True)
if not env["res.partner.bank"].with_company(company).search([
        ("partner_id", "=", vendor.id)]):
    bank = env["res.bank"].search([("bic", "=", "RHBKTHBK")]) or \
        env["res.bank"].create({"name": "Rehearsal Bank", "bic": "RHBKTHBK"})
    vals = {"acc_number": "0993000123456", "partner_id": vendor.id,
            "bank_id": bank.id}
    if "proxy_value" in env["res.partner.bank"]._fields:
        vals["proxy_value"] = "0819999999"
    env["res.partner.bank"].create(vals)
    log("vendor bank/proxy created")

# --- WHT account + withholding tax (name is propagated to target by runner)
wht_account = Account.search([("code", "=", "MIGWHT19")])
assert len(wht_account) <= 1, "Ambiguous MIGWHT19 account"
if not wht_account:
    wht_account = Account.create({
        "name": "Withholding Tax Payable (Migration)",
        "code": "MIGWHT19", "account_type": "liability_current",
        "wht_account": True,
    })
wht_tax = env["account.withholding.tax"].with_company(company).search([
    ("name", "=", "WHT 3%"), ("company_id", "=", company.id)])
assert len(wht_tax) <= 1, "Ambiguous WHT 3% withholding tax"
if not wht_tax:
    wht_tax = env["account.withholding.tax"].with_company(company).create({
        "name": "WHT 3%", "account_id": wht_account.id, "amount": 3.0,
        "income_tax_form": "pnd53", "wht_cert_income_type": "2",
    })
log(f"WHT tax id={wht_tax.id} account={wht_account.code}")

# --- CABA tax: copy of the chart's 7% purchase tax with a transition account
transition = Account.search([("code", "=", "114299")])
assert len(transition) <= 1, "Ambiguous 114299 transition account"
if not transition:
    transition = Account.create({
        "name": "Input VAT (CABA transition)", "code": "114299",
        "account_type": "asset_current", "reconcile": True,
    })
base_tax = Tax.search([
    ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
    ("amount", "=", 7.0), ("tax_exigibility", "=", "on_invoice")])
assert len(base_tax) == 1, f"Expected one 7% purchase tax, got {len(base_tax)}"
caba_tax = Tax.search([("company_id", "=", company.id),
                       ("tax_exigibility", "=", "on_payment"),
                       ("type_tax_use", "=", "purchase")])
assert len(caba_tax) <= 1, "Ambiguous CABA tax"
if not caba_tax:
    caba_tax = base_tax.copy({
        "name": "VAT7-ONPAYMENT", "tax_exigibility": "on_payment",
        "cash_basis_transition_account_id": transition.id,
    })
log(f"CABA tax id={caba_tax.id} transition={transition.code}")

input_vat = base_tax
output_vat = Tax.search([("company_id", "=", company.id),
                         ("type_tax_use", "=", "sale"),
                         ("amount", "=", 7.0),
                         ("tax_exigibility", "=", "on_invoice")])
assert len(output_vat) == 1, "Expected one 7% sale tax"
expense = Account.search([("code", "=", "611100")])
assert len(expense) == 1, "Chart must provide 611100"


def fill_tax_invoice_numbers(move, number):
    pending = move.tax_invoice_ids.filtered(
        lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
    pending.write({"tax_invoice_number": number,
                   "tax_invoice_date": move.invoice_date or move.date})
    log(f"TI {number} written on {len(pending)} row(s) of {move.ref}")


def post_bill(ref, move_type, partner, line_vals, ti_number=None):
    move = Move.search([("ref", "=", ref), ("move_type", "=", move_type),
                        ("company_id", "=", company.id)])
    assert len(move) <= 1, f"Ambiguous document {ref}"
    if move:
        log(f"{ref} already exists ({move.state})")
        return move
    move = Move.create({
        "move_type": move_type, "partner_id": partner.id, "ref": ref,
        "invoice_date": "2026-09-01", "date": "2026-09-01",
        "invoice_line_ids": [Command.create(vals) for vals in line_vals],
    })
    try:
        move.action_post()
    except Exception as exc:  # legacy asks for vendor TI info at post time
        log(f"post {ref} deferred ({exc}); filling TI {ti_number}")
        fill_tax_invoice_numbers(move, ti_number or "TI-" + ref)
        move.action_post()
    assert move.state == "posted", (ref, move.state)
    if ti_number and move.tax_invoice_ids:
        fill_tax_invoice_numbers(move, ti_number)
    log(f"{ref} posted, total={move.amount_total}")
    return move


def pay(move, amount, wht_tax=None, wht_base=None, label="",
        payment_date="2026-09-10"):
    wizard = Wizard.with_context(
        active_model="account.move", active_ids=[move.id]).create(
        {"payment_date": payment_date})
    if wht_tax:
        wizard.wht_tax_id = wht_tax
        wizard.wht_amount_base = wht_base
        wizard._onchange_wht()
        wizard.payment_difference_handling = "reconcile"
    else:
        wizard.amount = amount
    log(f"wizard: partner={wizard.partner_id.name} diff_handling="
        f"{wizard.payment_difference_handling} amount={wizard.amount}")
    assert abs(wizard.amount - amount) < 0.01, \
        (label, wizard.amount, amount)
    payments = wizard._create_payments()
    assert len(payments) == 1, (label, payments)
    payment = payments[0]
    log(f"{label}: payment {payment.amount}, to_clear_tax="
        f"{getattr(payment, 'to_clear_tax', False)}")
    return payment


bill_a = post_bill("MIG-BILL-001", "in_invoice", vendor, [{
    "name": "WHT bill service", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
    "wht_tax_id": wht_tax.id,
}])
if not bill_a.line_ids.mapped("wht_tax_id"):
    log("WARN: no wht_tax_id found on bill lines")

def payments_for(move):
    if move.move_type == "in_invoice":
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        ).matched_credit_ids.credit_move_id
    else:
        matched = move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        ).matched_debit_ids.debit_move_id
    return env["account.payment"].search([
        ("move_id", "in", matched.move_id.ids),
        ("company_id", "=", company.id)])


payment_a = payments_for(bill_a)
if not payment_a:
    payment_a = pay(bill_a, 97000.0, wht_tax=wht_tax, wht_base=100000.0,
                    label="pay bill A net of WHT")
    cert = payment_a.create_wht_cert()
    log(f"WHT cert created: {cert}")

bill_b = post_bill("MIG-BILL-002", "in_invoice", vendor, [{
    "name": "VAT bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([input_vat.id])],
}], ti_number="VAT-MIG-19-001")

inv_a = post_bill("MIG-INV-001", "out_invoice", customer, [{
    "name": "Sales item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([output_vat.id])],
}])

inv_b = post_bill("MIG-INV-002", "out_invoice", customer, [{
    "name": "Cancelled sales item", "quantity": 1, "price_unit": 50000.0,
    "account_id": expense.id, "tax_ids": [Command.clear()],
}])
if inv_b.state == "posted":
    inv_b.button_cancel()
    log("MIG-INV-002 cancelled")

bill_c = post_bill("MIG-BILL-CABA", "in_invoice", vendor, [{
    "name": "CABA bill item", "quantity": 1, "price_unit": 100000.0,
    "account_id": expense.id,
    "tax_ids": [Command.set([caba_tax.id])],
}], ti_number="CABA-BILL-TI")

caba_moves = env["account.move"].search([
    ("tax_cash_basis_origin_move_id", "=", bill_c.id),
    ("company_id", "=", company.id)])
if not caba_moves:
    pay(bill_c, 42800.0, label="CABA installment 40%",
        payment_date="2026-09-15")
    pay(bill_c, 64200.0, label="CABA installment 60%",
        payment_date="2026-09-20")
    caba_moves = env["account.move"].search([
        ("tax_cash_basis_origin_move_id", "=", bill_c.id)])

# CABA TIs are deferred at payment time: number them, then clear tax.
caba_numbers = iter(["CABA-MIG-19-40", "CABA-MIG-19-60"])
pending_tis = caba_moves.tax_invoice_ids.filtered(
    lambda ti: not ti.tax_invoice_number or not ti.tax_invoice_date)
if pending_tis:
    pending_tis.write({
        "tax_invoice_number": next(caba_numbers),
        "tax_invoice_date": bill_c.date,
    })
    log(f"numbered {len(pending_tis)} deferred CABA TI row(s)")
to_clear = env["account.payment"].search([
    ("to_clear_tax", "=", True), ("company_id", "=", company.id)])
if to_clear:
    to_clear.clear_tax_cash_basis()
    log(f"cleared tax on {len(to_clear)} payment(s)")

caba_moves = env["account.move"].search([
    ("tax_cash_basis_origin_move_id", "=", bill_c.id),
    ("company_id", "=", company.id)])
log("CABA entries: " + ", ".join(
    f"{m.name}(state={m.state})" for m in caba_moves))
for m in caba_moves:
    for ti in m.tax_invoice_ids:
        log(f"  TI {ti.tax_invoice_number} vat={abs(ti.balance)}")

env.cr.commit()
log("SEED DONE")
