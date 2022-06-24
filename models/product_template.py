from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    webshop = fields.Boolean(
        string = 'Im Webshop',
        default=False,
        help='Check this, if product is sold via bbi webshop',
        store=True,
        readonly=False,)

    bbiDrawingNb = fields.Char(
        string = 'bbi Zeichnungsnummer',
        help='Enter Drawing nb. if stock code (Scancode) is a bbi nb. and product needs a drawing nb. reference',
        store=True,
        readonly=False,)

    isSparePart = fields.Boolean(
        string = 'Ersatzteil',
        default=False,
        help='Check this, if product will be part of spare part BOM',
        store=True,
        readonly=False,)

    qualityCheck = fields.Boolean(
        string = 'erw. Wareneingangskontrolle',
        default=False,
        help='Check this, if product have to be checked in detail while stock input',
        store=True,
        readonly=False,)

    bbiStockLocation_id = fields.Many2one(
        'bbi.stock.location',
        string="BBI Lagerort",
        required = False,)

    locationName = fields.Char(
        related='bbiStockLocation_id.name',
        string="BBI Lagerort",
        readonly=True,
        store=False,)
