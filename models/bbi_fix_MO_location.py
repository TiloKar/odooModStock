from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

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
        neuePO = self.env['purchase.order'].search([('write_date','>=',mydate)])
        print(len(altePO))
        print(len(neuePO))


        ausgabe= "odoo;extern\n"
        for n in neuePO:
            treffer = altePO.filtered(lambda p: False if not p.partner_ref or not n.partner_ref else p.partner_ref.strip().lower() == n.partner_ref.strip().lower())

            #print(len(treffer))
            if len(treffer) > 0:
                for t in treffer:
                    ausgabe+= "{};{}\n".format(t.name,t.partner_ref)

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'duplikate PO.csv' # Name und Format des Downloads

        #alle po vor 6.7. write date mit doppelung der partner_ref als liste
