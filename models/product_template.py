from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    webshop = fields.Boolean(
        default=False,
        help='Check this, if product is sold via bbi webshop',
        store=True,
        readonly=False,)
