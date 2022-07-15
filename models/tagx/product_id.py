from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"
    def handleMissingProductId(self):

        allProductTemplates = self.env['product.template'].search([])
        print("alle product_templates: {}".format(len(allProductTemplates)))
        allProductProducts= self.env['product.product'].search([])
        print("alle product_product: {}".format(len(allProductProducts)))

        allProdTempl= []
        allProdProd = []
        toCreateCandidates = []

        for p in allProductTemplates:
            allProdTempl.append({'id': p.id,'default_code': p.default_code })
        for p in allProductProducts:
            allProdProd.append({'id': p.id,'product_tmpl_id': p.product_tmpl_id.id})

        for pIt in allProductTemplates:
            hits = list(filter(lambda p: p['product_tmpl_id'] == pIt['id'],allProdProd))
            if len(hits) == 0:
                toCreateCandidates.append({'product_tmpl_id': pIt['id'],'default_code': pIt['default_code']})
            else:
                allProdProd.remove({'id': hits[0]['id'],'product_tmpl_id': hits[0]['product_tmpl_id']})

        print ("fehlende product_product: {}".format(len(toCreateCandidates)))
        #duplikate datei

        for d in toCreateCandidates:
            print ("erzeuge product_product für tmpl_id: {}".format(d['product_tmpl_id']))
            self.env['product.product'].create({
                'product_tmpl_id': d['product_tmpl_id'],
                'active' : True,
                'default_code': d['default_code'],
            })
