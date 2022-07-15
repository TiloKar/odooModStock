from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    # comperator-funktion für REV Duplikatermittlung
    def compDuplicateHandler(self,p,toFind):
        if p['default_code'].lower() == toFind['default_code'].lower(): return True
        return False

    def handleBarcodeDuplicates(self):
        self.checkBarcodeDuplicatesInternal(True)

    def checkBarcodeDuplicates(self):
        self.checkBarcodeDuplicatesInternal(False)

    def checkBarcodeDuplicatesInternal(self,handleDuplicates):

        allProductsWithBarcode = self.env['product.product'].search([]).filtered(lambda p: p.default_code)
        print("alle teile mit barcode: {}".format(len(allProductsWithBarcode)))
        allProductsNoBarcode = self.env['product.product'].search([]).filtered(lambda p: not p.default_code)
        print("alle teile ohne barcode: {}".format(len(allProductsNoBarcode)))
        allProductsNoName = self.env['product.product'].search([]).filtered(lambda p: not p.name)
        print("alle teile ohne name: {}".format(len(allProductsNoName)))

        allProductsIter = []
        allProductsCandidates = []
        duples = []
        toDeleteCandidates = []

        #eigen suchliste und kandidatenliste erzeugen
        for p in allProductsWithBarcode:
            if p.create_date != False:
                allProductsIter.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': str(p.create_date),'user': p.create_uid.partner_id.name})
                allProductsCandidates.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': str(p.create_date),'user': p.create_uid.partner_id.name})
            else:
                allProductsIter.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': 'na','user': p.create_uid.partner_id.name})
                allProductsCandidates.append({'id': p.id , 'default_code': p.default_code,'bbiDrawingNb': p.bbiDrawingNb,'name': p.name,'date': 'na','user': p.create_uid.partner_id.name})

        for pIt in allProductsIter:
            if len(allProductsCandidates) == 0: break  #wenn noch kandidatenliste leer ist
            hits = list(filter(lambda p: p['id'] == pIt['id'],allProductsCandidates))
            if len(hits) == 0: continue #bereits entferntes Duplikat, übergehen bzw. ohne fund weiter
            toFind = {'id': pIt['id'] , 'default_code': pIt['default_code'],'bbiDrawingNb': pIt['bbiDrawingNb'],'name': pIt['name'],'date': pIt['date'],'user': pIt['user']}
            allProductsCandidates.remove(toFind) #sonst erstmal sich selbst rausnehmen
            #workaround um virtuals eindeutig zu kennzeichnen
            if pIt['default_code'] == 'virtual':
                print("updating virtual product barcode: {}".format(pIt['id']))
                self.env['product.product'].search([('id','=',pIt['id'])]).update({'default_code': str(pIt['default_code']) + str(pIt['id'])})
                continue # virtuelle Produkte übergehen
            if len(allProductsCandidates) > 0: # falls noch immer kandidaten da sind
                hits = list(filter(lambda p: self.compDuplicateHandler(p,pIt),allProductsCandidates))
                if len(hits) == 0: continue #keine Duplikate gefunden
                duples.append(toFind) #sonst ursprung des duplikats in ausgabe datei nehmen
                toDeleteCandidates.append({'id_1' : pIt['id'],'id_2' : hits[0]['id']})
                for p in hits:
                    print("duplikat mit id: {} zu id {}".format(str(p['id']),str(pIt['id'])))
                    toRemove = {'id': p['id'] , 'default_code': p['default_code'],'bbiDrawingNb': p['bbiDrawingNb'],'name': p['name'],'date': p['date'],'user': p['user']}
                    duples.append(toRemove) #duplikat aufnehmen
                    allProductsCandidates.remove(toRemove) # kandidaten entferene

        print ("duplikate: {}".format(len(duples)))
        #duplikate datei
        if (len(duples) > 0) and not handleDuplicates:
            ausgabe = ''
            ausgabe+= "{};{};{};{};{};{}\n".format('odoo id','interner odoo name','barcode','bbi zeichnungsnummer','im odoo erstellt am','im odoo erstellt von')
            for d in duples:
                ausgabe+= "{};{};{};{};{};{}\n".format(d['id'],str(d['name']).replace(';','|'),str(d['default_code']).replace(';','|'),d['bbiDrawingNb'],d['date'],d['user'])
            ausgabe+= 'ohne namen\n'
            for d in allProductsNoName:
                ausgabe+= "{};{};{}\n".format(d.id,str(d.name).replace(';','|'),str(d.default_code).replace(';','|'))
            ausgabe+= 'ohne barcode\n'
            for d in allProductsNoBarcode:
                ausgabe+= "{};{};{}\n".format(d.id,str(d.name).replace(';','|'),str(d.default_code).replace(';','|'))

            raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
            self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
            self.myFile_file_name = 'rev_duplicates.csv' # Name und Format des Downloads

        handleErorrs =[]
        if handleDuplicates:
            print("Duplikate fehlerhaftes kaufmann tos script behandeln...")
            #toDeleteCandidates.append({'id_src' : pIt['id'],'id_dupl' : hits[0]['id']})
            for d in toDeleteCandidates:
                id1 = self.env['product.product'].search([('id','=',d['id_1'])])
                id2 = self.env['product.product'].search([('id','=',d['id_2'])])
                if (not id1.create_date) or (not id2.create_date):
                    if id1.create_date:
                        src = id1
                        dpl = id2
                    else:
                        src = id2
                        dpl = id1
                        print("id src: {} id dupl: {} date:{}".format(src.id,dpl.id,dpl.create_date))
                    src.update({'name':dpl.name,'description':str(src.description) + str(dpl.description),'sale_ok':dpl.sale_ok,'purchase_ok':dpl.purchase_ok,'default_code':dpl.default_code})
                    print("versuche zu löschen: {}".format(dpl.id))
                    dpl.unlink()


            #to do: schleife über toDeleteCandidates
            # idee try catch und die mit error sammeln und als liste ausgeben

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

            #Löschkandidaten datei
            #if len(toDeleteCandidates) > 0:
            #    ausgabe = ''
            #    ausgabe+= "{};{};{};{};{};{}\n".format('odoo id','interner odoo name','barcode','bbi zeichnungsnummer','im odoo erstellt am','im odoo erstellt von')
            #    for d in toDeleteCandidates:
            #        ausgabe+= "{};{};{};{};{};{}\n".format(d['id'],d['name'],d['default_code'],d['bbiDrawingNb'],d['date'],d['user'])
            #    raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
            #    self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
            #    self.myFile_file_name = 'rev_to_delete.csv' # Name und Format des Downloads
