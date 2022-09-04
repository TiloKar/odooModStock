from odoo import api, fields, models
import base64, xlrd, datetime
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #holt lead times
    def getLeadTimes(self):
        self.handleLeadTimes(False)

    #setzt lead times auf minimum
    def setLeadTimes(self):
        self.handleLeadTimes(365)

    #ändere zu kurze
    def handleLeadTimes(self,minTime):
        ausgabe = ''
        allSupInfos=self.env['product.supplierinfo'].search([]).sorted(lambda s: s.product_tmpl_id)
        n = len(allSupInfos)
        print("sup infos gibt es {}".format(n))
        ausgabe+= "product_tmpl_id;productname;partner;bestellnummer partner;lead_time;preis\n"
        i=0
        for s in allSupInfos:
            i+=1
            print("parse {} von {}".format(i,n))
            ausgabe+= "{};{};{};{};{};{}\n".format(s.product_tmpl_id.id,s.product_tmpl_id.name,s.name.name,s.product_code,s.delay,s.price)
            if (minTime != False):
                if s.delay < minTime:
                    print("updating lead time of supInfo id {}".format(s.id))
                    s.update({'delay':minTime})

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'overview supInfo.csv' # Name und Format des Downloads

    def deleteSupInfoDuplicates(self):

        query = """ SELECT product_tmpl_id,name,COUNT(product_tmpl_id)
                    FROM product_supplierinfo
                    GROUP BY name,product_tmpl_id
                    ORDER BY product_tmpl_id"""
        self.env.cr.execute(query)
        allSupInfos=self.env.cr.fetchall()

        ausgabe = ''
        n = len(allSupInfos)
        print("gruppierte sup infos gibt es {}".format(n))
        i=0
        for s in allSupInfos:
            i+=1
            print("parse {} von {}".format(i,n))
            product=self.env['product.template'].search([('id','=',s[0])])
            partner=self.env['res.partner'].search([('id','=',s[1])])
            if (len(product) > 0) and (len(partner) > 0) and (s[2] > 1):
                print("try to delete duplicates for product_tmpl_id {}".format(s[0]))
                supInfos=self.env['product.supplierinfo'].search([('name','=',s[1]),('product_tmpl_id','=',s[0])]).sorted(key=lambda si: si.id)
                k=0
                end = s[2] - 1
                for sc in supInfos:
                    if k < end:
                        myMessage='entries for supplier {} deleted by script reverting history in supplierInfo. code: {} price: {} qty: {} created: {}'.format(partner.name,sc.product_code,sc.price,sc.min_qty,sc.create_date)
                        product.message_post(body=myMessage)
                        sc.unlink()
                    k+=1
