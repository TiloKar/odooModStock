from odoo import api, fields, models
import csv, base64

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    csv_file = fields.Binary(string='CSV File')
    output = fields.Char(string='internal output')

    def ebom_csv(self):
        raw = base64.b64decode(self.csv_file)
        raw_list = raw.split(b'\n')
        str_list = []
        offset = 0
        for row in raw_list:
            if offset > 0:
                str_row = row.decode(encoding='utf-8', errors='ignore').split(';')
                str_list.append(str_row)
            offset = offset + 1

        output_str = "len: " + str(len(str_list)) + " : "
        for row in str_list:
            result = self.env['product.template'].search([('default_code', '=', row[2])])
            if len(result) > 0:
                output_str = output_str + str(result[0].id) + "-"

                self.env['mrp.bom.line'].create({
                    'product_id': result[0].id,
                    'product_qty': int(row[0]),
                    'product_uom_id': 1,
                    'bom_id': self.id
                })
            else:
                output_str = output_str + "0-"
        self.output = output_str
        #self.env.cr.commit()

        return True
