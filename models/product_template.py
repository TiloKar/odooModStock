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

    @api.onchange('type')
    def _onchange_type(self):
        #wenn woanders diser super call kommt gibt es auch probleme

        # hier super call verändert, damit nicht die alte methode nochmal aufgerufen wird
        #res = super(models.Model,self).write(vals)
        #res = super(ProductTemplate, self)._onchange_type() or {}
        res = {}
        if self.type == 'consu' and self.tracking != 'none':
            self.tracking = 'none'

        # Return a warning when trying to change the product type
        if self.ids and self.product_variant_ids.ids and self.env['stock.move.line'].sudo().search_count([
            ('product_id', 'in', self.product_variant_ids.ids), ('state', '!=', 'cancel')
        ]):
            #res['warning'] = {
            #    'title': _('Warning!'),
            #    'message': _(
            #        'This product has been used in at least one inventory movement. '
            #        'It is not advised to change the Product Type since it can lead to inconsistencies. '
            #        'A better solution could be to archive the product and create a new one instead.'
            #    )
            #}
            print("bypassing raise in product_template._onchange_type()")
        return res

    # bypass raises in product_template methoden und loggerfunktion zum ende der methode
    def write(self, vals):
        self._sanitize_vals(vals)
        if 'uom_id' in vals:
            new_uom = self.env['uom.uom'].browse(vals['uom_id'])
            updated = self.filtered(lambda template: template.uom_id != new_uom)
            done_moves = self.env['stock.move'].search([('product_id', 'in', updated.with_context(active_test=False).mapped('product_variant_ids').ids)], limit=1)
            ausgabe=""
            if done_moves:
                #unlock all moves with state done
                closed_moves = done_moves.filtered(lambda m: m.state == 'done')

                #bbi inherit alle stock_moves auf die einheit bringen

                #error_move_lines= self.env['stock.move'].search([])

                for line in done_moves:
                    ausgabe += "moves to handle {} origin {} reference {}\n".format(line.id, line.origin,line.reference)
                    #if line.product_id.product_tmpl_id.uom_id.id != self.uom_id.id:
                        #if line.state == 'done':
                        #    if line.picking_id:
                        #        print("try to fix uom bug in stock.move {} for {} in picking {} in state {} origin {} reference {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.picking_id.name,line.state,line.origin,line.reference))
                        #    else:
                        #        print("try to fix uom bug in stock.move {} for {} with no picking id in state {} origin {} reference {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.state,line.origin,line.reference))
                    print("updating product move {} for product {} with uom {}".format(line.id,line.product_id.default_code,new_uom))
                    line.update({'product_uom' : new_uom })

                #ende inherit
                print("bypassing raise in product_template.write(vals)")
                #raise UserError(_("You cannot change the unit of measure as there are already stock moves for this product. If you want to change the unit of measure, you should rather archive this product and create a new one.\n{}".format(ausgabe)))
        if 'type' in vals and vals['type'] != 'product' and sum(self.mapped('nbr_reordering_rules')) != 0:
            print("bypassing raise in product_template.write(vals)")
            #raise UserError(_('You still have some active reordering rules on this product. Please archive or delete them first.'))
        if any('type' in vals and vals['type'] != prod_tmpl.type for prod_tmpl in self):
            existing_move_lines = self.env['stock.move.line'].search([
                ('product_id', 'in', self.mapped('product_variant_ids').ids),
                ('state', 'in', ['partially_available', 'assigned']),
            ])
            if existing_move_lines:

                for line in existing_move_lines:
                    print("try to unreserve move_line {}".format(line.id))
                    line.update({'product_uom_qty' : 0})


                print("bypassing raise in product_template.write(vals)")
                #raise UserError(_("You can not change the type of a product that is currently reserved on a stock move. If you need to change the type, you should first unreserve the stock move."))
        if 'type' in vals and vals['type'] != 'product' and any(p.type == 'product' and not float_is_zero(p.qty_available, precision_rounding=p.uom_id.rounding) for p in self):
            print("bypassing raise in product_template.write(vals)")
            #raise UserError(_("Available quantity should be set to zero before changing type"))

        #Hinzufügen von Datensätzen aus dem Protokollfeature aus Produkt Template diese Datensätze werden an bbi_history angehangen
        #Es wird zwischen roter punkt Produkten und anderen Produkten unterschieden, wodurch weniger und präzisere Daten übertragen werden.

        #im allgemeinen Fall Einlagerbar / Dienstleistung / etc alle allgemeinen attribute
        #protokoll_historie={
        #    'name': self.name,
        #    'default_code' : self.default_code,
        #    'product_tmpl_id': self._origin.id,
        #    'bbiDrawingNb': self.bbiDrawingNb,
        #    'detailed_type': self.detailed_type,
        #    'hs_code': self.hs_code,
        #    'uom_id': self.uom_id.name,
        #    'uom_po_id': self.uom_po_id.name,
        #    'list_price': self.list_price,}
        #Fall roter Punkt, zusätzlich noch diese
        #if self.detailed_type == 'consu':

        #    protokoll_historie['roterPunkt_qty'] = self.roterPunkt_qty
        #    protokoll_historie['roterPunkt_id'] = self.roterPunkt_id.partner_id.name

        #eintrag absetzen
        #self.env['bbi.history'].create(protokoll_historie)

        #ab hier loggerfunction iin den chatter
        if self.name:
            translation = self.env['ir.translation'].search([('src', '=', self.name)])
            if len(translation) == 1:
                original = " "
                translated = " "
                if translation.src == translation.value:
                    original = translation.id
                else:
                    translated = translation.id
                print("Original: {} und Übersetzt: {}.".format(original, translated))

        # Protokollfunktion für die Chatterbox
        product=self.env['product.template'].search([('id','=',self.id)])
        if (len(product) == 1):
            if ('default_code' in vals.keys()) and (self.default_code) :
                if self.default_code != vals['default_code']:
                    myMessage='bbi Scanncode changed from {} to {}.'.format(self.default_code,vals['default_code'])
                    product.message_post(body=myMessage)
            if ('name' in vals.keys()) and (self.name) :
                if self.name != vals['name']:
                    myMessage='Product Name changed from {} to {}.'.format(self.name,vals['name'])
                    product.message_post(body=myMessage)
            if ('bbiDrawingNb' in vals.keys()) and (self.bbiDrawingNb) :
                if self.bbiDrawingNb != vals['bbiDrawingNb']:
                    myMessage='bbi Drawing Number changed from {} to {}.'.format(self.bbiDrawingNb,vals['bbiDrawingNb'])
                    product.message_post(body=myMessage)
            if ('detailed_type' in vals.keys()) and (self.detailed_type) :
                if self.detailed_type != vals['detailed_type']:
                    myMessage='Pruduct Type changed from {} to {}.'.format(self.detailed_type,vals['detailed_type'])
                    product.message_post(body=myMessage)
            if ('hs_code' in vals.keys()) and (self.hs_code) :
                if self.hs_code != vals['hs_code']:
                    myMessage='HS-Code changed from {} to {}.'.format(self.hs_code,vals['hs_code'])
                    product.message_post(body=myMessage)
            if ('uom_id' in vals.keys()) and (self.uom_id) :
                if self.uom_id != vals['uom_id']:
                    myMessage='Unit of Measure changed from {} to {}.'.format(self.uom_id,vals['uom_id'])
                    product.message_post(body=myMessage)
            if ('uom_po_id' in vals.keys()) and (self.uom_po_id) :
                if self.uom_po_id != vals['uom_po_id']:
                    myMessage='Purchase UoM changed from {} to {}.'.format(self.uom_po_id,vals['uom_po_id'])
                    product.message_post(body=myMessage)
            if ('list_price' in vals.keys()) and (self.list_price) :
                if self.list_price != vals['list_price']:
                    myMessage='Sales Price changed from {} to {}.'.format(self.list_price,vals['list_price'])
                    product.message_post(body=myMessage)
            if ('roterPunkt_qty' in vals.keys()) and (self.roterPunkt_qty) :
                if self.roterPunkt_qty != vals['roterPunkt_qty']:
                    myMessage='Nachbestellen changed from {} to {}.'.format(self.roterPunkt_qty,vals['roterPunkt_qty'])
                    product.message_post(body=myMessage)
            if ('list_price' in vals.keys()) and (self.list_price) :
                if self.roterPunkt_id != vals['roterPunkt_id']:
                    myMessage='Roter Punkt - Wer changed from {} to {}.'.format(self.roterPunkt_id,vals['roterPunkt_id'])
                    product.message_post(body=myMessage)
        #weitergabe an ursprüngliche write
        # hier super call verändert auf models.Model, damit nicht die alte methode nochmal aufgerufen wird
        return super(models.Model,self).write(vals)
