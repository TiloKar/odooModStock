from odoo import models, fields

class BbiStockLocation(models.Model):
    _name = "bbi.stock.location"
    _description = "Eigene Lagerorte als Attribute an product_template"

    name = fields.Char(store = True, required = True , string = 'Eindeutige Lagerort Bezeichnung')
