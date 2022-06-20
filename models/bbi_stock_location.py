from odoo import api, fields, models
import csv, base64, sys, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _name = "bbi.stock.location"
    _description = "Eigene Lagerorte als Attribute an product_template"

    name = fields.Char(store = True, required = True , string = 'Eindeutige Lagerort Bezeichnung')

    myFile = fields.Binary(string='Terminal Datenbank für Übernahme an Tag X')

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
                raise ValidationError('Scancode: {} in Zeile {} nicht gefunden'.format(rowCode, i+1))

            if result[0].product_tmpl_id.type == 'product':
                if isinstance(sheet.cell(i, 6).value, str):
                    bestand = 0
                else:
                    bestand = int(sheet.cell(i, 6).value)

                if isinstance(sheet.cell(i, 7).value, str):
                    bedarf = 0
                else:
                    bedarf = int(sheet.cell(i, 7).value)
                print('abgeschlossen Projekt bom -- {}  -- product_product: {} mit bestand {} und bedarf {} aufgenommen'.format(sheet.name,result[0],bestand,bedarf))
                #to do Los ID
                if (bedarf - bestand) > 0:
                    datasetsBedarf.append({
                        'product_id': result[0].id,
                        'product_uom_id': result[0].uom_id.id,
                        'product_uom_qty': bedarf - bestand,
                    })
                elif bestand > 0:
                    datasetsBestand.append({
                        'product_id': result[0].id,
                        'product_uom_qty': bestand,
                        'product_uom_id': result[0].uom_id.id,
                    })

        #hilfsproduct für MO
        newProduct = self.env['product.product'].create({
            'name': "Projekt-{}-Hilfsprodukt".format(sheet.name),
            'detailed_type': "product",
            'type': "product",
            'purchase_ok': False,
            'active': False,
        })

        #Kopfdaten
        prodName = "TagX-BOM-{}-offene Bedarfe".format(sheet.name)
        newProduction = self.env['mrp.production'].create({
            'name': prodName,
            'origin': "Terminal",
            'product_id': newProduct.id,
            'product_uom_id': newProduct.uom_id.id,
            'product_qty' : 1,
            'product_uom_qty' : 1,
        })
        #move to stock
        self.env['stock.move'].create({
            'name': prodName,
            'origin': prodName,
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
        sequence = 0
        for d in datasetsBedarf:
            sequence += 1
            #if sequence == 10 : sequence = 11
            self.env['stock.move'].create({
                'name': prodName,
                'origin': prodName,
                'product_id': d['product_id'],
                'raw_material_production_id': newProduction.id,
                'product_uom': d['product_uom_id'],
                'product_uom_qty' : d['product_uom_qty'],
                'location_id': 8,
                'location_dest_id': 15,
                'warehouse_id': 1,
            })
