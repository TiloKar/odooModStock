from odoo import api, fields, models
import csv, base64

class BbiMessageWizard(models.TransientModel):
    _name = 'bbi.message.wizard'
    _description = "Show Message"

    message = fields.Text('Message', required=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    csv_file = fields.Binary(string='CSV File')
    output = fields.Char(string='internal output')

    def ebom_csv(self):
        raw = base64.b64decode(self.csv_file) #vorbereitung binary
        raw_list = raw.split(b'\n') #zerlegen zeilenweise
        str_list = [] # wird ein 2-dimensionales array aller zelleneinträge als rohstrings
        offset = 0 # zähler zeilen
        for row in raw_list:
            if offset > 0 and len(row) > 0: # nicht kopfzeile und leere ignorieren
                str_row = row.decode(encoding='cp1252', errors='replace').split(';') # spaltenweise zerlegen, mbcs ist für windows PCs optimiert
                str_list.append(str_row)
            offset = offset + 1

        #output_str = "len: " + str(len(str_list)) + " hits: "
        lines = [] # wird ein array mit den anzuhängenden dictionaries
        errors = 0
        message ="";
        if len(str_list) > 0:
            for row in str_list:
                if len(row) > 2:
                    result = self.env['product.template'].search([('default_code', '=', row[2])]) # product_template id.ermitteln
                    if len(result) > 0:
                        result_p = self.env['product.product'].search([('product_tmpl_id', '=', result[0].id)]) # passend product_product.id ermitteln
                        #output_str = str(result[0].id) + "-"
                        lines.append({
                            'product_tmpl_id': result[0].id,
                            'product_id' : result_p[0].id,
                            'product_qty': int(row[0]),
                            'product_uom_id': result[0].uom_id.id,
                            'bom_id': self.id
                        })
                    else:
                        errors += 1
                        message += " unknown scancode: " + row[2] + "\n"
                        #output_str = output_str + "0-"
                else:
                    errors += 1
                    message += " line " + str(row) + " not valid\n"
        else:
            errors += 1
            message += " file not valid\n"
        #self.output = message
        if errors == 0:
            self.env['mrp.bom.line'].create(lines)
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
