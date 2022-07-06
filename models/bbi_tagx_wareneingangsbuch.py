from odoo import api, fields, models
import base64, xlrd, datetime
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #einmalige übernahme des wareneingangs buchs an TagX
    #nur offene bestellungen werden übernommen und auch nicht bestätigt,
    #Die Produktpositionen sollen beim Wareneingang manuell nachgetragen werden
    #stock_move lines mit status "partly availabe auf die gleiche product-positions-id sind das problem"
    #assigned gab auch probleme??

    def compPORef(self,p,pIt):
        if not p.partner_ref: return False
        if not pIt['internal_reference']: return False
        if pIt['internal_reference'].lower() == str(p.partner_ref).lower(): return True
        return False

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
            print("untersuche zeile: {}".format(i+1))
            ausKaufmann = {}
            if i < 7:
                continue
            #if i > 9: break
            try:
                ausKaufmann['partner_name'] = str(sheet.cell(i, 10).value)

                ausKaufmann['internal_reference'] = str(sheet.cell(i, 1).value)

                hlp = sheet.cell(i, 0).value
                orderDate = datetime.datetime(*xlrd.xldate_as_tuple(hlp, book.datemode))
                ausKaufmann['date_approve'] = orderDate

                hlp = sheet.cell(i, 2).value
                if str(hlp) == "na":
                    ausKaufmann['date_planned'] = False
                else:
                    orderDate = datetime.datetime(*xlrd.xldate_as_tuple(hlp, book.datemode))
                    ausKaufmann['date_planned'] = orderDate

            except:
                raise ValidationError('Daten-Fehler in Zeile {}'.format(i))

            hit = self.env['res.partner'].search([('name', '=', ausKaufmann['partner_name'])])
            if len(hit) > 0:
                ausKaufmann['partner_id'] = hit[0].id
            else:
                raise ValidationError('Partner {} nicht gefuden in Zeile {}'.format(ausKaufmann['partner_name'],i+1))

            datasets.append(ausKaufmann)


        print("PO to do: {}".format(len(datasets)))

        ausgabe= ""
        for po in datasets:
            hits = created=self.env['purchase.order'].search([]).filtered(lambda p: self.compPORef(p,po))
            if len(hits) == 0:
                print("erzeuge PO {}".format(po['internal_reference']))
                if po['date_planned'] != False:
                    created=self.env['purchase.order'].create({
                        'partner_ref' : po['internal_reference'],
                        'date_order' : po['date_approve'],
                        'date_approve' : po['date_approve'],
                        'partner_id' : po['partner_id'],
                        'date_planned' : po['date_planned']
                    })
                else:
                    created=self.env['purchase.order'].create({
                        'partner_ref' : po['internal_reference'],
                        'date_order' : po['date_approve'],
                        'date_approve' : po['date_approve'],
                        'partner_id' : po['partner_id']
                    })
                ausgabe+= "created:{};{};{}\n".format(po['internal_reference'],created.name,str(created.date_planned))
            else:
                print("PO gibt es schon: {} in {}".format(po['internal_reference'],hits[0].name))
                ausgabe+= "schon da:{};{}\n".format(po['internal_reference'],hits[0].name)

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'generated POs.csv' # Name und Format des Downloads
