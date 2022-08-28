from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #update kaufmann preise
    def updateKaufmannPrices(self):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        sheet = book.sheets()[0]

        kaufmann = []

        for i in range(sheet.nrows):
            if i < 1:
                continue
            print("lese kaufmann zeile: {}".format(i+1))
            if isinstance(sheet.cell(i, 1).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                rowCode = str(sheet.cell(i, 1).value).replace('\n','')
            else:
                rowCode = str(int(sheet.cell(i, 1).value))

            if sheet.cell(i, 31).value == '':
                price = 0
            else:
                price = float(sheet.cell(i, 31).value)



            kaufmann.append({
                'default_code' : rowCode,
                'standard_price': price
            })

        allProducts = self.env['product.product'].search([])
        candidatesOdoo = []
        for p in allProducts:
            candidatesOdoo.append({
                'id' : p.id,
                'default_code' : p.default_code,
            })

        i=0
        toUpdate = []
        for p in kaufmann:
            i+=1
            result = list(filter(lambda pIt: self.compKaufmannCheck(pIt,p),candidatesOdoo)) # product_template id.ermitteln
            if len(result) != 0:
                toUpdate.append({
                    'id': result[0]['id'],
                    'standard_price': p['standard_price'],
                })
                print("kaufmann zeile: {} für update aufgenommen".format(i))
            candidatesOdoo.remove({ #damit für alle folgenden iterationen die suchkandidaten kleiner werden
                'id' : result[0]['id'],
                'default_code' : result[0]['default_code'],
            })
        ausgabe = ''

        n = len(toUpdate)
        print("zum update markierte produkte: {}".format(n))
        ausgabe+= "updates:\n{};{}\n".format('id','price')
        i=0
        for c in toUpdate:
            i+=1
            print("updating {} of {}".format(i,n))
            self.env['product.product'].search([('id','=',c['id'])]).update({'standard_price':c['standard_price'],'purchase_ok':True})
            ausgabe+= "{};{}\n".format(c['id'],c['standard_price'])
        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'updated kaufmann prices.csv' # Name und Format des Downloads
