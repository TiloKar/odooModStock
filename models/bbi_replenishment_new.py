import logging
from collections import defaultdict
from datetime import datetime, time
from dateutil import relativedelta
from itertools import groupby
from psycopg2 import OperationalError

from odoo import SUPERUSER_ID, _, api, fields, models, registry, tools
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import add, float_compare, frozendict, split_every

_logger = logging.getLogger(__name__)

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _get_orderpoint_action(self):
        #eigentliche Rückgabe zum Aufbau im Frontend, wird durch manipulation auf variable orderpoints im laufeder methode verändert
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context
        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])
        allStorables= self.env['product.product'].search([('detailed_type','=','product')])
        refill_id=[] #wird nur gebraucht um die purchase_order_lines auszulesen
        refill=[]
        in_order = []
        in_order_qty =[]

        for all in allStorables:
            if all.virtual_available< 0.0:
                refill_id.append(all.id)
                refill.append(all)

        # Methode an product.product nutzen um die purchase_order_lines zu prüfen und dann später von warehouse zu teilen.
        dummy, po_draft = self.env['product.product'].browse(refill_id)._get_quantity_in_progress(warehouse_ids=(1,))
        for (product, warehouse), product_qty in po_draft.items():
            in_order.append(product)
            in_order_qty.append(product_qty)

        # Die noch nicht bestätigten Angebote von refill abziehen
        temp=[]
        for r in refill:
            if r.id in in_order:
                index = in_order.index(r.id)
                check = r.virtual_available + in_order_qty[index]
                if check < 0:
                    temp.append(r)
            else:
                temp.append(r)
        refill=temp

        # Orderpoint erstellen oder updaten
        orderpoints_list =[]
        for r in refill:
            if r in orderpoints.product_id:
                o = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', r.id)])
                o[0].update({'qty_to_order':(max(o[0].product_min_qty, o[0].product_max_qty) - o[0].qty_forecast)})
            else:
                orderpoint_values= {}
                orderpoint_values['name']='Replenishment Report Test'
                orderpoint_values['trigger']='manual'
                orderpoint_values['active']= True
                orderpoint_values['warehouse_id']= 1
                orderpoint_values['location_id']=8
                orderpoint_values['product_id']=r.id
                orderpoint_values['company_id']=1
                orderpoint_values['qty_to_order']=1
                #to_order wird nicht benötigt, da er sich das selbst berechnet
                #if r.id in in_order:
                #    index = in_order.index(r.id)
                #    orderpoint_values['qty_to_order']=(r.virtual_available + in_order_qty[index])*-1
                orderpoints_list.append(orderpoint_values)
        orderpoints_create = self.env['stock.warehouse.orderpoint'].with_user(SUPERUSER_ID).create(orderpoints_list)

        # Route_ID, Vendor_ID und Supplier_ID
        # @TK Die Routeinformationen werden erst bei der 2. AUffüllung angezeigt, vllt.findest du eine Lösung, sonst muss ich evtl eine Verzögerung einbauen
        for o in orderpoints:
            if not o.route_id:
                p=self.env['product.product'].search([('id', '=', o.product_id.id)])
                if len(p[0].route_ids) == 1:
                    o.write({'route_id':p[0].route_ids.id})
            sup = self.env['product.supplierinfo'].search([('product_tmpl_id','=',o.product_id.product_tmpl_id.id)])
            if (not o.supplier_id) and len(sup) > 0:
                o.write({'supplier_id':sup[0].id, 'vendor_id': sup[0].name.id})

        return action

    @api.depends('product_id', 'location_id', 'product_id.stock_move_ids', 'product_id.stock_move_ids.state',
                 'product_id.stock_move_ids.date', 'product_id.stock_move_ids.product_uom_qty')
    def _compute_qty(self):
        orderpoints_contexts = defaultdict(lambda: self.env['stock.warehouse.orderpoint'])
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.qty_on_hand = False
                orderpoint.qty_forecast = False
                continue
            orderpoint_context = orderpoint._get_product_context()
            product_context = frozendict({**self.env.context, **orderpoint_context})
            orderpoints_contexts[product_context] |= orderpoint

        for orderpoint_context, orderpoints_by_context in orderpoints_contexts.items():

            products_qty = {
                p['id']: p for p in orderpoints_by_context.product_id.with_context(orderpoint_context).read(['qty_available', 'virtual_available'])
            }

            products_qty_in_progress = orderpoints_by_context._quantity_in_progress()

            for orderpoint in orderpoints_by_context:
                orderpoint.qty_on_hand = products_qty[orderpoint.product_id.id]['qty_available']
                #orderpoint.qty_forecast = products_qty[orderpoint.product_id.id]['virtual_available']  + products_qty_in_progress[orderpoint.id]
                orderpoint.qty_forecast = orderpoint.product_id.virtual_available + products_qty_in_progress[orderpoint.id]#EDIT HNN


    def action_replenish(self):
        now = datetime.now()
        try:
            self._procure_orderpoint_confirm(company_id=self.env.company)
        except UserError as e:
            if len(self) != 1:
                raise e
            raise RedirectWarning(e, {
                'name': self.product_id.display_name,
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'res_id': self.product_id.id,
                'views': [(self.env.ref('product.product_normal_form_view').id, 'form')],
                'context': {'form_view_initial_mode': 'edit'}
            }, _('Edit Product'))
        notification = False
        if len(self) == 1:
            notification = self.with_context(written_after=now)._get_replenishment_order_notification()
        # Forced to call compute quantity because we don't have a link.
        self._compute_qty()
        #EDIT HNN
        #self.filtered(lambda o: o.create_uid.id == SUPERUSER_ID and o.qty_to_order <= 0.0 and o.trigger == 'manual').unlink()
        return notification

    @api.autovacuum
    def _unlink_processed_orderpoints(self):
        domain = [
            ('create_uid', '=', SUPERUSER_ID),
            ('trigger', '=', 'manual'),
            ('qty_to_order', '<=', 0)
        ]
        if self.ids:
            expression.AND([domain, [('ids', 'in', self.ids)]])
        orderpoints_to_remove = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search(domain)
        # Remove previous automatically created orderpoint that has been refilled.
        #EDIT HNN
        #orderpoints_to_remove.unlink()
        return orderpoints_to_remove
