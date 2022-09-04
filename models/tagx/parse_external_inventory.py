from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #übernahme aus excel liste zur inventur und automatisches generieren der quants
    #noch nie korrigierte haben keinen eintrag in stock quant unter der product_id und loaction_id 8
    #für diese stock.quant anlegen und dananch quant.action_apply_inventory()

    #für bereits korrigierte gibt es einen quant mit product_id und loaction = 8
    #auf bisher unbestimmte weise aktualisiert sich quantity an quants bei änderungen in den stock moves von selbst
    #mit inventory_quatity_set = true die zählung auf NICHT angewendet setzen
    #bei inventory_quantity zielwert raufschreiben und bei inventory_diff_quantity=neu - quantity und dann quant.action_apply_inventory()

    def moveLineIsIn(self,m):
        if not m.picking_id: return False
        if 'WH/IN' in m.picking_id.name: return True
        return False

    def compQuantsInv(self,p,rowCode):
        if not p.default_code: return False
        if rowCode.lower() == str(p.default_code).lower(): return True
        return False

    def getExtInventoryReport(self):
        #parsen der liste und rückgabe welche teile davon seit checkDate in wh/stock eingeflogen sind
        self.parseExtInventory(False)

    def setExtInventory(self):
        #parsen der liste und rückgabe welche teile davon seit checkDate in wh/stock eingeflogen sind
        self.parseExtInventory(True)

    def parseExtInventory(self,makeCorrection):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        if book.nsheets < 2: raise ValidationError('Datei Fehler!')
        notFound = []
        rotePunkteOdoo = []
        #stumpfe übernahme ohne 1905 betrachtung
        productsToSet = [] # wird ein array mit den anzuhängenden dictionaries
        sheet = book.sheets()[1]

        for i in range(sheet.nrows):
            if i < 1:
                continue
            if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                rowCode = str(sheet.cell(i, 0).value).replace('\n','')
            else:
                rowCode = str(int(sheet.cell(i, 0).value))

            result = self.env['product.product'].search([]).filtered(lambda p: self.compQuantsInv(p,rowCode)) # product_template id.ermitteln
            if len(result) != 1:
                #nicht gefundene oder mehrfachtreffer Produkte erzeugen und später als csv zurückgeben
                notFound.append({
                    'name': str(sheet.cell(i, 1).value),
                    'default_code' : rowCode,
                })
                print('{} kein treffer -- code: {} -- name: {}'.format(i+1,rowCode,str(sheet.cell(i, 1).value)))
            else:
                if (result[0].product_tmpl_id.type == 'product') and ( result[0].product_tmpl_id.detailed_type == 'product') : # nur zählbare erfassen
                    if isinstance(sheet.cell(i, 6).value, str):
                        bestand = 0
                    else:
                        bestand = float(sheet.cell(i, 6).value)

                    vals = {'product_id': result[0].id,
                        'name': result[0].name,
                        'qty_to_set': bestand,
                        'product_uom_id': result[0].uom_id.id,
                        'default_code' : rowCode}

                    productsToSet.append(vals)

                    print('{} in Lagerliste product: {} mit bestand {} aufgenommen'.format(i+1,result[0].default_code,bestand))

                else: #roter rotePunkt
                    rotePunkteOdoo.append({
                        'name': str(sheet.cell(i, 1).value),
                        'default_code' : rowCode,
                    })
                    print('{} in Lagerliste Verbrauchsartikel -- code: {} -- name: {}'.format(i+1,rowCode,str(sheet.cell(i, 1).value)))

        #ende for über alle zeilen im blatt lagerliste

        i=0
        n=len(productsToSet)
        idsToSet = []
        productsInTracking = [] # wird ein array mit den produkten in chargen oder seriennummernverfolgung
        for p in productsToSet:
            i+=1
            print("checking quant {} from {}".format(i,n))
            product = self.env['product.product'].search([('id','=',p['product_id'])])
            toSet = p['qty_to_set']
            idsToSet.append(product.id)
            if product.tracking != 'none':
                productsInTracking.append({'product_id': product.id,
                    'name': product.name,
                    'qty_to_set': toSet,
                    'product_uom_id': product.uom_id.id,
                    'default_code' : product.default_code
                })
            elif (makeCorrection == True): #nur produkte ohne serien/chargenverfolgung behandeln
                quant = self.env['stock.quant'].search([('product_id','=',product.id),('location_id','=',8)])
                if len(quant) == 1:
                    print('schon da {}'.format(product.default_code))
                    #bei inventory_quantity zielwert raufschreiben und bei inventory_diff_quantity=neu - quantity und dann quant.action_apply_inventory()
                    quant.update({
                        'inventory_quantity': toSet,
                        'inventory_diff_quantity' : toSet - quant.quantity,
                    })
                    quant.action_apply_inventory()
                else:
                    print('update {}'.format(product.default_code))
                    newQuant = self.env['stock.quant'].create({
                        'product_id': product.id,
                        'location_id': 8,
                        'inventory_quantity': toSet,
                    })
                    newQuant.action_apply_inventory()

        #hier noch prüfen, ob dazu wareneingänge existieren
        moveLines = self.env['stock.move.line'].search([('location_dest_id','=',8),('state','=','done'),('product_id','in',idsToSet)]).filtered(lambda m: self.moveLineIsIn(m))

        ausgabe = 'Anzahl;code;name\nto create:\n'
        if len(productsToSet) > 0 :
            for d in productsToSet:
                ausgabe+= "{};{};{}\n".format(d['qty_to_set'],d['default_code'],d['name'].replace(';','|'))
        if len(notFound) > 0 :
            ausgabe += '!!! NOT FOUND:\n'
            for d in notFound:
                ausgabe+= "{};{};{}\n".format('na',d['default_code'],d['name'].replace(';','|'))
        if len(rotePunkteOdoo) > 0 :
            ausgabe += '!!! nicht übernommen wegen Verbrauchsartikel im odoo:\n'
            for d in rotePunkteOdoo:
                ausgabe+= "{};{};{}\n".format('na',d['default_code'],d['name'].replace(';','|'))
        if len(productsInTracking) > 0 :
            ausgabe += '!!! nicht übernommen wegen Tracking im odoo:\n'
            for d in productsInTracking:
                ausgabe+= "{};{};{}\n".format('na',d['default_code'],d['name'].replace(';','|'))
        if (moveLines):
            ausgabe += '!!! wareneingänge:\n'
            for d in moveLines:
                ausgabe+= "{};{};{}\n".format('na',d.product_id.default_code,d.product_id.name.replace(';','|'))

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'products_checked_or_generated_for quants.csv' # Name und Format des Downloads
