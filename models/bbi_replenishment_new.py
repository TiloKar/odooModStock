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

#eigen kopie des reports für auffüllungs-query mod
#im ersten select, die bedingung für date komplet tentfernt, date wird noch gebildet, aber nicht mehr zum filtern genutzt
class BbiReportStockQuantityMini(models.Model):
    _name = 'bbi.report.stock.quantity.mini'
    _auto = False
    _description = 'Stock Quantity Report bbi mod for Replenishment minfied for wh/stock und INV/stock'

    def init(self):
        tools.drop_view_if_exists(self._cr, 'bbi_report_stock_quantity_mini')
        #sicherheitshalber um bereinigen

#eigen kopie des reports für auffüllungs-query mod
#im ersten select, die bedingung für date komplet tentfernt, date wird noch gebildet, aber nicht mehr zum filtern genutzt
class BbiReportStockQuantity(models.Model):
    _name = 'bbi.report.stock.quantity'
    _auto = False
    _description = 'Stock Quantity Report bbi mod for Replenishment'


    def init(self):
        #sicherheitshalber um bereinigen
        tools.drop_view_if_exists(self._cr, 'bbi_report_stock_quantity')



class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"


    def _get_orderpoint_action(self):

        #probelem: einige Produkte z.B. 46858 tauchen nicht auf
        #db dump vom 14.09 dazu liegt unter  Z:\Austausch\TK



        #eigentliche Rückgabe zum Aufbau im Frontend, wird durch manipulation auf variable orderpoints im laufeder methode verändert
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context

        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])

        # Remove previous automatically created orderpoint that has been refilled (purchase orders).

        orderpoints_removed = orderpoints._unlink_processed_orderpoints()
        orderpoints = orderpoints - orderpoints_removed
        to_refill = defaultdict(float)
        all_product_ids = []
        all_warehouse_ids = []

        allStorables= self.env['product.product'].search([('detailed_type','=','product')])

        for p in allStorables:
            qty_INV = p.with_context({'location' : 21}).virtual_available
            if qty_INV < 0.0:
                warehouse_id = 2
                all_product_ids.append(p.id)
                all_warehouse_ids.append(warehouse_id)
                to_refill[(p.id, warehouse_id)] = qty_INV
            qty_WH = p.with_context({'location' : 8}).virtual_available
            if qty_WH < 0.0:
                warehouse_id = 1
                all_product_ids.append(p.id)
                all_warehouse_ids.append(warehouse_id)
                to_refill[(p.id, warehouse_id)] = qty_WH


        # Remove incoming quantity from other origin than moves (e.g RFQ)
        product_ids, warehouse_ids = zip(*to_refill)
        dummy, qty_by_product_wh = self.env['product.product'].browse(product_ids)._get_quantity_in_progress(warehouse_ids=warehouse_ids)
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        # Group orderpoint by product-warehouse
        orderpoint_by_product_warehouse = self.env['stock.warehouse.orderpoint'].read_group(
            [('id', 'in', orderpoints.ids)],
            ['product_id', 'warehouse_id', 'qty_to_order:sum'],
            ['product_id', 'warehouse_id'], lazy=False)
        orderpoint_by_product_warehouse = {
            (record.get('product_id')[0], record.get('warehouse_id')[0]): record.get('qty_to_order')
            for record in orderpoint_by_product_warehouse
        }
        print("1. to refill: {}".format(len(to_refill)))
        for (product, warehouse), product_qty in to_refill.items():
            qty_in_progress = qty_by_product_wh.get((product, warehouse)) or 0.0
            qty_in_progress += orderpoint_by_product_warehouse.get((product, warehouse), 0.0)
            # Add qty to order for other orderpoint under this warehouse.
            if not qty_in_progress:
                continue
            to_refill[(product, warehouse)] = product_qty + qty_in_progress
        to_refill = {k: v for k, v in to_refill.items() if float_compare(
            v, 0.0, precision_digits=rounding) < 0.0}
        print("2. to refill: {}".format(len(to_refill)))

        lot_stock_id_by_warehouse = self.env['stock.warehouse'].with_context(active_test=False).search_read([
            ('id', 'in', [g[1] for g in to_refill.keys()])
        ], ['lot_stock_id'])
        lot_stock_id_by_warehouse = {w['id']: w['lot_stock_id'][0] for w in lot_stock_id_by_warehouse}

        # With archived ones to avoid `product_location_check` SQL constraints
        orderpoint_by_product_location = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).read_group(
            [('id', 'in', orderpoints.ids)],
            ['product_id', 'location_id', 'ids:array_agg(id)'],
            ['product_id', 'location_id'], lazy=False)
        orderpoint_by_product_location = {
            (record.get('product_id')[0], record.get('location_id')[0]): record.get('ids')[0]
            for record in orderpoint_by_product_location
        }
        print("3. to refill: {}".format(len(to_refill)))
        orderpoint_values_list = []
        for (product, warehouse), product_qty in to_refill.items():
            lot_stock_id = lot_stock_id_by_warehouse[warehouse]
            orderpoint_id = orderpoint_by_product_location.get((product, lot_stock_id))
            if orderpoint_id:
                self.env['stock.warehouse.orderpoint'].browse(orderpoint_id).qty_forecast += product_qty
            else:
                orderpoint_values = self.env['stock.warehouse.orderpoint']._get_orderpoint_values(product, lot_stock_id)
                orderpoint_values.update({
                    'name': _('Replenishment Report'),
                    'warehouse_id': warehouse,
                    'company_id': self.env['stock.warehouse'].browse(warehouse).company_id.id,
                })
                orderpoint_values_list.append(orderpoint_values)

        print("4. to refill (verändert): {}".format(len(orderpoint_values_list)))
        print("Values_list: {}".format(orderpoint_values_list))

        orderpoints = self.env['stock.warehouse.orderpoint'].with_user(SUPERUSER_ID).create(orderpoint_values_list)
        for o in orderpoints:

            print(o.product_id.virtual_available)
        #for orderpoint in orderpoints:
        #    orderpoint_wh = orderpoint.location_id.warehouse_id
        #    orderpoint.route_id = next((r for r in orderpoint.product_id.route_ids if not r.supplied_wh_id or r.supplied_wh_id == orderpoint_wh), orderpoint.route_id)
        #    if not orderpoint.route_id:
        #        orderpoint._set_default_route_id()
        #    orderpoint.qty_multiple = orderpoint._get_qty_multiple_to_order()

        return action

    @api.depends('product_id', 'location_id', 'product_id.stock_move_ids', 'product_id.stock_move_ids.state',
                 'product_id.stock_move_ids.date', 'product_id.stock_move_ids.product_uom_qty')
    def _compute_qty(self):
        print("Hier compute qty")
        orderpoints_contexts = defaultdict(lambda: self.env['stock.warehouse.orderpoint'])
        for orderpoint in self:
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.qty_on_hand = False
                orderpoint.qty_forecast = False
                continue
            # Hier wird standardmäßig die location und die Zeit geholt (in unserem Fall 4 Jahre)
            orderpoint_context = orderpoint._get_product_context()

            # Hier werden Location und Zeit an die eigenen Informatioen??? gehängt
            # {'lang': 'en_US', 'tz': 'Europe/Berlin', 'uid': 29, 'allowed_company_ids': [1],
            # 'mail_notify_force_send': False, 'search_default_trigger': 'manual', 'search_default_filter_to_reorder': True,
            # 'search_default_filter_not_snoozed': True, 'default_trigger': 'manual', 'bin_size': True, 'location': 8,
            # 'to_date': datetime.datetime(2026, 9, 13, 23, 59, 59, 999999)}
            product_context = frozendict({**self.env.context, **orderpoint_context})

            # Die eigenen User Informationen werden mit der Location und der Zeit an die Orderpoint gehangen
            # orderpoint_context != orderpoints_contexts
            # Datensätzen werden von den stock_moves bestimmt
            orderpoints_contexts[product_context] |= orderpoint
            #print('#')
            #print(orderpoints_contexts)

        for orderpoint_context, orderpoints_by_context in orderpoints_contexts.items():
            #print('#')
            #print(orderpoint_context)

            products_qty = {
                p['id']: p for p in orderpoints_by_context.product_id.with_context(orderpoint_context).read(['qty_available', 'virtual_available'])
            }

            products_qty_in_progress = orderpoints_by_context._quantity_in_progress()
            #print('#')
            #print(products_qty_in_progress)
            for orderpoint in orderpoints_by_context:
                orderpoint.qty_on_hand = products_qty[orderpoint.product_id.id]['qty_available']
                orderpoint.qty_forecast = orderpoint.product_id.virtual_available #EDIT HNN
                #orderpoint.qty_forecast = products_qty[orderpoint.product_id.id]['virtual_available']

                print("Forcast: {} | Virtual: {}".format(orderpoint.qty_forecast, orderpoint.product_id.virtual_available))
