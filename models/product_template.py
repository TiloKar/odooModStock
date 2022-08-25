from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

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
        string="bbi Lagerort",
        readonly=True,
        store=False,)

    bbiMaterial_id = fields.Many2one(
        'bbi.material',
        string="Material",
        required = False,
        )

    bbiMaterial_name = fields.Char(
        related='bbiMaterial_id.name',
        string='Materialart',
        readonly=False,
        store=True,
        )

    # Die dazugehörige Protokollhistorie ist in bypass_raises.py zu finden
    protokoll_ids = fields.One2many('bbi.history', 'product_tmpl_id', readonly=True)

    #@api.onchange('default_code')
    #def getOldHistory(self):
    #    ids = []
    #    for i in self:
    #        for j in i.protokoll_ids:
    #            print(str(j._origin.id))

    def generateScancode(self):
        if not self.default_code:
            return super(models.Model,self).write({'default_code' : str(self.id)})

    roterPunkt_id = fields.Many2one(
        'res.users', 'Roter Punkt - Wer',
        help="Letzter Benutzer des Roter Punkt Felds",)

    roterPunkt_qty = fields.Float(string='Nachbestellen', digits='Product Unit of Measure')

    roterPunkt_date = fields.Datetime('Roter Punkt - Wann',
        help='Das Datum, wann die Nachbestellung geändert wurde',
        readonly=False)

    @api.onchange('roterPunkt_qty')
    def _onchange_roterPunkt_qty(self):
        self.roterPunkt_id = self.env.user
        self.roterPunkt_date = self.write_date

    @api.onchange('bbiMaterial_name', 'bbiMaterial_id')
    def checkSchmelze(self):
        if self.bbiMaterial_name != "Edelstahl":
            result = self.env['stock.production.lot'].search([('bbiSchmelze', '!=', False)])
            exists = 0
            for i in result:
                if i.product_id.product_tmpl_id.default_code == self.default_code:
                    exists = exists +1
            if exists > 0:
                raise ValidationError ("Es existiert breits eine Schmelznummer!")
