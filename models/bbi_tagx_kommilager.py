from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #einmalige übernahme der Kommilager aus der Lagerliste
    # für jedes komilager eine geschlossen MO für Bestände
    # und eine offene MO für noch nicht gedeckte bedarfe
    def parseKommilager(self):
        self.parseKommilagerInternal(False)

    def generateKommilager(self):
        self.parseKommilagerInternal(True)


    def compMORef(self,p,rowCode):
        if not p.default_code: return False
        if rowCode.lower() == str(p.default_code).lower(): return True
        return False

    def parseKommilagerInternal(self,generate):
        try:
            raw = base64.decodestring(self.myFile) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        notFound = []
        toCreate = []
        rotePunkteOdoo = []

        #behandlungsversuch unreserve bug
        #reserved = self.env['stock.move.line'].search([('product_qty','>',0)])
        #for r in reserved:
        #    print("unreserve: {}".format(r))
        #    r.sudo().update({
        #        'product_uom_qty' : 0,
        #        'product_qty' : 0,
        #    })
        #GELÖST: durch löschen aller stock_move_lines mit qty_done == 0


        for k in range(book.nsheets):
            if k < 1:   #erstes blatt nicht anfassen
                continue
            sheet = book.sheets()[k]
            if sheet.name in ('1229','1230','1232','1233','1234','1235','1900','1905','1906','1783','ohne Projekt','Muster','Schwund'):
                print("skipping {}".format(sheet.name))
                continue

            datasetsBedarf = [] # wird ein array mit den anzuhängenden dictionaries
            datasetsBestand = [] # wird ein array mit den anzuhängenden dictionaries
            for i in range(sheet.nrows):
                if i < 1:
                    continue
                if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                    rowCode = str(sheet.cell(i, 0).value).replace('\n','')
                else:
                    rowCode = str(int(sheet.cell(i, 0).value))

                result = self.env['product.product'].search([]).filtered(lambda p: self.compMORef(p,rowCode)) # product_template id.ermitteln
                if len(result) == 0:
                    #nicht gefundene Produkte erzeugen und später als csv zurückgeben
                    notFound.append({
                        'name': str(sheet.cell(i, 1).value),
                        'default_code' : rowCode,
                        'bbiDrawingNb' : str(sheet.cell(i, 2).value),
                        'sheetName' : sheet.name
                    })
                    print('kein treffer bom -- {}  -- code: {} -- name: {}'.format(sheet.name,rowCode,str(sheet.cell(i, 1).value)))
                else:
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
                            toCreate.append({
                                'projekt': sheet.name,
                                'type': 'Bedarf',
                                'count': bedarf - bestand,
                                'default_code' : rowCode,
                            })
                        if bestand > 0:
                            datasetsBestand.append({
                                'product_id': result[0].id,
                                'product_uom_qty': bestand,
                                'product_uom_id': result[0].uom_id.id,
                                'default_code' : rowCode,
                            })
                            print('abgeschlossen Projekt bom -- {}  -- product_product: {} mit bestand {} und bedarf {} aufgenommen'.format(sheet.name,result[0],bestand,bedarf))
                            toCreate.append({
                                'projekt': sheet.name,
                                'type': 'Bestand',
                                'count': bestand,
                                'default_code' : rowCode,
                            })
                    else: #roter rotePunkt
                        rotePunkteOdoo.append({
                            'name': str(sheet.cell(i, 1).value),
                            'default_code' : rowCode,
                            'bbiDrawingNb' : str(sheet.cell(i, 2).value),
                            'sheetName' : sheet.name
                        })
            #ende for über alle zeilen im blatt
            if (len(datasetsBedarf) > 0) and (generate == True):
                print("generating bom bedarf {}".format(sheet.name))
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
                    print("generating part bedarf {} --  id {}".format(sheet.name,d['product_id']))
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
            if (len(datasetsBestand) > 0) and (generate == True) :
                print("generating bom bestand {}".format(sheet.name))
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
                    print("generating part bestand {} --  id {}".format(sheet.name,d['product_id']))
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
                #GELÖST: durch löschen aller stock_move_lines mit qty_done == 0



            #ende der scripte zur erzeugung der MO
        #ende for über alle sheets
        ausgabe = 'Projekt;Typ;Anzahl;code\nto create:\n'
        #toCreate.append({
        #    'projekt': sheet.name,
        #    'type': 'Bestand',
        #    'count': bestand,
        #    'default_code' : rowCode,
        #})
        if len(toCreate) > 0 :
            for d in toCreate:
                ausgabe+= "{};{};{};{}\n".format(d['projekt'],d['type'],d['count'],d['default_code'])
        #notFound.append({
        #    'name': str(sheet.cell(i, 1).value),
        #    'default_code' : rowCode,
        #    'bbiDrawingNb' : str(sheet.cell(i, 2).value),
        #    'sheetName' : sheet.name
        #})
        if len(notFound) > 0 :
            ausgabe += '!!! NOT FOUND:\n'
            for d in notFound:
                ausgabe+= "{};{};{};{}\n".format(d['sheetName'],'na','na',d['default_code'])
        #rotePunkteOdoo.append({
        #    'name': str(sheet.cell(i, 1).value),
        #    'default_code' : rowCode,
        #    'bbiDrawingNb' : str(sheet.cell(i, 2).value),
        #    'sheetName' : sheet.name
        #})
        if len(rotePunkteOdoo) > 0 :
            ausgabe += '!!! nicht übernommen wegen Verbrauchsartikel im odoo:\n'
            for d in rotePunkteOdoo:
                ausgabe+= "{};{};{};{}\n".format(d['sheetName'],'na','na',d['default_code'])

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'products_checked_or_generated_for MO.csv' # Name und Format des Downloads
