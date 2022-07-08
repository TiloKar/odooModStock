from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'


    #legacy da das mit tos gemacht wurde
    def fixingType(self):

        result = self.env['product.product'].search([('detailed_type','=','product'),('type','!=','product')]) # product_template id.ermitteln
        if len(result) > 0:
            print("fixing {} type issues".format(len(result)))
            for p in result:
                print("fixing type issues on {} code {}".format(p,p.default_code))
                p.sudo().update({'type' : 'product'})
