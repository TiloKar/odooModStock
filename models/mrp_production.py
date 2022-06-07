from odoo import api, fields, models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    weldDoc = fields.Boolean(
        string = 'Schweißdoku',
        default=False,
        help='Check this, if product will need qualified welding documentation',
        store=True,
        readonly=False,
        required = True,)

    materialCerts = fields.Boolean(
        string = 'Materialzertifikate',
        default=False,
        help='Check this, if product will need qualified material documentation',
        store=True,
        readonly=False,
        required = True,)

    def _get_move_raw_values(self, product_id, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        source_location = self.location_src_id
        origin = self.name
        if self.orderpoint_id and self.origin:
            origin = self.origin.replace(
                '%s - ' % (self.orderpoint_id.display_name), '')
            origin = '%s,%s' % (origin, self.name)
        data = {
            'sequence': bom_line.sequence if bom_line else 10,
            'name': self.name,
            'date': self.date_planned_start,
            'date_deadline': self.date_planned_start,
            'bom_line_id': bom_line.id if bom_line else False,
            'picking_type_id': self.picking_type_id.id,
            'product_id': product_id.id,
            'product_uom_qty': product_uom_qty,
            'product_uom': product_uom.id,
            'location_id': source_location.id,
            'location_dest_id': self.product_id.with_company(self.company_id).property_stock_production.id,
            'raw_material_production_id': self.id,
            'company_id': self.company_id.id,
            'operation_id': operation_id,
            'price_unit': product_id.standard_price,
            'procure_method': 'make_to_stock',
            'origin': origin,
            'state': 'draft',
            'warehouse_id': source_location.warehouse_id.id,
            'group_id': self.procurement_group_id.id,
            'propagate_cancel': self.propagate_cancel,
            'materialCerts': bom_line.materialCerts,
        }
        return data
