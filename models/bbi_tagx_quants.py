
#legacy




from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    def parseLagerliste(self):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        sheet = book.sheets()[0]

        datasets = [] # wird ein array mit den anzuhängenden dictionaries
        for i in range(sheet.nrows):
            if i < 1:
                continue
            if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                rowCode = str(sheet.cell(i, 0).value).replace('\n','')
            else:
                rowCode = str(int(sheet.cell(i, 0).value))

            result = self.env['product.product'].search([('default_code', '=', rowCode)]) # product_template id.ermitteln
            if len(result) == 0:
                raise ValidationError('Scancode: {} in Zeile {} nicht gefunden'.format(rowCode, i+1))

            if result[0].product_tmpl_id.type == 'product':
                if isinstance(sheet.cell(i, 8).value, str):
                    rowQty = 0
                else:
                    rowQty = int(sheet.cell(i, 8).value)
                print('product_product: {} mit qty {} aufgenommen'.format(result[0],rowQty))
                #to do Los ID
                datasets.append({
                    'product_id': result[0].id,
                    'inventory_quantity': rowQty,
                    'location_id': 8,
                    'inventory_quantity_set' : True
                })
        for d in datasets:
            hit = self.env['stock.quant'].search([('product_id', '=', d['product_id']),('location_id', '=', d['location_id'])])
            print(str(len(hit)))
            if len(hit) > 0:
                hit[0].update(d)
            else:
                self.env['stock.quant'].create(d)
