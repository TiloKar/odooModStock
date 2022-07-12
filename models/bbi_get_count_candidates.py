from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #repariert falsch übernommene mO locations und die alten PO
    def getPartToCount(self):

        partList = []
        productionsToCheck= self.env['mrp.production'].search([]).filtered(lambda p: p.state not in('draft','cancel','done'))
        k=0
        n=len(productionsToCheck)
        for p in productionsToCheck:
            k+=1
            print("{} of {} checking production {}".format(k,n,p.name))
            moves = self.env['stock.move'].search([]).filtered(lambda m: m.raw_material_production_id.id == p.id)
            i=0
            for m in moves:
                i+=1
                print("checking raw material {} in {}".format(i,p.name))
                toAppend = True
                for c in partList:
                    if c['product_id'] == m.product_id.id:
                        toAppend = False
                        break
                if toAppend:
                    partList.append({'product_id' : m.product_id.id,'name' : m.product_id.name,'default_code' : m.product_id.default_code })

        ausgabe = 'code;name\nto create:\n'

        if len(partList) > 0 :
            for d in partList:
                ausgabe+= "{};{}\n".format(d['default_code'],d['name'].replace(';','|'))

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'offene MO Komponenten mit Fehlbestandspotenzial .csv' # Name und Format des Downloads
