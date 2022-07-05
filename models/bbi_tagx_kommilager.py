from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #einmalige übernahme der Kommilager aus der parseLagerliste
    # für jedes komilager eine geschlossen MO für Bestände
    # und eine offene MO für noch nicht gedeckte bedarfe
    def parseKommilager(self):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        sheet = book.sheets()[1]

        # hier später eine schleife über alle sheets ab 1

        scancodeSetsGenerated=[]
        created = []
        for k in range(book.nsheets):
            if k < 1:
                continue
            sheet = book.sheets()[k]
            datasetsBedarf = [] # wird ein array mit den anzuhängenden dictionaries
            datasetsBestand = [] # wird ein array mit den anzuhängenden dictionaries
            for i in range(sheet.nrows):
                if i < 1:
                    continue
                if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                    rowCode = str(sheet.cell(i, 0).value).replace('\n','')
                else:
                    rowCode = str(int(sheet.cell(i, 0).value))

                result = self.env['product.product'].search([('default_code', '=', rowCode)]) # product_template id.ermitteln
                if len(result) == 0:
                    #nicht gefundene Produkte erzeugen und später als csv zurückgeben
                    result = self.env['product.product'].create({
                        'name': str(sheet.cell(i, 1).value),
                        'default_code' : rowCode,
                        'bbiDrawingNb' : str(sheet.cell(i, 2).value),
                        'detailed_type': "product",
                        'type': "product",
                    })
                    scancodeSetsGenerated.append({'origin' : 'Scancode: {} in {} Zeile {} nicht gefunden'.format(rowCode,sheet.name, i+1),'scancode' : rowCode});
                    #raise ValidationError('Scancode: {} in Zeile {} nicht gefunden'.format(rowCode, i+1))

                if (result[0].product_tmpl_id.type == 'product') and ( result[0].product_tmpl_id.detailed_type == 'product') : # nur zählbare erfassen
                    if isinstance(sheet.cell(i, 6).value, str):
                        bestand = 0
                    else:
                        bestand = int(sheet.cell(i, 6).value)

                    if isinstance(sheet.cell(i, 7).value, str):
                        bedarf = 0
                    else:
                        bedarf = int(sheet.cell(i, 7).value)
                    #to do Los ID
                    if (bedarf - bestand) > 0:
                        datasetsBedarf.append({
                            'product_id': result[0].id,
                            'product_uom_id': result[0].uom_id.id,
                            'product_uom_qty': bedarf - bestand,
                        })
                        print('offene Projekt bom -- {}  -- product_product: {} mit bestand {} und bedarf {} aufgenommen'.format(sheet.name,result[0],bestand,bedarf))
                    if bestand > 0:
                        datasetsBestand.append({
                            'product_id': result[0].id,
                            'product_uom_qty': bestand,
                            'product_uom_id': result[0].uom_id.id,
                        })
                        print('abgeschlossen Projekt bom -- {}  -- product_product: {} mit bestand {} und bedarf {} aufgenommen'.format(sheet.name,result[0],bestand,bedarf))
            if len(datasetsBedarf) > 0:
                #hilfsproduct für MO Bestand
                newProduct = self.env['product.product'].create({
                    'name': "{} TagX Hilfsprodukt für Bedarf aus Terminal".format(sheet.name),
                    'detailed_type': "product",
                    'type': "product",
                    'purchase_ok': False,
                    'active': False,
                })

                #Kopfdaten MO Bestand
                newProduction = self.env['mrp.production'].create({
                    'origin': "{} TagX Terminal Bedarfe".format(sheet.name),
                    'product_id': newProduct.id,
                    'product_uom_id': newProduct.uom_id.id,
                    'product_qty' : 1,
                    'qty_producing' : 1,
                    'product_uom_qty' : 1,
                })
                #created.append(newProduction)
                #move to stock
                self.env['stock.move'].create({
                    'name': newProduction.name,
                    'origin': newProduction.name,
                    'reference': newProduction.name,
                    'product_id': newProduct.id,
                    'production_id': newProduction.id,
                    'product_uom': newProduct.uom_id.id,
                    'product_uom_qty' : 1,
                    'location_id': 15,
                    'location_dest_id': 8,
                    'warehouse_id': 1,
                    'sequence' : 10,
                })

                #move from stock to production
                for d in datasetsBedarf:
                    self.env['stock.move'].create({
                        'name': newProduct.name,
                        'origin': newProduct.name,
                        'reference': newProduction.name,
                        'product_id': d['product_id'],
                        'raw_material_production_id': newProduction.id,
                        'product_uom': d['product_uom_id'],
                        'product_uom_qty' : d['product_uom_qty'],
                        'location_id': 8,
                        'location_dest_id': 15,
                        'warehouse_id': 1,
                        'sequence' : 1,
                    })

                newProduction.action_confirm()

            #ab hier MO für bestand
            if len(datasetsBestand) > 0 :
                #hilfsproduct für MO Bestand
                newProduct = self.env['product.product'].create({
                    'name': "{} TagX Hilfsprodukt für Bestand aus Terminal".format(sheet.name),
                    'detailed_type': "product",
                    'type': "product",
                    'purchase_ok': False,
                    'active': False,
                })

                #Kopfdaten MO Bestand
                newProduction = self.env['mrp.production'].create({
                    'origin': "{} TagX Terminal Bestände".format(sheet.name),
                    'product_id': newProduct.id,
                    'product_uom_id': newProduct.uom_id.id,
                    'product_qty' : 1,
                    'qty_producing' : 1,
                    'product_uom_qty' : 1,
                })
                #created.append(newProduction)
                #move to stock
                self.env['stock.move'].create({
                    'name': newProduction.name,
                    'origin': newProduction.name,
                    'reference': newProduction.name,
                    'product_id': newProduct.id,
                    'production_id': newProduction.id,
                    'product_uom': newProduct.uom_id.id,
                    'product_uom_qty' : 1,
                    'location_id': 15,
                    'location_dest_id': 8,
                    'warehouse_id': 1,
                    'sequence' : 10,
                })

                #move from stock to production
                moves = []
                for d in datasetsBestand:
                    move = self.env['stock.move'].create({
                        'name': newProduct.name,
                        'origin': newProduct.name,
                        'reference': newProduction.name,
                        'product_id': d['product_id'],
                        'raw_material_production_id': newProduction.id,
                        'product_uom': d['product_uom_id'],
                        'product_uom_qty' : d['product_uom_qty'],
                        'location_id': 8,
                        'location_dest_id': 15,
                        'warehouse_id': 1,
                        'sequence' : 1,
                    })
                    moves.append(move)

                newProduction.action_confirm()

                # jetzt noch move lines zum bestätigen vorbereiten

                #move_lines from stock to production, erledigt menge eintragen
                for d in moves:
                    self.env['stock.move.line'].create({
                        'move_id' : d.id,
                        'product_id': d.product_id.id,
                        'product_uom_id': d.product_uom.id,
                        'qty_done' : d.product_uom_qty,
                        'location_id' : 8,
                        'location_dest_id' : 15,
                        'state' : 'confirmed',
                        'reference': d.reference,
                    })

                newProduction.button_mark_done()
                #das versucht zu reservieren, und schmeißt unter unständen fehler wenn schon irgendwo anders reserviert
                # zum entfernen von reservierungen werden kollidierende stock_move_lines vn andren productions entfernt

        if len(scancodeSetsGenerated) > 0 :
            ausgabe = ''
            for d in scancodeSetsGenerated:
                ausgabe+= "{};{}\n".format(d['scancode'],d['origin'])
            raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
            self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
            self.myFile_file_name = 'products_generated.csv' # Name und Format des Downloads
