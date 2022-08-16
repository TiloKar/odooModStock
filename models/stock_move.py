from odoo import api, fields, models
from odoo.exceptions import ValidationError

class StockMove(models.Model):
    _inherit = 'stock.move'

    materialCerts = fields.Boolean(
        string = 'MCert',
        default=False,
        help='If checked, material documentation has to be documentated while manufacturing',
        store=True,
        readonly=True,)

    qualityCheck = fields.Boolean(
        related='product_id.product_tmpl_id.qualityCheck',
        string="Deep Check",
        readonly=True,
        store=False,)

    def action_print_serialnumber_bbi(self):
        return self.env.ref('bbi_mod_stock.action_report_seriennummer_bbi').report_action(self)

        if self.id != 1:
            print(self.id)
            raise ValidationError("Test")
