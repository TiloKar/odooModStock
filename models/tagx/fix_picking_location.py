from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #ändert ziel von input auf stock in offenen wareneingängen
    def fixingPickingLocation(self):

        pickings= self.env['stock.picking'].search([]).filtered(lambda p: p.state not in('cancel','done') and p.location_dest_id.id == 9)
        np=0
        print("repairing {} pickings".format(len(pickings)))
        for p in pickings:
            np+=1
            print("try to fix picking {} with id {}".format(p.name,p.id))
            moves = self.env['stock.move'].search([]).filtered(lambda m: m.picking_id.id == p.id)
            if len(moves) > 0:
                for m in moves:
                    moveLines = self.env['stock.move.line'].search([]).filtered(lambda ml: ml.move_id.id == m.id)
                    if len(moveLines) > 0:
                        for ml in moveLines:
                            print("try to fix move line with id {}".format(ml.id))
                            ml.update({'location_dest_id' : 8})
                    print("try to fix move with id {}".format(m.id))
                    m.update({'location_dest_id' : 8})
            p.update({'location_dest_id' : 8})
