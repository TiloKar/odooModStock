from odoo import api, fields, models

class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'
    supplier_id = fields.Many2one('product.supplierinfo', string='Product Supplier', check_company=True,domain="['|', ('product_id', '=', product_id), '&', ('product_id', '=', False), ('product_tmpl_id', '=', product_tmpl_id)]")
    vendor_id = fields.Many2one(related='supplier_id.name', string="Vendor", store=True)

    #überschreiben der check methode für einheiten-verletzung mit selbst-reparatur
    # im moment noch nicht im einsatz
    #@api.constrains('product_id')
    #def _check_product_uom(self):
    #    ''' Check if the UoM has the same category as the product standard UoM '''
    #    for orderpoint in self:
    #        if orderpoint.product_id.uom_id.category_id != orderpoint.product_uom.category_id:
    #            print(orderpoint.product_id)
#
    #    if any(orderpoint.product_id.uom_id.category_id != orderpoint.product_uom.category_id for orderpoint in self):
    #        raise ValidationError('You have to select a product unit of measure that is in the same category as the default unit of measure of the product\n'.format(orderpoint.product_id.id))
