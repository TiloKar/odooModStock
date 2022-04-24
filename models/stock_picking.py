from odoo import api, fields, models

class Picking(models.Model):
    _inherit = 'stock.picking'

    csv_file = fields.Binary(string='CSV File')

    @api.onchange('csv_file')
    def parse_csv(self):
        return {'warning': {'title': "Output from parser", 'message': "Hallo Welt"},}
