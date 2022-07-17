from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def fixingProductsCompany(self):
        print("repairing uom in purchase_order_lines")
        lines= self.env['product.template'].search([])
        for line in lines:
            print("checking purchase order line {}".format(line.id))
            if not line.company_id:
                print("try to fix company id for product {}".format(line.id))
                line.update({'company_id' : 1 })
