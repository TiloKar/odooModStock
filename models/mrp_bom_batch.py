from odoo import api, fields, models
import csv, base64

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    csv_file = fields.Binary(string='CSV File')

    output = fields.Char(string='internal output')

    def makeLinesFromKbom(self):
        message_id = self.env['bbi.message.wizard'].create({'message': 'muss noch gebaut werden'})
        return {
            'name': 'Fehler in der BOM!',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'bbi.message.wizard',
            'res_id': message_id.id,
            'target': 'new'
        }

    def makeLinesFromEbom(self):
        raw = base64.b64decode(self.csv_file) #vorbereitung binary
        raw_list = raw.split(b'\n') #zerlegen zeilenweise
        str_list = [] # wird ein 2-dimensionales array aller zelleneinträge als rohstrings
        rowNum = 0 # zähler zeilen
        errors = 0
        message ="";
        for row in raw_list:
            if rowNum > 1:
                if len(row) > 0: # nicht kopfzeile und leere ignorieren
                    str_row = row.decode(encoding='cp1252', errors='replace').split(';') # spaltenweise zerlegen, mbcs ist für windows PCs optimiert
                    if len(str_row) > 2:
                        str_list.append(str_row)
                    else:
                        errors += 1
                        message += " file-row " + str(str_row) + " not valid\n"
                #else:
                    #errors += 1
                    #message += " file-row " + str(rowNum) + " not valid\n"
                    #leerzeilen ignorieren
            rowNum+= 1

        if len(str_list) == 0 :
            errors+= 1
            message += " file has no lines\n"

        list = []
        if errors == 0:
            rowNum = 0 # zähler zeilen
            for row in str_list: #normiren auf zwei-spaltenliste
                entry = []
                entry.append(row[1])
                entry.append(row[2])
                list.append(entry)
                if len(list[rowNum][0]) == 0:
                    errors += 1
                    message += " file-row " + str(rowNum) + " quantity not set\n"
                elif len(list[rowNum][1]) == 0:
                    errors += 1
                    message += " file-row " + str(rowNum) + " scancode not set\n"
                rowNum+= 1

        if errors != 0:
            message_id = self.env['bbi.message.wizard'].create({'message': message})
            return {
                'name': 'Fehler in der BOM!',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'bbi.message.wizard',
                'res_id': message_id.id,
                'target': 'new'
            }
        else:
            return self.addLinesFromBom(list)

    def addLinesFromBom(self,list):

        datasets = [] # wird ein array mit den anzuhängenden dictionaries
        errors = 0
        message ="";
        if len(self.bom_line_ids) != 0:
            errors += 1
            message += " BOM must be empty for batch import\n"
        else:
            for row in list:
                result = self.env['product.template'].search([('default_code', '=', row[1])]) # product_template id.ermitteln
                if len(result) > 0:
                    result_p = self.env['product.product'].search([('product_tmpl_id', '=', result[0].id)]) # passend product_product.id ermitteln
                    #output_str = str(result[0].id) + "-"
                    datasets.append({
                        'product_tmpl_id': result[0].id,
                        'product_id' : result_p[0].id,
                        'product_qty': int(row[0]),
                        'product_uom_id': result[0].uom_id.id,
                        'bom_id': self.id
                    })
                else:
                    errors += 1
                    message += " unknown scancode: " + row[1] + "\n"
                    #output_str = output_str + "0-"

        #self.output = message
        if errors == 0:
            self.env['mrp.bom.line'].create(datasets)
            self.output = len(self.bom_line_ids)
            return True
        else:
            message_id = self.env['bbi.message.wizard'].create({'message': message})
            return {
                'name': 'Fehler in der BOM!',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'bbi.message.wizard',
                'res_id': message_id.id,
                'target': 'new'
            }

    @api.constrains('product_id', 'product_tmpl_id', 'bom_line_ids', 'byproduct_ids', 'operation_ids')
    def _check_bom_test(self):

        message = ""
        nLines = len(self.bom_line_ids)
        boms = self.env['mrp.bom'].search(['len(bom_line_ids)', '!=', nLines])
        raise ValidationError(_(str(len(boms))))
        sequenz_self = 0
        temp= 0
        test = False

        for k in self:
            for l in k.bom_line_ids:
                if l.sequence > 0:
                    sequenz_self= sequenz_self +1
        message = "Aktuelle BoM: " + str(self.product_tmpl_id.name) + "\n\n"
        for j in boms: # j alle boms überhaupt
            temp = 0
            for i in j.bom_line_ids: # alle lines der j-boms
                for k in self: #k ist die aktuelle bom
                    for l in k.bom_line_ids: # l sind lindes der aktuellen bom
                        if ((i.product_tmpl_id == l.product_tmpl_id) and (j != self) and (i.product_qty == l.product_qty)):
                            temp = temp + 1
                            break
            if temp == sequenz_self:
                test = True
                message = message + str(j.product_tmpl_id.name) + " gibt es schon! \n"
        #message_id = self.env['bbi.message.wizard'].create({'message': message})
        #if test == True:
        #    return {
        #        'name': 'Fehler in der BOM!',
        #        'type': 'ir.actions.act_window',
        #        'view_mode': 'form',
        #        'res_model': 'bbi.message.wizard',
        #        'res_id': message_id.id,
        #        'target': 'new'
        #        }
