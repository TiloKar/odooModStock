from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #Comperator für kaufmann Artikel Vergleich
    def compKaufmannCheck(self,pIt,p):
        if pIt['default_code'] == False: return False
        if pIt['default_code'].lower() == p['default_code'].lower(): return True
        return False

    #übernahme aus kaufmann export
    def parseKaufmannProducts(self):
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

            if sheet.cell(i, 70).value == '':
                price = 0
            else:
                price = float(sheet.cell(i, 70).value)

            name = str(sheet.cell(i, 5).value).replace('\n','')
            name.replace(';',' | ')
            draw = str(sheet.cell(i, 8).value).replace('\n','')
            draw.replace(';',' | ')
            desc = str(sheet.cell(i, 7).value).replace('\n','')
            desc.replace(';',' | ')

            kaufmann.append({
                'name': name,
                'default_code' : rowCode,
                'bbiDrawingNb' : draw,
                'detailed_type': "product",
                'type': "product",
                'description': desc,
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
        toCreate = []
        toUpdate = []
        for p in kaufmann:
            i+=1
            result = list(filter(lambda pIt: self.compKaufmannCheck(pIt,p),candidatesOdoo)) # product_template id.ermitteln
            if len(result) == 0:
                #nicht gefundene Produkte für erzeugung aufnehmen und später als csv zurückgeben
                toCreate.append({
                    'name': p['name'],
                    'default_code' : p['default_code'],
                    'bbiDrawingNb' : p['bbiDrawingNb'],
                    'detailed_type': "product",
                    'type': "product",
                    'description': p['description'],
                    'standard_price': p['standard_price']
                })
                print("verarbeite kaufmann zeile: {} für create aufgenommen".format(i))
            else:
                toUpdate.append({
                    'id': result[0]['id'],
                    'standard_price': p['standard_price']
                })
                candidatesOdoo.remove({ #damit für alle folgenden iterationen die suchkandidaten kleiner werden
                    'id' : result[0]['id'],
                    'default_code' : result[0]['default_code'],
                })
                print("verarbeite kaufmann zeile: {} für update aufgenommen".format(i))

        ausgabe = ''
        print("zu erzeugende produkte: {}".format(len(toCreate)))
        ausgabe+= "{};{};{};{};{};{}\n".format('name','default_code','bbiDrawingNb','detailed_type','type','description')
        for c in toCreate:
            self.env['product.product'].create(c)
            ausgabe+= "{};{};{};{};{};{}\n".format(c['name'],c['default_code'],c['bbiDrawingNb'],c['detailed_type'],c['type'],c['description'])
        print("zum update markierte produkte: {}".format(len(toUpdate)))
        ausgabe+= "updates:\n{};{}\n".format('id','default_code')
        for c in toUpdate:
            self.env['product.product'].search([('id','=',c['id'])]).update({'standard_price':c['standard_price']})
            ausgabe+= "{};{}\n".format(c['id'],c['standard_price'])
        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'generated kaufmann products.csv' # Name und Format des Downloads
