# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models
from odoo.exceptions import UserError


class L10nThMigrateArchive(models.Model):
    """Raw copies of legacy-only evidence, archived so nothing historical is
    lost when the legacy engines are retired (contract rows 2 and 6 keep
    their legacy rows verbatim here)."""

    _name = "l10n_th.migrate.archive"
    _description = "Legacy Evidence Archive"
    _order = "source_table, legacy_id"

    _SOURCE_FIELDS = ("run_id", "source_table", "legacy_id", "payload")

    run_id = fields.Many2one(
        comodel_name="l10n_th.migrate.run",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source_table = fields.Char(required=True, index=True)
    legacy_id = fields.Integer(required=True)
    payload = fields.Json(string="Legacy Row", required=True)
    xref_model = fields.Char(
        string="Target Model",
        help="Model of the Odoo 20 record this legacy row is cross-referenced "
             "to (evidence only — the target record is canonical).",
    )
    xref_res_id = fields.Integer(string="Target Record ID")
    over_claim_amount = fields.Float(
        string="Over-claim Amount",
        digits="Account",
        help="For accepted CABA over-claims: legacy CABA VAT minus the "
             "official target CABA VAT for the bill — recorded separately "
             "from the row's own VAT.",
    )
    note = fields.Char(string="Cross-reference Note")

    def write(self, vals):
        if self and any(field in vals for field in self._SOURCE_FIELDS):
            raise UserError(self.env._(
                "Archive source fields (run, source table, legacy id, "
                "payload) mirror the legacy evidence verbatim and are "
                "immutable. Only the cross-reference, over-claim amount "
                "and note may be updated.",
            ))
        return super().write(vals)
