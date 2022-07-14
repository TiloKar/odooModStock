from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert falsch übernommene mO locations und die alten PO
    def fixMoLocation(self):

        productionsToFix= self.env['mrp.production'].search([]).filtered(lambda p: p.picking_type_id.id == 6)
        k=0
        n=len(productionsToFix)
        for p in productionsToFix:

            k+=1
            print("{} of {} fixing production {}".format(k,n,p.name))
            p.update({'picking_type_id':9,'location_src_id':8,'location_dest_id':8}) # 6,13,13 zu 9,8,8
            moves = self.env['stock.move'].search([]).filtered(lambda m: m.production_id.id == p.id)#7,13 zu 15,8 (production_id ==)
            i=0
            for m in moves:
                i+=1
                print("fixing line production {} in {}".format(i,p.name))
                m.update({'location_id':15,'location_dest_id':8,'picking_type_id' : 9, 'warehouse_id':1})
                line = self.env['stock.move.line'].search([]).filtered(lambda ml: ml.move_id.id == m.id)
                line.update({'location_id':15,'location_dest_id':8})
            moves = self.env['stock.move'].search([]).filtered(lambda m: m.raw_material_production_id.id == p.id)#8,7 zu 8,15 picking_type_id : 9 warehouse id:1  (raw_material_production_id ==)
            i=0
            for m in moves:
                i+=1
                print("fixing line raw material {} in {}".format(i,p.name))
                m.update({'location_id':8,'location_dest_id':15,'picking_type_id' : 9, 'warehouse_id':1})
                line = self.env['stock.move.line'].search([]).filtered(lambda ml: ml.move_id.id == m.id)
                line.update({'location_id':8,'location_dest_id':15})
            if k>100:break #debug ,damit kein thread timeout
        #alle po vor 6.7. write date mit doppelung der partner_ref als liste

        mydate= date(2022, 7, 6)
        altePO = self.env['purchase.order'].search([('write_date','<',mydate)])
        ausnahmen = ('P00033','P00196','P00196','P00196','P00221','A-00473','A-00488','A-00456','A-00538','A-00551','A-00615',
            'A-00611','A-00584','A-00593','A-00616','A-00635','A-00633','A-00638','P00026','A-00651','P00039','P00041',
            'P00028','P00042','P00036','P00070','P00070','P00046','P00078','P00077','P00087','P00088','P00185','P00073',
            'P00082','P00090','P00068','P00085','P00091','P00066','P00081','P00061','P00062','P00060','P00222','P00201','P00204','P00202')
        altePO = self.env['purchase.order'].search([('write_date','<',mydate)]).filtered(lambda p: p.name not in ausnahmen)
        print(len(altePO))
        i=0
        for n in altePO:
            i+=1
            print("{} delete".format(i))
            n.write({'state': 'cancel', 'mail_reminder_confirmed': False})
            n.unlink()


        #alle po vor 6.7. write date mit doppelung der partner_ref als liste
