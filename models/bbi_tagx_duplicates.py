from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    # comperator-funktion für REV Duplikatermittlung
    def compRevHandler(self,p,toFind):
        if p['default_code'].lower() == toFind['default_code'].lower(): return True
        return False

    def handleRevDuplicates(self):

        allProducts = self.env['product.product'].search([]).filtered(lambda p: p.default_code)

        allProductsIter = []
        allProductsCandidates = []
        duples = []
        toDeleteCandidates = []

        for p in allProducts:
            #allProductsIter.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': str(p.create_date),'user': p.create_uid.partner_id.name})
            if p.create_date != False:
                allProductsIter.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': str(p.create_date),'user': p.create_uid.partner_id.name})
                allProductsCandidates.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': str(p.create_date),'user': p.create_uid.partner_id.name})
            else:
                allProductsIter.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': 'na','user': p.create_uid.partner_id.name})
                allProductsCandidates.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': 'na','user': p.create_uid.partner_id.name})
        print("alle teile mit barcode min {}".format(len(allProductsCandidates)))
        #print ("alle produkte: {}".format(len(allProducts)))

        for pIt in allProductsIter:
            if len(allProductsCandidates) > 0:
                #toFind = {'id': pIt['id'] , 'default_code': pIt['default_code'],'bbiDrawingNb': pIt['bbiDrawingNb'],'name': pIt['name'],'date': pIt['date'],'user': pIt['user']}
                hits = list(filter(lambda p: p['id'] == pIt['id'],allProductsCandidates))
                if len(hits) == 0: continue #bereits entferntes Duplikat, übergehen
                toFind = {'id': hits[0]['id'] , 'default_code': hits[0]['default_code'],'bbiDrawingNb': hits[0]['bbiDrawingNb'],'name': hits[0]['name'],'date': hits[0]['date'],'user': hits[0]['user']}
                allProductsCandidates.remove(toFind) #sonst erstmal sich selbst rausnehmen
                if pIt['default_code'] == 'virtual': continue # virtuelle Produkte übergehen
                if len(allProductsCandidates) > 0: # falls noch immer kandidaten da sind
                    hits = list(filter(lambda p: self.compRevHandler(p,pIt),allProductsCandidates))
                    if len(hits) == 0: continue #keine Duplikate gefunden
                    duples.append(toFind)
                    for p in hits:
                        print("duplikat mit id: {} zu id {}".format(str(p['id']),str(pIt['id'])))
                        #toRemove = {'id': p['id'] , 'default_code': p['default_code'],'bbiDrawingNb': p['bbiDrawingNb'],'name': p['name'],'date': p['date'],'user': p['user']}
                        toRemove = {'id': p['id'] , 'default_code': p['default_code'],'bbiDrawingNb': p['bbiDrawingNb'],'name': p['name'],'date': p['date'],'user': p['user']}
                        duples.append(toRemove)
                        allProductsCandidates.remove(toRemove)
                        #delCandidates = []
                        #delCandidates.append(toFind)
                        #delCandidates.append(toRemove)

                        #revFixSrc = list(filter(lambda p: "-REV" in p['default_code'],delCandidates))
                        #revFixDest = list(filter(lambda p: "-rev" in p['default_code'],delCandidates))
                        #if (len(revFixSrc)) > 0 and (len(revFixDest) > 0):
                        #    print("deleting: {}".format(revFixSrc))
                        #    dest = self.env['product.product'].search([('id', '=', revFixDest[0]['id'])])
                        #    src = self.env['product.product'].search([('id', '=', revFixSrc[0]['id'])])
                        #    dest.update({'name':src.name,'description':src.description,'sale_ok':src.sale_ok,'purchase_ok':src.purchase_ok,'default_code':src.default_code})
                        #    src.unlink()
                            #toDeleteCandidates.append({'id': toDelete.id , 'default_code': toDelete.default_code,'bbiDrawingNb': toDelete.bbiDrawingNb,'name': toDelete.name,'date': str(toDelete.create_date),'user': toDelete.create_uid.partner_id.name})

                        #continue # mehrere duplikate erst mal nicht behandeln

        print ("duplikate: {}".format(len(duples)))
        #duplikate datei
        if len(duples) > 0:
            ausgabe = ''
            ausgabe+= "{};{};{};{};{};{}\n".format('odoo id','interner odoo name','barcode','bbi zeichnungsnummer','im odoo erstellt am','im odoo erstellt von')
            for d in duples:
                ausgabe+= "{};{};{};{};{};{}\n".format(d['id'],d['name'],d['default_code'],d['bbiDrawingNb'],d['date'],d['user'])
            raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
            self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
            self.myFile_file_name = 'rev_duplicates.csv' # Name und Format des Downloads

        #Löschkandidaten datei
        #if len(toDeleteCandidates) > 0:
        #    ausgabe = ''
        #    ausgabe+= "{};{};{};{};{};{}\n".format('odoo id','interner odoo name','barcode','bbi zeichnungsnummer','im odoo erstellt am','im odoo erstellt von')
        #    for d in toDeleteCandidates:
        #        ausgabe+= "{};{};{};{};{};{}\n".format(d['id'],d['name'],d['default_code'],d['bbiDrawingNb'],d['date'],d['user'])
        #    raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        #    self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        #    self.myFile_file_name = 'rev_to_delete.csv' # Name und Format des Downloads
