from odoo import api, fields, models
from odoo.exceptions import ValidationError

class BbiHistory(models.Model):
    _name = "bbi.history"
    _description = "Protokoll für Produktänderungen"

    name = fields.Char(store = True, string = 'Produktname' , readonly = 'True')
    product_tmpl_id = fields.Many2one('product.template', 'Produkt Template', store = True)
    detailed_type = fields.Char(store = True, string = 'Produktart', readonly = 'True')
    default_code = fields.Char(store = True, string = 'bbi Scancode', readonly = 'True')
    bbiDrawingNb = fields.Char(store = True, string = 'Zeichnungsnummer', readonly = 'True')
    roterPunkt_qty = fields.Char(store = True, string = 'Roter Punkt - Menge', readonly = 'True')
    roterPunkt_id = fields.Char(store = True, string = 'Roter Punkt - Wer', readonly = 'True')
    hs_code = fields.Char(store = True, string = 'HS-Code', readonly = 'True')
    list_price = fields.Float(store = True, string = 'Verkaufspreis', readonly = 'True')
    uom_id = fields.Char(store = True, string = 'Maßeinheit', readonly = 'True')
    uom_po_id = fields.Char(store = True, string = 'Maßeinheit Einkauf', readonly = 'True')
