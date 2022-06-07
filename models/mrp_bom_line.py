from odoo import api, fields, models

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    materialCerts = fields.Boolean(
        string = 'Product Contact',
        default=False,
        help='Check this, if BOM Position will need qualified material documentation in MO',
        store=True,
        readonly=False,)
