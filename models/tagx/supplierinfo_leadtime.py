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
        print("nix")

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
        ausgabe+= "product_tmpl_id;productname;partner;anzahl einträge\n"
        i=0
        for s in allSupInfos:
            i+=1
            print("parse {} von {}".format(i,n))
            product=self.env['product.template'].search([('id','=',s[0])])
            partner=self.env['res.partner'].search([('id','=',s[1])])
            if (len(product) > 0) and (len(partner) > 0 and s[2] > 1):
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

                #myMessage='product {} with id {} has {} entries for supplier {}'.format(product.name,product.id,s[2],partner.name)
                #product.message_post(body=myMessage)
                #ausgabe+= "{};{};{};{};\n".format(product.id,product.name.replace(";","|").replace("\n","|"),partner.name.replace(";","|").replace("\n","|"),s[2])

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'overview supInfo.csv' # Name und Format des Downloads

#mini protokollfunktion im chatter erstmal nur für preis,menge und nummer
class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    def write(self, vals):

        product=self.env['product.template'].search([('id','=',self.product_tmpl_id.id)])
        partner=self.env['res.partner'].search([('id','=',self.name.id)])
        if ('min_qty' in vals.keys()) and (self.min_qty) :
            if self.min_qty != vals['min_qty']:
                myMessage='min_qty for supplier {} changed from {} to {}'.format(partner.name,self.min_qty,vals['min_qty'])
                product.message_post(body=myMessage)
        if ('product_code' in vals.keys()) and (self.product_code) :
            if self.product_code != vals['product_code']:
                myMessage='product_code for supplier {} changed from {} to {}'.format(partner.name,self.product_code,vals['product_code'])
                product.message_post(body=myMessage)
        if ('price' in vals.keys()) and (self.price) :
            if self.price != vals['price']:
                myMessage='price for supplier {} changed from {} to {}'.format(partner.name,self.price,vals['price'])
                product.message_post(body=myMessage)

        return super(models.Model,self).write(vals)
