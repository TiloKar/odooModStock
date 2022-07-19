from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def fixingQuantLocation(self):
        print("repairing quants")

        picking= self.env['stock.picking'].create({'origin':'Korrektur input->stock','move_type':'direct','location_id':9,'location_dest_id':8,'picking_type_id':5,'partner_id':13936})

        quants= self.env['stock.quant'].search([])
        nq=0
        nm=0
        for q in quants:
            if q.location_id.id == 9 and q.create_uid.id==17:
                nq+=1
                print("try to move quant {}".format(q.id))
                #q.update({'location_id' : 8 })
                self.env['stock.move'].create({
                    'name': picking.name,
                    'origin': picking.name,
                    'reference': picking.name,
                    'product_id': q.product_id.id,
                    'product_uom': q.product_id.uom_id.id,
                    'product_uom_qty' : q.quantity,
                    'location_id': 9,
                    'location_dest_id': 8,
                    'warehouse_id': 1,
                    'sequence' : 10,
                    'partner_id' : 13936,
                    'picking_id' : picking.id
                })

        print("created: {}".format(nq))
