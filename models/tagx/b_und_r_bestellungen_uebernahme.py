from odoo import api, fields, models
import base64, xlrd, datetime
from datetime import date
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    # Excelimport
    def parseBRpo(self):
        try:
            raw = base64.decodestring(self.myFile)
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        sheet = book.sheets()[0]

        # Purchase Order Daten aus Exel ziehen und vorbereiten
        bestellung = []
        #product IDs und menge der Positionen nur einmal holen
        lastProductLine = 0
        productIds = []

        for row in range(sheet.nrows):
            if row < 3: continue
            lastProductLine += 1
            productStr=sheet.cell(row, 1).value
            print("suche produkt in zeile {} mit code {}".format(row,productStr))
            if (not isinstance(productStr, str)) or (productStr == ""): break
            product = self.env['product.product'].search([('default_code', '=', productStr)])
            if len(product) != 1:
                raise ValidationError("default code nicht lesbar: {}.".format(productStr))
            productIds.append(product.id)


        # Datum wird in die Exceldatei nachgetragen
        date_order = datetime.datetime(*xlrd.xldate_as_tuple(sheet.cell(2, 0).value, book.datemode))
        duplicate = []
        for coloum in range(sheet.ncols):
            ausExcel= {}
            if coloum > 2:
                print("Lese Purchase Order Kopfdaten von Spalte: {}".format(coloum))
                partnerRefStr=str(sheet.cell(34, coloum).value)

                #Aufnahe Duplikate partner referenz
                duplicate_partner_ref = self.env['purchase.order'].search([('partner_ref', '=', partnerRefStr)])
                if len(duplicate_partner_ref) != 0:
                    duplicate.append(partnerRefStr)
                ausExcel['index_col'] = coloum
                ausExcel['partner_ref'] = partnerRefStr
                ausExcel['partner_id'] = 15777 #Partner ID für B&R
                ausExcel['desired_date'] = datetime.datetime(*xlrd.xldate_as_tuple(sheet.cell(1, coloum).value, book.datemode))
                ausExcel['date_order'] = date_order
                #anzahl der produkte schon hier auslesen
                productQty = []
                for row in range(3,2 + lastProductLine):
                    print(sheet.cell(row, coloum).value)
                    productQty.append(int(sheet.cell(row, coloum).value))
                ausExcel['qty'] = productQty
                #print(productQty)

                bestellung.append(ausExcel)

        #Prüfung auf Duplikate
        if len(duplicate) != 0:
            raise ValidationError("Partner Ref Duplikate: {}.".format(duplicate))

        # Purchase Order Daten erstellen
        for crO in bestellung:
            print("Erstelle Purchase Order Kopfdaten: {}.".format(crO['partner_ref']))
            createdOrder=self.env['purchase.order'].create({
                'partner_ref' : crO['partner_ref'],
                'date_order' : crO['date_order'], #Datum von Katarina notwendig
                'date_approve' : crO['date_order'], #Datum von Katarina notwendig
                'partner_id' : crO['partner_id'],
                'fiscal_position_id' : 8 #Fiscal Position für LieferantDE
            })

            i=0
            for p in productIds:
                print("Erstelle Purchase Order Line: {}".format(i+1))
                qty= crO['qty'][i]
                i+=1
                if qty == 0: continue #lines mit 0 überspringen
                product = self.env['product.product'].search([('id', '=', p)])
                created=self.env['purchase.order.line'].create({
                    'product_qty' : qty,
                    'product_id' : p,
                    'partner_id' : 15777, #Partner ID für B&R
                    'order_id' : createdOrder.id,
                    'taxes_id' : [23] #Tax ID für 19%USt
                })


            #Geplantes Lieferdatum / date_planned auf das Datum aus der Exceldatei geändert
            print("Datum der Bestellung {} auf den {} ändern".format(createdOrder.name,crO['desired_date']))
            createdOrder.update({'date_planned' : crO['desired_date']})
