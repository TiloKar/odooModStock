import logging
from collections import defaultdict
from datetime import datetime, time
from dateutil import relativedelta
from itertools import groupby
from psycopg2 import OperationalError

from odoo import SUPERUSER_ID, _, api, fields, models, registry
from odoo.addons.stock.models.stock_rule import ProcurementException
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import add, float_compare, frozendict, split_every

_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    def _get_orderpoint_action(self):
        """Create manual orderpoints for missing product in each warehouses. It also removes
        orderpoints that have been replenish. In order to do it:
        - It uses the report.stock.quantity to find missing quantity per product/warehouse
        - It checks if orderpoint already exist to refill this location.
        - It checks if it exists other sources (e.g RFQ) tha refill the warehouse.
        - It creates the orderpoints for missing quantity that were not refill by an upper option.
        return replenish report ir.actions.act_window
        """
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context
        # Search also with archived ones to avoid to trigger product_location_check SQL constraints later
        # It means that when there will be a archived orderpoint on a location + product, the replenishment
        # report won't take in account this location + product and it won't create any manual orderpoint
        # In master: the active field should be remove
        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])
        # Remove previous automatically created orderpoint that has been refilled.
        orderpoints_removed = orderpoints._unlink_processed_orderpoints()
        orderpoints = orderpoints - orderpoints_removed
        to_refill = defaultdict(float)
        all_product_ids = []
        all_warehouse_ids = []
        # Take 3 months since it's the max for the forecast report
        # Das bedeutet, wenn man den Forcasted Report ausgibt werden nur Produkte angezeigt, deren Bedarfmeldungen innerhalb von 3 Monaten liegen.
        # Ein MO die heute (31.08.) eröffnet wird, wird noch angezeigt, wenn das geplannte Datum am 30.11. ist, aber verschwindet, wenn das Datum der 1.12 ist.
        # EDIT: Hanning Liu months von 3 auf 24 gesetzt um die Leadtage zu erhöhen
        to_date = add(fields.date.today(), months=24)
        # report.story.quantity zeigt den forcasted reported zu allen Produkten an und ist somit eine Erweiterung zum stock.quant
        qty_by_product_warehouse = self.env['report.stock.quantity'].read_group(
            [('date', '=', to_date), ('state', '=', 'forecast')],
            ['product_id', 'product_qty', 'warehouse_id'],
            ['product_id', 'warehouse_id'], lazy=False)

        for group in qty_by_product_warehouse:
            #setzt Warehouse id Stock = 1 Inventar = 2
            warehouse_id = group.get('warehouse_id') and group['warehouse_id'][0]
            # filtert den Forecast nach Produkte mit einer Prognose unter 0
            if group['product_qty'] >= 0.0 or not warehouse_id:
                continue
            # alle Produkte mit einer Prognose unter 0 werden in all_product_ids abgespeichert
            all_product_ids.append(group['product_id'][0])
            all_warehouse_ids.append(warehouse_id)
            # to refill = alle aufzufüllenden Produkte mit dem Format (73628, 1): -5.0 / nur negative Product_qty durch vorherige Abfrage
            to_refill[(group['product_id'][0], warehouse_id)] = group['product_qty']
        # wenn keine Produkte zum auffüllen vorhanden sind bricht die Methode hier ab
        if not to_refill:
            return action

        # Recompute the forecasted quantity for missing product today but at this time
        # with their real lead days.
        # Berechnung gruppiert nach leaddays
        key_to_remove = []
        pwh_per_day = defaultdict(list)
        for (product, warehouse) in to_refill.keys():
            product = self.env['product.product'].browse(product).with_prefetch(all_product_ids)
            warehouse = self.env['stock.warehouse'].browse(warehouse).with_prefetch(all_warehouse_ids)
            # Rules gibt die 'route_ids' und die 'warehouse_id' an
            rules = product._get_rules_from_location(warehouse.lot_stock_id)
            # Die Leaddays werden von den Supplierinfo entnommen
            lead_days = rules._get_lead_days(product)[0]
            #lead_days = rules.with_context(bypass_delay_description=True)._get_lead_days(product)[0]
            # EDIT Hanning Liu: Wenn keine Leaddays in der Supplierinfo eingetragen wird, wird derzeit standardmäßig eine Leadtime von 0 eingetragen
            # Somit wird, sobald die Leaddays 0 betragen automatisch eine 365 eingetragen
            # Das ist wichtig für die Fertigung, die lediglich einen Bedarf eintragen, aber keinen Lieferanten, wodurch eine Leadtime von 0 entsteht und somit nicht in der Auffüllung angezeigt wird.
            #if lead_days == 0:
            #    lead_days = 365
            #print("Produkt: " + str(product.product_tmpl_id.name) + " Lead_days: " +str(lead_days))
            # pwh_per_day ist ein Gruppierung der Produkte nach den Leadtagen. D.h. 10 Leadtage --> xxx, xxx, xxx PRoduct
            pwh_per_day[(lead_days, warehouse)].append(product.id)
        #print (str(pwh_per_day))

        # group product by lead_days and warehouse in order to read virtual_available
        # in batch
        for (days, warehouse), p_ids in pwh_per_day.items():
            products = self.env['product.product'].browse(p_ids)
            qties = products.with_context(
                warehouse=warehouse.id,
                to_date=fields.datetime.now() + relativedelta.relativedelta(days=days)
            ).read(['virtual_available'])

            #print(str(qties) + " test")
            for qty in qties:
                if float_compare(qty['virtual_available'], 0, precision_rounding=product.uom_id.rounding) >= 0:
                    key_to_remove.append((qty['id'], warehouse.id))
                else:
                    to_refill[(qty['id'], warehouse.id)] = qty['virtual_available']

        for key in key_to_remove:
            del to_refill[key]
        if not to_refill:
            return action

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
        for (product, warehouse), product_qty in to_refill.items():
            qty_in_progress = qty_by_product_wh.get((product, warehouse)) or 0.0
            qty_in_progress += orderpoint_by_product_warehouse.get((product, warehouse), 0.0)
            # Add qty to order for other orderpoint under this warehouse.
            if not qty_in_progress:
                continue
            to_refill[(product, warehouse)] = product_qty + qty_in_progress
        to_refill = {k: v for k, v in to_refill.items() if float_compare(
            v, 0.0, precision_digits=rounding) < 0.0}

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

    @api.depends('rule_ids', 'product_id.seller_ids', 'product_id.seller_ids.delay')
    def _compute_lead_days(self):
        counter = 0
        for orderpoint in self.with_context(bypass_delay_description=True):
            if not orderpoint.product_id or not orderpoint.location_id:
                orderpoint.lead_days_date = False
                continue
            values = orderpoint._get_lead_days_values()
            lead_days, dummy = orderpoint.rule_ids._get_lead_days(orderpoint.product_id, **values)
            # EDIT Hanning Liu: hier musste auch der Default auf 365 Tage gesetzt werden, damit es in der Auffüllung wirksam ist.
            #if lead_days == 0:
            #    lead_days = 365.0

            counter = counter +1
            print("NR: " + str(counter) + " | " + str(lead_days))
            lead_days_date = fields.Date.today() + relativedelta.relativedelta(days=lead_days)
            orderpoint.lead_days_date = lead_days_date

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
        orderpoints_to_remove.unlink()
        return orderpoints_to_remove

    @api.model
    def _get_orderpoint_values(self, product, location):
        return {
            'product_id': product,
            'location_id': location,
            'product_max_qty': 0.0,
            'product_min_qty': 0.0,
            'trigger': 'manual',
        }

    def _set_default_route_id(self):
        """ Write the `route_id` field on `self`. This method is intendend to be called on the
        orderpoints generated when openning the replenish report.
        """
        self = self.filtered(lambda o: not o.route_id)
        rules_groups = self.env['stock.rule'].read_group([
            ('route_id.product_selectable', '!=', False),
            ('location_id', 'in', self.location_id.ids),
            ('action', 'in', ['pull_push', 'pull'])
        ], ['location_id', 'route_id'], ['location_id', 'route_id'], lazy=False)
        for g in rules_groups:
            if not g.get('route_id'):
                continue
            orderpoints = self.filtered(lambda o: o.location_id.id == g['location_id'][0])
            orderpoints.route_id = g['route_id']

    def _get_qty_multiple_to_order(self):
        """ Calculates the minimum quantity that can be ordered according to the PO UoM or BoM
        """
        self.ensure_one()
        return 0
