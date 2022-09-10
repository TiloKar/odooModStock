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

    def parseBackupInventory(self):
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
        #stumpfe übernahme ohne 1905 betrachtung
        handledLots = [] #hier noch die bearbeiteten und übersprungen lose sammeln und zum schluss abgleichen!
        handledProducts = []
        sheet = book.sheets()[0]
        ausgabe = 'product_id;code;name;Anzahl\nhandled products:\n'
        for i in range(sheet.nrows):
            print('handling row {} from {}'.format(i+1,sheet.nrows))
            if i < 1:
                continue
            pId = int(sheet.cell(i, 0).value)
            result = self.env['product.product'].search([('id','=',pId)])
            if len(result) != 1:
                #nicht gefundene oder mehrfachtreffer Produkte erzeugen und später als csv zurückgeben
                notFound.append({
                    'id' : pId,
                })
                print('kein product_id treffer')
            else:
                p=result[0]
                pName=p.name.replace(';','|').replace('\n','|')
                if (p.product_tmpl_id.type == 'product') and ( p.product_tmpl_id.detailed_type == 'product') : # nur zählbare erfassen
                    handledProducts.append(p.id)
                    if (sheet.cell(i, 3).value):
                        lotId = sheet.cell(i, 3).value
                    else:
                        lotId = False
                    print('lot id: {}'.format(lotId))
                    if (sheet.cell(i, 4).value):
                        lotName = str(sheet.cell(i, 4).value).replace('###','')
                    else:
                        lotName = False
                    print('lot name: {}'.format(lotName))
                    toSet = float(sheet.cell(i, 6).value)
                    print('toSet: {}'.format(toSet))
                    if (lotId == False) or (lotId == ''): #no tracking
                        if p.tracking == 'lot' : raise ValidationError('no lotname given for tracked product in row {}'.format(i+1))
                        if p.with_context({'location' : 8}).qty_available != toSet:
                            quant=self.env['stock.quant'].search([('product_id','=',p.id),('location_id','=',8)])
                            if len(quant) == 0:
                                print('make new quant for untracked correction')
                                ausgabe+= "{};{};{};{};new quant, untracked\n".format(p.id,p.default_code,pName,toSet)
                                #todo new quant correction
                                newQuant = self.env['stock.quant'].create({
                                    'product_id': p.id,
                                    'location_id': 8,
                                    'inventory_quantity': toSet,
                                })
                                newQuant.action_apply_inventory()
                            else:
                                print('using existing quant for untracked correction')
                                ausgabe+= "{};{};{};{};existing quant, untracked\n".format(p.id,p.default_code,pName,toSet)
                                #todo use existing quant correction
                                quant[0].update({
                                    'inventory_quantity': toSet,
                                    'inventory_diff_quantity' : toSet - quant[0].quantity,
                                })
                                quant[0].action_apply_inventory()
                        else:
                            print('skippend untracked with no changes in qty')
                            ausgabe+= "{};{};{};{};skipped quant, untracked\n".format(p.id,p.default_code,pName,toSet)
                    elif lotId == 'not given':
                        lot = self.env['stock.production.lot'].search([('product_id','=',p.id)])
                        if len(lot) != 0: raise ValidationError('lot id found, but marked as not given in row {}'.format(i+1))
                        if (lotName == False) or (lotName == ''): lotName = 'untraced'
                        print('make new quant and lot for not given lotname')
                        ausgabe+= "{};{};{};{};new lot, untraced\n".format(p.id,p.default_code,pName,toSet)
                        #todo neu erstellen los und quant mit losname 'untraced', falls in lotName nicht vergeben
                        newLot = self.env['stock.production.lot'].create({
                            'product_id': p.id,
                            'name': lotName,
                            'company_id':1,
                        })
                        newQuant = self.env['stock.quant'].create({
                            'product_id': p.id,
                            'location_id': 8,
                            'inventory_quantity': toSet,
                            'lot_id': newLot.id,
                        })
                        newQuant.action_apply_inventory()
                    else: #losnummer ist vergeben
                        lotId = int(lotId)
                        lot = self.env['stock.production.lot'].search([('id','=',lotId)])
                        if len(lot) == 0: raise ValidationError('lot id not found in row {}'.format(i+1))
                        handledLots.append(lot.id)
                        if p.id != lot.product_id.id: raise ValidationError('lot product_id missmatch in row {}'.format(i+1))
                        if lotName != lot.name: raise ValidationError('lot name missmatch in row {} {} != {}'.format(i+1,lotName,lot.name))
                        if lot.product_qty != toSet:
                            quant=self.env['stock.quant'].search([('lot_id','=',lotId),('location_id','=',8)])
                            if len(quant) == 0: raise ValidationError('quant not found for existing lot_id in row {}'.format(i+1))
                            #todo quant correction for existing quant with lot
                            quant[0].update({
                                'inventory_quantity': toSet,
                                'inventory_diff_quantity' : toSet - quant[0].quantity,
                            })
                            quant[0].action_apply_inventory()
                            print('use existing lot for correction')
                            ausgabe+= "{};{};{};{};using existing lot\n".format(p.id,p.default_code,pName,toSet)
                        else:
                            print('skippend tracked with no changes in qty')
                            ausgabe+= "{};{};{};{};skipped existing lot\n".format(p.id,p.default_code,pName,toSet)

                else: #roter rotePunkt
                    rotePunkteOdoo.append({
                        'id': pId,
                    })
                    print('Verbrauchsartikel')

        #ende for über alle zeilen im blatt lagerliste

        lots = self.env['stock.production.lot'].search([])
        ausgabe+= "unhandled lot ids\n"
        for lot in lots:
            if lot.id not in handledLots:
                ausgabe+= "{};{}\n".format(lot.product_id.id,lot.product_id.default_code)

        products = self.env['product.product'].search([('type','=','product')])
        ausgabe+= "unhandled product_ids\n"
        for p in products:
            if p.id not in handledProducts:
                ausgabe+= "{};{}\n".format(p.id,p.default_code)
        if len(notFound) > 0 :
            ausgabe += '!!! NOT FOUND:\n'
            for d in notFound:
                ausgabe+= "{}\n".format(d['id'])
        if len(rotePunkteOdoo) > 0 :
            ausgabe += '!!! nicht übernommen wegen Verbrauchsartikel im odoo:\n'
            for d in rotePunkteOdoo:
                ausgabe+= "{}\n".format(d['id'])

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'report corrected quantities from external inventory file.csv' # Name und Format des Downloads
