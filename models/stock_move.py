from odoo import api, fields, models

class StockMove(models.Model):
    _inherit = 'stock.move'

    materialCerts = fields.Boolean(
        string = 'MCert',
        default=False,
        help='If checked, material documentation has to be documentated while manufacturing',
        store=True,
        readonly=True,)
