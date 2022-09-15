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

        query = """ SELECT product_id,SUM(product_qty) qty
                    FROM stock_move
                    WHERE location_dest_id = 8 AND state not in
                    GROUP BY picking_id
                    ORDER BY picking_id"""
        self.env.cr.execute(query)
        allInputPickings=self.env.cr.fetchall()



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
        #    if p.id==46858:
            #    print("\n#\n#\n#\n#\n#1\n{} {}".format(qty_INV,qty_WH))

        # wenn keine Produkte zum auffüllen vorhanden sind bricht die Methode hier ab
#
    #    if not to_refill:
    #        return action

    #    if  46858 in    all_product_ids:
    #        print("\n#\n#\n#\n#\n#2 is da\n")




        # Remove incoming quantity from other origin than moves (e.g RFQ)
        product_ids, warehouse_ids = zip(*to_refill)
        print("\n#\n#\n#\n#\n#3")
        print(product_ids)
        print(warehouse_ids)
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
        for (product, warehouse), product_qty in to_refill.items():
            qty_in_progress = qty_by_product_wh.get((product, warehouse)) or 0.0
            qty_in_progress += orderpoint_by_product_warehouse.get((product, warehouse), 0.0)
            # Add qty to order for other orderpoint under this warehouse.
            if not qty_in_progress:
                continue
            to_refill[(product, warehouse)] = product_qty + qty_in_progress
        to_refill = {k: v for k, v in to_refill.items() if float_compare(
            v, 0.0, precision_digits=rounding) < 0.0}
        print("\n#\n#\n#\n#\n#3\n{}".format(to_refill))

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

        orderpoints = self.env['stock.warehouse.orderpoint'].with_user(SUPERUSER_ID).create(orderpoint_values_list)
        for orderpoint in orderpoints:
            orderpoint_wh = orderpoint.location_id.warehouse_id
            orderpoint.route_id = next((r for r in orderpoint.product_id.route_ids if not r.supplied_wh_id or r.supplied_wh_id == orderpoint_wh), orderpoint.route_id)
            if not orderpoint.route_id:
                orderpoint._set_default_route_id()
            orderpoint.qty_multiple = orderpoint._get_qty_multiple_to_order()
        return action
