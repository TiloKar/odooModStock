from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def fixingUOMbbi(self):
        print("repairing uom in purchase_order_lines")
        lines= self.env['purchase.order.line'].search([])
        for line in lines:
            print("checking purchase order line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in order.line {} for product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in ale_order_line")
        lines= self.env['sale.order.line'].search([])
        for line in lines:
            print("checking sale_order_line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in sale.order.line {} product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in stock_moves")
        lines= self.env['stock.move'].search([])
        for line in lines:
            print("checking move {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in stock_move {} for product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in stock_move_line")
        lines= self.env['stock.move.line'].search([])
        for line in lines:
            print("checking stock_move_line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom_id.id:
                print("try to fix uom bug in stock.move.line {} product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom_id' : line.product_id.product_tmpl_id.uom_id.id })
