from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert falsch übernommene mO locations und die alten PO
    def addOrderPointInfo(self):

        partsToCheck= self.env['product.product'].search([])
        k=0
        n=len(partsToCheck)
        ausgabe = 'code;name;bom;supplier;bbi\n'
        newOP = 0
        updOP = 0
        rout5 = 0
        rout7 = 0
        for p in partsToCheck:
            k+=1
            boms = self.env['mrp.bom'].search([('product_tmpl_id','=',p.product_tmpl_id.id)])
            hasBom = len(boms) > 0
            #print(len(boms))
            print("{}/{} - id:{} - boms found - {}".format(k,n,p.default_code,hasBom))
            supplier = self.env['product.supplierinfo'].search([('product_id','=',p.id)])
            hasSupplier = len(supplier) > 0
            print("{}/{} - id:{} - supplier found - {}".format(k,n,p.default_code,hasSupplier))
            hasBbiNr = False
            if p.default_code: hasBbiNr = "bbi-" in p.default_code.strip().lower()
            print("{}/{} - id:{} - bbi nr found - {}".format(k,n,p.default_code,hasBbiNr))


            valsP = {}
            valsO = {'location_id':8,'product_id':p.id}

            if hasBom:
                valsO['route_id'] = 5
                routeManu = p.route_ids.filtered(lambda r: r.id == 5)
                if len(routeManu) == 0:
                    p.write({'route_ids': [(4, 5)] })# 4 ist der operatortyp für add, die 5 ist die id des co-modells zum ergänzen
                rout5+=1

            if hasSupplier: #trägt sup_info und partner_id ein
                valsP['purchase_ok']=True
                if not ('route_id' in valsO):
                    valsO['route_id'] = 7
                valsO['supplier_id'] = supplier[0].id
                valsO['vendor_id'] = supplier[0].name.id
                routeBuy = p.route_ids.filtered(lambda r: r.id == 7)
                if len(routeBuy) == 0:
                    p.write({'route_ids': [(4, 7)] })# 4 ist der operatortyp für add, die 7 ist die id des co-modells zum ergänzen
                rout7+=1

            if hasBbiNr:
                valsP['sale_ok']=True

            if len(valsP) > 0:
                p.write(valsP)


            orderPoint = self.env['stock.warehouse.orderpoint'].search([('product_id','=',p.id)])

            #scheinbar wird nur "einkaufen" angelegt und die neuen orderpoints sind auto!!!

            if len(orderPoint) > 0: #bestehenden orderpoint  updaten
                orderPoint.write(valsO)
                updOP+=1
            else:#neu anlegen
                newOP+=1
                valsO['name'] ='scriptTK'
                valsO['trigger'] = 'manual'
                orderPoint = self.env['stock.warehouse.orderpoint'].create(valsO)

            ausgabe += '{};{};{};{};{}\n'.format(p.default_code,p.name.replace(';','|'),hasBom,hasSupplier,hasBbiNr)

            #if k>1000:break

        ausgabe += 'new OP {};updated OP {};new5 {};new7 {}'.format(newOP,updOP,rout5,rout7)
        #if len(partList) > 0 :
        #    for d in partList:
        #        ausgabe+= "{};{}\n".format(d['default_code'],d['name'].replace(';','|'))

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'artikel ohne klare beschaffungsregeln.csv' # Name und Format des Downloads
