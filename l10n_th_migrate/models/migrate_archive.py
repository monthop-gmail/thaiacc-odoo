# Copyright 2026 ThaiACC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class L10nThMigrateArchive(models.Model):
    """Raw copies of legacy-only evidence, archived so nothing historical is
    lost when the legacy engines are retired (contract rows 2 and 6 keep
    their legacy rows verbatim here)."""

    _name = "l10n_th.migrate.archive"
    _description = "Legacy Evidence Archive"
    _order = "source_table, legacy_id"

    run_id = fields.Many2one(
        comodel_name="l10n_th.migrate.run",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source_table = fields.Char(required=True, index=True)
    legacy_id = fields.Integer(required=True)
    payload = fields.Json(string="Legacy Row", required=True)
