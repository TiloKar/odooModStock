from odoo import api, fields, models
from odoo.exceptions import ValidationError

class BbiMaterial(models.Model):
    _name = "bbi.material"
    _description = "Materialart des Produktes für den Einkauf"

    name = fields.Char(store = True, required = True , string = 'Material')
    description = fields.Char(store = True, string = 'Beschreibung')

    @api.onchange('name')
    def checkDuplicate(self):
        for i in self:
            result = self.env['bbi.material'].search([('name', '=', i.name)])
            if len(result)>0:
                raise ValidationError ("Material existiert bereits: " + i.name)
