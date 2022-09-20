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
        #sicherheitshalber zum bereinigen, nach erstem update kann das raus

#eigen kopie des reports für auffüllungs-query mod
#im ersten select, die bedingung für date komplet tentfernt, date wird noch gebildet, aber nicht mehr zum filtern genutzt
class BbiReportStockQuantity(models.Model):
    _name = 'bbi.report.stock.quantity'
    _auto = False
    _description = 'Stock Quantity Report bbi mod for Replenishment'

    def init(self):
        #sicherheitshalber zum bereinigen, nach erstem update kann das raus
        tools.drop_view_if_exists(self._cr, 'bbi_report_stock_quantity')

class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"


    #original  qty_to_order ist computet und benutzt  qty_forecast und qty_multiple, product_max_qty, product_min_qty

    #orderpoint.qty_on_hand und orderpoint.qty_forecast werden computet mit qty_on_hand= product_product.qty_available
    # orderpoint.qty_forecast=product_product.virtual_available + orderpoint._quantity_in_progress

    #_compute_qty_to_order nutzt forecast und melde/min bestände + losgröße um die tatsächlich zu bestellende menge auszugeben auf qty_to_order (computet)
    # _compute_qty_to_order wird auch von stock_rule genutzt


    #product_product.virtual_available ist          quant + in_progress (die geplante menge aller bestätigten vorgänge ohne zeiteinschränkung)
    #product_product.qty_available ist die summer über alle chargen die tatsächlich ungenutzt im lager liegen bliebe, wenn alle geplanten verbrauche entnommen würden)
    #product_product.free_qty ist für mich nicht nachvollziehbar, es wird niemla negativ, ist weder quant noch progress und hat auch nichts mit order am hut

    def _get_orderpoint_action(self):

        query = """
SELECT WH_qty_union.product_id, SUM(WH_qty_union.qty_progress), SUM(WH_qty_union.qty_order) FROM (
    SELECT WH_qty_progress.product_id, SUM(WH_qty_progress.qty) as qty_progress, 0 as qty_order FROM (
        SELECT product_id,SUM(product_qty) as qty
            FROM stock_move
            WHERE location_dest_id = 8 and state NOT IN ('draft', 'cancel', 'done')
            GROUP BY product_id
        UNION ALL
        SELECT product_id,-SUM(product_qty) as qty
            FROM stock_move
            WHERE location_id = 8 and state NOT IN ('draft', 'cancel', 'done')
            GROUP BY product_id
        ) as WH_qty_progress
        GROUP BY product_id
    UNION ALL
    SELECT WH_qty_order.product_id, 0 as qty_progress, SUM(WH_qty_order.qty) as qty_order FROM (
        SELECT purchase_order_line.product_id,purchase_order_line.product_qty as qty, purchase_order.picking_type_id
            FROM purchase_order_line
            INNER JOIN purchase_order ON (purchase_order.id = purchase_order_line.order_id)
                and (purchase_order_line.display_type IS NULL)
                and purchase_order_line.state IN ('draft', 'sent')
        ) as WH_qty_order
        GROUP BY product_id
    )as WH_qty_union
    GROUP BY product_id
"""

        self.env.cr.execute(query)
        forecastet=self.env.cr.fetchall()

        #eigentliche Rückgabe zum Aufbau im Frontend, einträge werden durch manipulation in laufeder methode verändert
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context

        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])

        #die Orderpoint Ids auflisten zur bessren verarbeitung
        #allOrderpointIds = []

        #orderpoints_removed = orderpoints._unlink_processed_orderpoints()
        #orderpoints = orderpoints - orderpoints_removed
        #to_refill = defaultdict(float)
        #all_product_ids = []
        #all_warehouse_ids = []
        updated_orderpoint_ids = []

        allStorables= self.env['product.product'].search([('detailed_type','=','product')])


        print(len(forecastet))

        return

        forecastetDict = {}
        #transformieren in dict für bessere anwendbarkeit der ergebnisse
        for f in forecastet:
            forecastetDict[str(f[0])] = f

        allStorables= self.env['product.product'].search([('detailed_type','=','product')])



        for p in allStorables:

            quantOdoo = self.env['stock.quant'].search([('product_id','=',p.id),('location_id','=',8)])
            quant = 0
            if len(quantOdoo) > 0:
                quant = 0
                for q in quantOdoo: quant += q.quantity #damit werden los quantities addiert
            in_progress = 0
            orders_sent = 0
            if str(p.id) in forecastetDict.keys():
                in_progress = forecastetDict[str(p.id)][1]
                orders_sent = forecastetDict[str(p.id)][2]
            check_to_order = - quant - in_progress - orders_sent
            to_order = 0
            if check_to_order > 0 :
                to_order = check_to_order
                #warehouse_id = 1
                #all_product_ids.append(p.id)
                #all_warehouse_ids.append(warehouse_id)
                #to_refill[(p.id, warehouse_id)] = to_order


                calc_odoo_to_order = p.with_context({'location' : 8}).free_qty
                try_calc = 0
                if (quant + in_progress) > 0 :
                    try_calc = quant
                else:
                    try_calc = 0
                if calc_odoo_to_order != (try_calc):
                    print("{} try:{} quant: {} in progress: {} orders_sent: {}".format(p.name,calc_odoo_to_order,quant,in_progress,orders_sent))
                    return

        print(len(to_refill))
        print("keine abweichungen")

        return


                #alter code
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
