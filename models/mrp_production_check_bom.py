from odoo import api, fields, models
import csv, base64

class BbiMessageWizard(models.TransientModel):
    _name = 'bbi.message.wizard'
    _description = "Show Message"

    message = fields.Text('Message', required=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def check_bom(self):
        message ="funktioniert und es gibt keine Übereinstimmung";
        message_id = self.env['bbi.message.wizard'].create({'message': message})
        return {
            'name': 'Test',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'bbi.message.wizard',
            'res_id': message_id.id,
            'target': 'new'
        }
