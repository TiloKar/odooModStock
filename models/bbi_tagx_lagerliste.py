from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #einmalige übernahme aus der lagerliste und einstellen der quantities

    def parseLagerListe(self):
        self.parseLagerListeInternal(False)

    def generateLagerListe(self):
        self.parseLagerListeInternal(True)

    def compQuantsMO(self,m,p):
        if p.id != m.product_id.id: return False #id muss gleich sein
        if m.location_dest_id.id != 15: return False #muss in production aufgehen
        if m.state != 'done': return False #muss abgeschlossen sein
        return True


    def compQuantsRef(self,p,rowCode):
        if not p.default_code: return False
        if rowCode.lower() == str(p.default_code).lower(): return True
        return False

    def parseLagerListeInternal(self,generate):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        notFound = []
        rotePunkteOdoo = []
        datasetsBestand1905 = [] # wird ein array mit den anzuhängenden dictionaries

        for k in range(book.nsheets):
            sheet = book.sheets()[k]
            if sheet.name == '1905': break

        for i in range(sheet.nrows):
            if i < 1:
                continue
            if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                rowCode = str(sheet.cell(i, 0).value).replace('\n','')
            else:
                rowCode = str(int(sheet.cell(i, 0).value))

            result = self.env['product.product'].search([]).filtered(lambda p: self.compQuantsRef(p,rowCode)) # product_template id.ermitteln
            if len(result) == 0:
                #nicht gefundene Produkte erzeugen und später als csv zurückgeben
                notFound.append({
                    'name': str(sheet.cell(i, 1).value),
                    'default_code' : rowCode,
                })
                print('{} in 1905 nicht gefunden -- code: {}'.format(i+1,rowCode))
            else:
                if (result[0].product_tmpl_id.type == 'product') and ( result[0].product_tmpl_id.detailed_type == 'product') : # nur zählbare erfassen
                    if isinstance(sheet.cell(i, 6).value, str):
                        verbrauch = 0
                    else:
                        verbrauch = float(sheet.cell(i, 6).value)

                    allLines = self.env['stock.move.line'].search([]).filtered(lambda m: self.compQuantsMO(m,result[0]))
                    summeOdoo = sum(allLines.mapped('qty_done'))

                    datasetsBestand1905.append({
                        'product_id': result[0].id,
                        'name': result[0].name,
                        'verbrauch1905': verbrauch,
                        'verbrauchOdoo': summeOdoo,
                        'product_uom_id': result[0].uom_id.id,
                        'default_code' : rowCode,
                    })
                    print('{} in 1905 , product: {} mit bestand1905: {} und bestandOdoo: {} aufgenommen'.format(i+1,rowCode,verbrauch,summeOdoo))
                    #if summeOdoo > 0: break # debug
                else: #roter rotePunkt
                    rotePunkteOdoo.append({
                        'name': str(sheet.cell(i, 1).value),
                        'default_code' : rowCode,
                    })
                    print('{} in 1905 Verbrauchsartikel -- code: {} -- name: {}'.format(i+1,rowCode,str(sheet.cell(i, 1).value)))


        # debug abbruch
        #ausgabe = 'id;name;code;1905;odoo\n'
        #if len(datasetsBestand1905) > 0 :
        #    for d in datasetsBestand1905:
        #        ausgabe+= "{};{};{};{};{}\n".format(d['product_id'],d['name'].replace(';','|'),d['default_code'],d['verbrauch1905'],d['verbrauchOdoo'])

        #raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        #self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        #self.myFile_file_name = 'products_checked_or_generated_for quants.csv' # Name und Format des Downloads
        #return

        #ende for 1905

        datasetsBestand = [] # wird ein array mit den anzuhängenden dictionaries
        sheet = book.sheets()[0]

        for i in range(sheet.nrows):
            if i < 1:
                continue
            if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                rowCode = str(sheet.cell(i, 0).value).replace('\n','')
            else:
                rowCode = str(int(sheet.cell(i, 0).value))

            result = self.env['product.product'].search([]).filtered(lambda p: self.compQuantsRef(p,rowCode)) # product_template id.ermitteln
            if len(result) == 0:
                #nicht gefundene Produkte erzeugen und später als csv zurückgeben
                notFound.append({
                    'name': str(sheet.cell(i, 1).value),
                    'default_code' : rowCode,
                })
                print('{} kein treffer -- code: {} -- name: {}'.format(i+1,rowCode,str(sheet.cell(i, 1).value)))
            else:
                if (result[0].product_tmpl_id.type == 'product') and ( result[0].product_tmpl_id.detailed_type == 'product') : # nur zählbare erfassen
                    if isinstance(sheet.cell(i, 8).value, str):
                        bestand = 0
                    else:
                        bestand = float(sheet.cell(i, 8).value)

                    vals = {'product_id': result[0].id,
                        'name': result[0].name,
                        'product_uom_qty': bestand,
                        'product_uom_id': result[0].uom_id.id,
                        'default_code' : rowCode}


                    #schauene ob es zusätzliche menge in 1105 gibt, dann differenz in richtung 1905 dazu packen
                    res1905 = list(filter(lambda d: d['product_id'] == result[0].id,datasetsBestand1905))
                    if (len(res1905) > 0):
                        vals['verbrauch1905'] = res1905[0]['verbrauch1905']
                        vals['verbrauchOdoo'] = res1905[0]['verbrauchOdoo']

                    datasetsBestand.append(vals)
                
                    print('{} in Lagerliste product: {} mit bestand {} aufgenommen'.format(i+1,result[0].default_code,bestand))

                else: #roter rotePunkt
                    rotePunkteOdoo.append({
                        'name': str(sheet.cell(i, 1).value),
                        'default_code' : rowCode,
                    })
                    print('{} in Lagerliste Verbrauchsartikel -- code: {} -- name: {}'.format(i+1,rowCode,str(sheet.cell(i, 1).value)))

        #ende for über alle zeilen im blatt lagerliste

        #ab hier MO für bestand
        if (len(datasetsBestand) > 0) and (generate == True) :
            print("generating quant {}".format(sheet.name))
            for d in datasetsBestand:
                dif = 0
                toSet = d['product_uom_qty']
                if d['verbrauch1905']:
                    dif = d['verbrauch1905'] - d['verbrauchOdoo']
                if dif > 0:
                    toSet = dif + d['product_uom_qty']

                thisProduct = self.env['product.product'].search([('id','=',d['product_id'])])
                thisProduct._compute_quantities()
                ist = thisProduct.qty_available

                newQuant = self.env['stock.quant'].create({
                    'product_id': d['product_id'],
                    'location_id': 9,
                    'inventory_quantity': toSet,
                #    'type': "product",
                #    'purchase_ok': False,
                #    'active': False,
                })
                newQuant.action_apply_inventory()

            #newProduction.action_confirm()

            #newProduction.button_mark_done()

        ausgabe = 'Anzahl;code;name;Anzahl 1905;Anzahl Odoo MO;\nto create:\n'
        #    datasetsBestand.append({
        #        'product_id': result[0].id,
        #        'name': result[0].name,
        #        'product_uom_qty': bestand,
        #        'product_uom_id': result[0].uom_id.id,
        #        'default_code' : rowCode,
        #                        vals['verbrauch1905'] = result[0]['verbrauch1905']
        #                        vals['verbrauchOdoo'] = result[0]['verbrauchOdoo']
        #    })
        if len(datasetsBestand) > 0 :
            for d in datasetsBestand:
                dif = 0
                if d['verbrauch1905']:
                    dif = d['verbrauch1905'] - d['verbrauchOdoo']
                if dif > 0:
                    ausgabe+= "{};{};{};{};{}\n".format(dif + d['product_uom_qty'],d['default_code'],d['name'],d['verbrauch1905'],d['verbrauchOdoo'])
                else:
                    ausgabe+= "{};{};{}\n".format(d['product_uom_qty'],d['default_code'],d['name'])
        #notFound.append({
        #    'name': str(sheet.cell(i, 1).value),
        #    'default_code' : rowCode,
        #    'bbiDrawingNb' : str(sheet.cell(i, 2).value),
        #})
        if len(notFound) > 0 :
            ausgabe += '!!! NOT FOUND:\n'
            for d in notFound:
                ausgabe+= "{};{};{}\n".format('na',d['default_code'],d['name'])
        #rotePunkteOdoo.append({
        #    'name': str(sheet.cell(i, 1).value),
        #    'default_code' : rowCode,
        #    'bbiDrawingNb' : str(sheet.cell(i, 2).value),
        #})
        if len(rotePunkteOdoo) > 0 :
            ausgabe += '!!! nicht übernommen wegen Verbrauchsartikel im odoo:\n'
            for d in rotePunkteOdoo:
                ausgabe+= "{};{};{}\n".format('na',d['default_code'],d['name'])

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'products_checked_or_generated_for quants.csv' # Name und Format des Downloads
