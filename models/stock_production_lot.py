from odoo import api, fields, models

class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    bbiSchmelze = fields.Char(store=True, string="Schmelze")
