from odoo import api, fields, models

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    bbiSchmelze_name = fields.Char(
        related='lot_id.bbiSchmelze',
        string='Schmelznummer',
        readonly=False,
        store=True,
        )
        
    bbiMaterial_name = fields.Char(related="product_id.bbiMaterial_name")

    def action_print_serialnumber_bbi(self):
        return self.env.ref('bbi_mod_stock.action_report_seriennummer_bbi').report_action(self)
