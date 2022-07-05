from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #einmalige übernahme des wareneingangs buchs an TagX
    #nur offene bestellungen werden übernommen und auch nicht bestätigt,
    #Die Produktpositionen sollen beim Wareneingang manuell nachgetragen werden
    #stock_move lines mit status "partly availabe auf die gleiche product-positions-id sind das problem"
    #assigned gab auch probleme??
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
