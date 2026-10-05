"""Run with Odoo 20 shell on an isolated target; see MIGRATION-RUNBOOK.md.

Reads native Odoo 19 adapter views through a read-only connection. The XML IDs
are the persistent source-to-target ledger for repeat runs of this rehearsal.
Unsupported accounting shapes fail before any target commit.
"""

import json
import os
from collections import Counter
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

from odoo import Command


source_dsn = os.environ["THAIACC_SOURCE_DSN"]
target_company_name = os.environ.get("THAIACC_TARGET_COMPANY", "ThaiACC 20 Rehearsal")
source = psycopg2.connect(source_dsn)
source.set_session(readonly=True, autocommit=True)


def fetch(sql):
    with source.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]


identity = fetch("SELECT database_uuid, company_id FROM legacy19.source_identity")
assert len(identity) == 1 and identity[0]["database_uuid"] and identity[0]["company_id"], identity
source_key = identity[0]["database_uuid"].replace("-", "") + "_" + str(identity[0]["company_id"])
documents = fetch("SELECT * FROM legacy19.account_move ORDER BY id")
lines = fetch("SELECT * FROM legacy19.account_invoice_line ORDER BY move_id, id")
payments = fetch("SELECT * FROM legacy19.account_payment_evidence ORDER BY date, id")
withholding_taxes = fetch("SELECT * FROM legacy19.account_withholding_tax ORDER BY id")
partners = {row["id"]: row for row in fetch("SELECT * FROM legacy19.res_partner ORDER BY id")}
assert documents and all(
    row["move_type"] in ("in_invoice", "out_invoice", "in_refund")
    for row in documents)
assert all(row["state"] in ("posted", "cancel") for row in documents)
assert len({row["id"] for row in documents}) == len(documents)
assert len({(row["id"], row["invoice_move_id"]) for row in payments}) == len(payments)
assert all(count == 1 for count in Counter(row["id"] for row in payments).values()), \
    "A source payment settles multiple invoices; allocate it before importing"
lines_by_move = {}
for row in lines:
    lines_by_move.setdefault(row["move_id"], []).append(row)
assert all(lines_by_move.get(row["id"]) for row in documents), "Document without invoice lines"
assert all(row["account_code"] for row in lines), "Invoice line without account code"

Company = env["res.company"]
company = Company.search([("name", "=", target_company_name)])
assert len(company) <= 1, "Ambiguous target company"
if not company:
    company = Company.create({"name": target_company_name, "country_id": env.ref("base.th").id})
    env["account.chart.template"].try_loading("th", company)
assert company.account_fiscal_country_id.code == "TH", "Target must have Thai chart"
company.l10n_th_is_vat_registered = True
company.tax_exigibility = True
Partner = env["res.partner"].with_company(company)
Account = env["account.account"].with_company(company)
Tax = env["account.tax"].with_company(company)
Move = env["account.move"].with_company(company)
PaymentWizard = env["account.payment.register"].with_company(company)
WithholdingLine = env["account.payment.withholding.line"].with_company(company)
Xmlid = env["ir.model.data"]
Run = env["l10n_th.migrate.run"].with_company(company)


def linked(kind, legacy_id, model):
    name = f"odoo19_{source_key}_{kind}_{legacy_id}"
    record = Xmlid.search([("module", "=", "l10n_th_migrate"), ("name", "=", name)])
    assert len(record) <= 1 and (not record or record.model == model), name
    target = env[model].browse(record.res_id).exists() if record else env[model]
    assert not record or target, f"Dangling source identity: {name}"
    return name, target


def save_link(name, target):
    Xmlid.create({"module": "l10n_th_migrate", "name": name,
                 "model": target._name, "res_id": target.id, "noupdate": True})


def net_payment_amount(payment):
    lines = WithholdingLine.search([("payment_id", "=", payment.id)])
    return payment.amount - sum(lines.mapped("amount"))


def get_partner(legacy_id):
    row = partners[legacy_id]
    domain = [("vat", "=", row["vat"])] if row["vat"] else [("name", "=", row["name"])]
    found = Partner.search(domain)
    assert len(found) <= 1, f"Ambiguous partner {legacy_id}"
    return found or Partner.with_context(no_vat_validation=True).create({
        "name": row["name"], "vat": row["vat"],
        "is_company": row["is_company"], "country_id": env.ref("base.th").id,
    })


def get_account(code):
    found = Account.search([("code", "=", code)])
    assert len(found) == 1, f"Account {code} requires an explicit mapping"
    return found


def get_tax(spec):
    amount = Decimal(str(spec["amount"]))
    assert spec["type_tax_use"] in ("purchase", "sale") and amount == 7, \
        f"Unmapped VAT tax {spec}"
    domain = [("company_id", "=", company.id),
              ("type_tax_use", "=", spec["type_tax_use"]),
              ("amount", "=", float(amount)),
              ("tax_exigibility", "=", spec["tax_exigibility"]),
              ("is_withholding_tax", "=", False)]
    matches = Tax.search(domain)
    named = matches.filtered(lambda tax: tax.name == spec["name"])
    if len(named) == 1:
        return named
    if spec["tax_exigibility"] == "on_invoice":
        assert len(matches) == 1, f"Ambiguous VAT mapping {spec}"
        return matches
    assert spec["tax_exigibility"] == "on_payment" and not named, \
        f"Ambiguous CABA mapping {spec}"
    transition_code = spec["transition_account_code"]
    assert transition_code, f"CABA tax has no transition account {spec}"
    transition = Account.search([("code", "=", transition_code)])
    assert len(transition) <= 1, f"Ambiguous transition account {transition_code}"
    if not transition:
        transition = Account.create({
            "name": "Migration Deferred Input VAT", "code": transition_code,
            "account_type": "asset_current", "reconcile": True,
        })
    base_spec = {**spec, "name": "7%", "tax_exigibility": "on_invoice"}
    base = get_tax(base_spec)
    return base.copy({"name": spec["name"], "tax_exigibility": "on_payment",
                      "cash_basis_transition_account_id": transition.id})


# Partners must exist before the metadata runner classifies branches and banks.
for row in documents:
    get_partner(row["partner_id"])
first_run = Run.create({"source_dsn": source_dsn})
first_run.action_run()
assert first_run.state == "done", first_run.error_message
for row in withholding_taxes:
    assert row["account_code"] and row["account_type"], \
        f"Withholding tax {row['id']} has no source posting account"
    account = Account.search([("code", "=", row["account_code"])])
    assert len(account) <= 1, f"Ambiguous WHT account {row['account_code']}"
    if not account:
        account = Account.create({
            "name": row["account_name"] or row["account_code"],
            "code": row["account_code"], "account_type": row["account_type"],
        })
    tax = Tax.search([("name", "=", row["name"]),
                      ("company_id", "=", company.id),
                      ("is_withholding_tax", "=", True)])
    assert len(tax) == 1, f"Ambiguous WHT tax {row['name']}"
    for repartition in (tax.invoice_repartition_line_ids,
                        tax.refund_repartition_line_ids):
        tax_lines = repartition.filtered(lambda line: line.repartition_type == "tax")
        if any(line.account_id != account for line in tax_lines):
            tax_lines.write({"account_id": account.id})

created_documents = 0
created_payments = 0
target_moves = {}
for row in documents:
    name, move = linked("move", row["id"], "account.move")
    if move:
        assert move.company_id == company and move.ref == row["ref"] and \
            move.move_type == row["move_type"] and move.state == row["state"], \
            f"Source identity drift: move {row['id']}"
        target_moves[row["id"]] = move
        continue
    assert not Move.search([("company_id", "=", company.id),
                            ("ref", "=", row["ref"]),
                            ("move_type", "=", row["move_type"])]), \
        f"Unlinked target reference {row['ref']}"
    commands = []
    for line in lines_by_move[row["id"]]:
        taxes = [get_tax(spec).id for spec in line["taxes"]]
        if line["withholding_tax_name"]:
            wht = Tax.search([("name", "=", line["withholding_tax_name"]),
                              ("company_id", "=", company.id),
                              ("is_withholding_tax", "=", True)])
            assert len(wht) == 1, f"Missing WHT tax {line['withholding_tax_name']}"
            taxes.append(wht.id)
        commands.append(Command.create({
            "name": line["name"], "quantity": line["quantity"],
            "price_unit": line["price_unit"], "discount": line["discount"],
            "account_id": get_account(line["account_code"]).id,
            "tax_ids": [Command.set(taxes)],
        }))
    create_vals = {
        "company_id": company.id, "partner_id": get_partner(row["partner_id"]).id,
        "move_type": row["move_type"], "ref": row["ref"],
        "date": row["date"], "invoice_date": row["invoice_date"],
        "invoice_line_ids": commands,
    }
    if row["reversed_ref"]:
        origin = Move.search([
            ("ref", "=", row["reversed_ref"]), ("company_id", "=", company.id),
            ("move_type", "in", ("in_invoice", "in_receipt", "out_invoice")),
        ], limit=1)
        assert origin, f"Reversal origin {row['reversed_ref']} not imported"
        create_vals["reversed_entry_id"] = origin.id
    move = Move.create(create_vals)
    move.action_post()
    if row["state"] == "cancel":
        move.button_cancel()
    assert move.state == row["state"] and \
        abs(move.amount_total - row["amount_total"]) < 0.01, row["ref"]
    save_link(name, move)
    target_moves[row["id"]] = move
    created_documents += 1

for row in payments:
    name, payment = linked("payment", row["id"], "account.payment")
    if payment:
        assert payment.company_id == company and \
            abs(net_payment_amount(payment) - row["amount"]) < 0.01, \
            f"Source identity drift: payment {row['id']}"
        continue
    invoice = target_moves[row["invoice_move_id"]]
    assert invoice.state == "posted", f"Payment on unposted invoice {invoice.ref}"
    wizard_vals = {"payment_date": row["date"]}
    if not any(line["withholding_tax_name"]
               for line in lines_by_move[row["invoice_move_id"]]):
        wizard_vals["amount"] = row["amount"]
    wizard = PaymentWizard.with_context(
        active_model="account.move", active_ids=invoice.ids,
    ).create(wizard_vals)
    payment = wizard._create_payments()
    assert len(payment) == 1 and abs(net_payment_amount(payment) - row["amount"]) < 0.01, \
        f"Payment {row['id']}: expected net {row['amount']}, got " \
        f"{net_payment_amount(payment)} (nominal {payment.amount})"
    save_link(name, payment)
    created_payments += 1

last_run = Run.create({"source_dsn": source_dsn})
last_run.action_run()
assert last_run.state == "done", last_run.error_message
summary = last_run.stats["reconciliation_summary"]
source_ledger = {
    (row["period"], row["account_code"]): row
    for row in fetch("SELECT * FROM legacy19.account_ledger_period")
}
env.cr.execute("""
    SELECT to_char(m.date, 'YYYY-MM') AS period,
           a.code_store ->> l.company_id::text AS account_code,
           SUM(l.debit) AS debit, SUM(l.credit) AS credit
    FROM account_move_line l
    JOIN account_move m ON m.id = l.move_id
    JOIN account_account a ON a.id = l.account_id
    WHERE m.company_id = %s AND m.state = 'posted'
    GROUP BY to_char(m.date, 'YYYY-MM'), a.code_store ->> l.company_id::text
""", (company.id,))
target_ledger = {
    (row[0], row[1]): {"debit": row[2], "credit": row[3]}
    for row in env.cr.fetchall()
}
ledger_deltas = []
for period, code in sorted(source_ledger.keys() | target_ledger.keys()):
    old = source_ledger.get((period, code), {})
    new = target_ledger.get((period, code), {})
    debit_delta = round(float(new.get("debit", 0) - old.get("debit", 0)), 2)
    credit_delta = round(float(new.get("credit", 0) - old.get("credit", 0)), 2)
    if debit_delta or credit_delta:
        ledger_deltas.append({"period": period, "account_code": code,
                              "debit_delta": debit_delta,
                              "credit_delta": credit_delta,
                              "net_balance_delta": round(debit_delta - credit_delta, 2)})
gates = {
    "posted_documents": "PASS" if not summary["document_debit_delta"]
                        and not summary["document_credit_delta"]
                        and not summary["missing_document_refs"] else "DELTA",
    "full_ledger_by_period": "DELTA" if ledger_deltas else "PASS",
    "withholding": "PASS" if not summary["wht_delta"] else "DELTA",
    "on_invoice_vat": "PASS" if not last_run.stats["tax_invoice_evidence"]["unresolved"]
                      and last_run.stats["customer_tax_invoices"]["with_official_ti"]
                      == last_run.stats["customer_tax_invoices"]["legacy_rows"]
                      else "DELTA",
    "caba_vat": "PASS" if (
        (not (summary["caba_vat_delta"]
              or summary["unresolved_caba_tax_invoice_ids"]))
        or (summary.get("caba_over_claim_policy") == "official_canonical"
            and summary["unresolved_caba_tax_invoice_ids"] == [])
    ) else "DELTA",
    "canonical_identity": "PASS" if len(documents) == len(target_moves) else "DELTA",
    "pit_pnd_periods": "BLOCKED",
    "reversal_pair": "PASS" if (
        documents and all(
            target_moves[row["id"]].reversed_entry_id
            and target_moves[row["id"]].reversed_entry_id.ref == row["reversed_ref"]
            for row in documents if row["reversed_ref"]
        )
    ) else "DELTA" if any(row["reversed_ref"] for row in documents) else "BLOCKED",
    "bank_qr_render": "BLOCKED",
    "historical_50_tawi_access": "BLOCKED",
    "historical_source_snapshot": "BLOCKED",
    "post_migration_upgrade": "PASS" if os.environ.get("THAIACC_POST_UPGRADE") == "1"
                              else "BLOCKED",
}
report = {
    "source_database_uuid": identity[0]["database_uuid"],
    "source_company_id": identity[0]["company_id"],
    "target_company_id": company.id,
    "documents": {"source": len(documents), "created": created_documents,
                  "linked": len(documents)},
    "payments": {"source": len(payments), "created": created_payments,
                 "linked": len(payments)},
    "runner_id": last_run.id,
    "runner_stats": last_run.stats,
    "ledger_period_deltas": ledger_deltas,
    "gates": gates,
    "status": "BLOCKED" if "BLOCKED" in gates.values() else
              "DELTA" if "DELTA" in gates.values() else "PASS",
}
env.cr.commit()
source.close()
print("THAIACC_REHEARSAL_REPORT=" + json.dumps(report, default=str, sort_keys=True))
