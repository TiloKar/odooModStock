from odoo import api, fields, models
import csv, base64

class Picking(models.Model):
    _inherit = 'stock.picking'

    csv_file = fields.Binary(string='CSV File')
    output = fields.Char(string='internal output')

    def ebom_csv(self):
        raw = base64.b64decode(self.csv_file)
        raw_list = raw.split(b'\n')
        str_list = []
        for row in raw_list:
            str_row = row.decode(encoding='utf-8', errors='ignore').split(';')
            str_list.append(str_row)

        output = ""
        for row in str_list:
            result = self.env['product.template'].search([('default_code', '=', row[2])])
            if len(result) > 0:
                output = output + "1-"
            else:
                output = output + "0-"
        self.output = output

        return True
