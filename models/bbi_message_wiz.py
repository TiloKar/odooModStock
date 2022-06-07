from odoo import api, fields, models

class BbiMessageWizard(models.TransientModel):
    _name = 'bbi.message.wizard'
    _description = "Show Message"

    message = fields.Text('Message', required=True)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
