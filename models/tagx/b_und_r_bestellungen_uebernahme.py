from odoo import api, fields, models
import base64, xlrd, datetime
from datetime import date
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    # Excelimport
    def parseExcelData(self):
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

        # Datum wird in die Exceldatei nachgetragen
        date_order = datetime.datetime(*xlrd.xldate_as_tuple(sheet.cell(2, 0).value, book.datemode))
        for coloum in range(sheet.ncols):
            ausExcel= {}
            if coloum > 2:
                    ausExcel['index_col'] = coloum
                    ausExcel['partner_ref'] = str(sheet.cell(34, coloum).value)
                    ausExcel['partner_id'] = 15777 #Partner ID für B&R
                    ausExcel['desired_date'] = datetime.datetime(*xlrd.xldate_as_tuple(sheet.cell(1, coloum).value, book.datemode))
                    ausExcel['date_order'] = date_order
                    bestellung.append(ausExcel)
                    print("Lese Purchase Order Kopfdaten von Spalte: {} Wunschdatum {}.".format(coloum, ausExcel['desired_date']))

        #Prüfung auf Duplikate
        duplicate = []
        for check in bestellung:
            duplicate_partner_ref = self.env['purchase.order'].search([('partner_ref', '=', check['partner_ref'])])
            if len(duplicate_partner_ref) != 0:
                duplicate.append(check['partner_ref'])
        if len(duplicate) != 0:
            raise ValidationError("Partner Ref Duplikate: {}.".format(duplicate))

        # Purchase Order Daten erstellen
        for cr in bestellung:
            created=self.env['purchase.order'].create({
                        'partner_ref' : cr['partner_ref'],
                        'date_order' : cr['date_order'], #Datum von Katarina notwendig
                        'date_approve' : cr['date_order'], #Datum von Katarina notwendig
                        'partner_id' : cr['partner_id'],
                        'fiscal_position_id' : 8 #Fiscal Position für LieferantDE
                    })

            print("Erstelle Purchase Order Kopfdaten: {}.".format(cr['partner_ref']))

        # Purchase Order Lines aus Excel ziehen und vorbereiten
        positionen = []
        for coloum in range(sheet.ncols):
            if coloum > 2:
                # Treffer für die Order ID
                treffer_order_id = self.env['purchase.order'].search([('partner_ref', '=', str(sheet.cell(34, coloum).value))])
                for row in range(sheet.nrows):
                    print (str("Zeile {} und Spalte {}".format(row,coloum)))
                    ausExcel= {}
                    if (row > 2) and (row < 33) : # Erste und letzte Zeile
                        # Treffer für die Product ID
                        treffer_product_id = self.env['product.product'].search([('default_code', '=', str(sheet.cell(row, 1).value))])
                        ausExcel['product'] = treffer_product_id.default_code
                        ausExcel['product_name'] = treffer_product_id.product_tmpl_id.name #nicht notwendig
                        ausExcel['product_id'] = treffer_product_id.id
                        ausExcel['menge'] = sheet.cell(row, coloum).value
                        ausExcel['order_id'] = treffer_order_id.id
                        ausExcel['order_name'] = treffer_order_id.name #nicht notwendig

                        if (len(treffer_order_id) != 1) or (len(treffer_product_id) != 1):
                            raise ValidationError ("Fehler bei Produkt {} in Reihe {}.".format(sheet.cell(row, 1).value,row))
                        positionen.append(ausExcel)
                        print("Lese Purchase Order Lines von Spalte: {} und Zeile: {}.".format(coloum,row))

        # Purchase order Lines erstellen
        for cr2 in positionen:
            if cr2['menge'] != 0:
                created=self.env['purchase.order.line'].create({
                            #'name' : cr2['product_name'],
                            'product_qty' : cr2['menge'],
                            'product_id' : cr2['product_id'],
                            'partner_id' : 15777, #Partner ID für B&R
                            'order_id' : cr2['order_id'],
                            'taxes_id' : [23] #Tax ID für 19%USt
                        })
                print("Erstlle Purchase Order Line an der Purchase Order: {} mit {} x {}".format(cr2['order_name'],cr2['menge'],cr2['product_name'],))
            else:
                print("Lasse aus!")

        # Geplantes Lieferdatum / date_planned auf das Datum aus der Exceldatei geändert
        # WICHTIG! Aufgrund der Erstellgeschwindigkeit muss dieser Teil weiter unten stehen und kann nicht zusammen in einer for-Schleife wie die Erstellung der Kopfdaten gepackt werden,
        # weil sonst die Leadtime das date_planned überschreibt
        for d_planned in bestellung:
            treffer = self.env['purchase.order'].search([('partner_ref', '=', d_planned['partner_ref'])])
            treffer.date_planned = d_planned['desired_date']
            print("Datum der Bestellung {} auf den {} geändert.".format(treffer.name,d_planned['desired_date']))
