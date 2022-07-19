from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def fixingOldPOlines(self):
        print("repairing purchase order lines")

        lines= self.env['purchase.order.line'].search([])
        nq=0
        for l in lines:
            if not l.qty_received_method and not(l.display_type in ('line_note','line_section')):
                if 'A' in l.order_id.name:
                    nq+=1
                    print("try to fix po line {}".format(l.id))
                    l.update({'qty_received_method' : 'stock_moves' })
                else:
                    print("######################## no A in line {} - {}".format(l.id,l.order_id.name))

        print("created: {}".format(nq))
