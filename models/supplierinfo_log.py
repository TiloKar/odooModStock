from odoo import api, fields, models

#mini protokollfunktion im chatter erstmal nur für preis,menge und nummer
class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    #hängt sich in write vererbungskette
    def write(self, vals):
        if len(self.product_tmpl_id) != 1: #ensure one für product_tmpl_id
            return super(SupplierInfo,self).write(vals)
        product=self.env['product.template'].search([('id','=',self.product_tmpl_id.id)])
        if len(self.name) != 1: #ensure_one für partner_id
            return super(SupplierInfo,self).write(vals)
        partner=self.env['res.partner'].search([('id','=',self.name.id)])
        if (len(product) == 1) and (len(partner) == 1):
            if ('min_qty' in vals.keys()) and (self.min_qty) :
                if self.min_qty != vals['min_qty']:
                    myMessage='min_qty for supplier {} changed from {} to {}'.format(partner.name,self.min_qty,vals['min_qty'])
                    product.message_post(body=myMessage)
            if ('product_code' in vals.keys()) and (self.product_code) :
                if self.product_code != vals['product_code']:
                    myMessage='product_code for supplier {} changed from {} to {}'.format(partner.name,self.product_code,vals['product_code'])
                    product.message_post(body=myMessage)
            if ('price' in vals.keys()) and (self.price) :
                if self.price != vals['price']:
                    myMessage='price for supplier {} changed from {} to {}'.format(partner.name,self.price,vals['price'])
                    product.message_post(body=myMessage)
            if ('delay' in vals.keys()) and (self.delay) :
                if self.delay != vals['delay']:
                    myMessage='lead_time for supplier {} changed from {} to {}'.format(partner.name,self.delay,vals['delay'])
                    product.message_post(body=myMessage)

        return super(SupplierInfo,self).write(vals)
