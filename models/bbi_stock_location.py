from odoo import api, fields, models
import csv, base64, sys, xlrd, xlwt, datetime
from odoo.exceptions import ValidationError
from io import BytesIO, StringIO

class BbiStockLocation(models.Model):
    _name = "bbi.stock.location"
    _description = "Eigene Lagerorte als Attribute an product_template"

    name = fields.Char(store = True, required = True , string = 'Eindeutige Lagerort Bezeichnung')

    myFile = fields.Binary(string='Terminal Datenbank für Übernahme an Tag X')
    myFile_file_name = fields.Char(String='Name')

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

        datasetsBedarf = [] # wird ein array mit den anzuhängenden dictionaries
        datasetsBestand = [] # wird ein array mit den anzuhängenden dictionaries
        scancodeSetsError =[]
        for k in range(book.nsheets):
            if k < 1:
                continue
            sheet = book.sheets()[k]
            for i in range(sheet.nrows):
                if i < 1:
                    continue
                if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                    rowCode = str(sheet.cell(i, 0).value).replace('\n','')
                else:
                    rowCode = str(int(sheet.cell(i, 0).value))

                result = self.env['product.product'].search([('default_code', '=', rowCode)]) # product_template id.ermitteln
                if len(result) == 0:
                    scancodeSetsError.append({'origin' : 'Scancode: {} in {} Zeile {} nicht gefunden'.format(rowCode, i+1, sheet.name),'scancode' : rowCode});
                    #raise ValidationError('Scancode: {} in Zeile {} nicht gefunden'.format(rowCode, i+1))
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
        if len(scancodeSetsError) == 0 :
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
                'product_uom_qty' : 1,
            })
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
                    'name': newProduct,
                    'origin': newProduct,
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
        else:
            ausgabe = ''
            for d in scancodeSetsError:
                ausgabe+= "{};{}\n".format(d['scancode'],d['origin'])
            raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
            self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
            self.myFile_file_name = 'errors.csv' # Name und Format des Downloads


    #einmalige übernahme des wareneingangs buchs an TagX
    #nur offene etsellungen werden übernommen und auch nicht bestätigt,
    #Die Produktpositionen sollen beim Wareneingang manuell nachgetragen werden
    def parseWareneingangsbuch(self):
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
            vals = {}
            if i < 7:
                continue
            elif i > 10:
                break   #nur weil die jetzige liste da ne macke hat
            try:
                partnerName = str(sheet.cell(i, 10).value)

                if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                    partnerShippingNb = str(sheet.cell(i, 5).value).replace('\n','')
                else:
                    partnerShippingNb = str(sheet.cell(i, 5).value)
                #if partnerShippingNb == "":
                #    raise ValidationError('LS-Nr. nicht gefuden in Zeile {}'.format(i+1))

                if isinstance(sheet.cell(i, 0).value, str): #fallunterscheidung für als zahl interpretierte scancodes
                    partnerOrderNb = str(sheet.cell(i, 1).value).replace('\n','')
                else:
                    partnerOrderNb = str(sheet.cell(i, 1).value)
                if partnerOrderNb == "":
                    raise ValidationError('Bestllnr. nicht gefuden in Zeile {}'.format(i+1))
                vals['partner_ref'] = partnerOrderNb

                hlp = sheet.cell(i, 0).value
                orderApproveDate = datetime.datetime(*xlrd.xldate_as_tuple(hlp, book.datemode))
                vals['date_approve'] = orderApproveDate

                hlp = sheet.cell(i, 2).value
                datePlanned = datetime.datetime(*xlrd.xldate_as_tuple(hlp, book.datemode))
                vals['date_planned'] = datePlanned
            except:
                raise ValidationError('Daten-Fehler in Zeile {}'.format(i))

            partnerId = 213 #optional, falls Dummy-Zulieferer doch automatisch gesetzt werden soll, dann noch ID anpassen
            hit = self.env['res.partner'].search([('name', '=', partnerName)])
            if len(hit) > 0:
                partnerId = hit[0].id
                vals['partner_id'] = partnerId
            else:
                raise ValidationError('Partner {} nicht gefuden in Zeile {}'.format(partnerName,i+1))

        for po in datasets:
            created=self.env['purchase.order'].create(po)
            print(created)


        #for d in datasets:
        #    hit = self.env['stock.quant'].search([('product_id', '=', d['product_id']),('location_id', '=', d['location_id'])])
            #print(str(len(hit)))
            #if len(hit) > 0:
            #    hit[0].update(d)
            #else:
            #    self.env['stock.quant'].create(d)
