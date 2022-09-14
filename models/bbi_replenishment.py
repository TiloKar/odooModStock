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

    date = fields.Date(string='Date', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    state = fields.Selection([
        ('forecast', 'Forecasted Stock'),
        ('in', 'Forecasted Receipts'),
        ('out', 'Forecasted Deliveries'),
    ], string='State', readonly=True)
    product_qty = fields.Float(string='Quantity', readonly=True)
    move_ids = fields.One2many('stock.move', readonly=True) #wird nicht benutzt
    company_id = fields.Many2one('res.company', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', readonly=True)

    def init(self):
        """
        Because we can transfer a product from a warehouse to another one thanks to a stock move, we need to
        generate some fake stock moves before processing all of them. That way, in case of an interwarehouse
        transfer, we will have an outgoing stock move for the source warehouse and an incoming stock move
        for the destination one. To do so, we select all relevant SM (incoming, outgoing and interwarehouse),
        then we duplicate all these SM and edit the values:
            - product_qty is kept if the SM is not the duplicated one or if the SM is an interwarehouse one
                otherwise, we set the value to 0 (this allows us to filter it out during the SM processing)
            - the source warehouse is kept if the SM is not the duplicated one
            - the dest warehouse is kept if the SM is not the duplicated one and is not an interwarehouse
                OR the SM is the duplicated one and is an interwarehouse
        """
        tools.drop_view_if_exists(self._cr, 'bbi_report_stock_quantity')
        query = """
CREATE or REPLACE VIEW bbi_report_stock_quantity AS (
WITH
    existing_sm (id, product_id, tmpl_id, product_qty, date, state, company_id, whs_id, whd_id) AS (
        SELECT m.id, m.product_id, pt.id, m.product_qty, m.date, m.state, m.company_id, whs.id, whd.id
        FROM stock_move m
        LEFT JOIN stock_location ls on (ls.id=m.location_id)
        LEFT JOIN stock_location ld on (ld.id=m.location_dest_id)
        LEFT JOIN stock_warehouse whs ON ls.parent_path like concat('%/', whs.view_location_id, '/%')
        LEFT JOIN stock_warehouse whd ON ld.parent_path like concat('%/', whd.view_location_id, '/%')
        LEFT JOIN product_product pp on pp.id=m.product_id
        LEFT JOIN product_template pt on pt.id=pp.product_tmpl_id
        WHERE pt.type = 'product' AND
            (whs.id IS NOT NULL OR whd.id IS NOT NULL) AND
            (whs.id IS NULL OR whd.id IS NULL OR whs.id != whd.id) AND
            m.product_qty != 0 AND
            m.state NOT IN ('draft', 'cancel', 'done')
    ),
    all_sm (id, product_id, tmpl_id, product_qty, date, state, company_id, whs_id, whd_id) AS (
        SELECT sm.id, sm.product_id, sm.tmpl_id,
            CASE
                WHEN is_duplicated = 0 THEN sm.product_qty
                WHEN sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id THEN sm.product_qty
                ELSE 0
            END,
            sm.date, sm.state, sm.company_id,
            CASE WHEN is_duplicated = 0 THEN sm.whs_id END,
            CASE
                WHEN is_duplicated = 0 AND NOT (sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id) THEN sm.whd_id
                WHEN is_duplicated = 1 AND (sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id) THEN sm.whd_id
            END
        FROM
            GENERATE_SERIES(0, 1, 1) is_duplicated,
            existing_sm sm
    )
SELECT
    MIN(id) as id,
    product_id,
    product_tmpl_id,
    state,
    date,
    sum(product_qty) as product_qty,
    company_id,
    warehouse_id
FROM (SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN 'out'
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN 'in'
        END AS state,
        m.date::date AS date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0 AND
        m.state != 'done'
    UNION ALL
    SELECT
        -q.id as id,
        q.product_id,
        pp.product_tmpl_id,
        'forecast' as state,
        date.*::date,
        q.quantity as product_qty,
        q.company_id,
        wh.id as warehouse_id
    FROM
        GENERATE_SERIES((now() at time zone 'utc')::date - interval '3month',
        (now() at time zone 'utc')::date + interval '3 month', '1 day'::interval) date,
        stock_quant q
    LEFT JOIN stock_location l on (l.id=q.location_id)
    LEFT JOIN stock_warehouse wh ON l.parent_path like concat('%/', wh.view_location_id, '/%')
    LEFT JOIN product_product pp on pp.id=q.product_id
    WHERE
        (l.usage = 'internal' AND wh.id IS NOT NULL) OR
        l.usage = 'transit'
    UNION ALL
    SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        'forecast' as state,
        GENERATE_SERIES(
        CASE
            WHEN m.state = 'done' THEN (now() at time zone 'utc')::date - interval '3month'
            ELSE m.date::date
        END,
        CASE
            WHEN m.state != 'done' THEN (now() at time zone 'utc')::date + interval '3 month'
            ELSE m.date::date - interval '1 day'
        END, '1 day'::interval)::date date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL AND m.state = 'done' THEN m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL AND m.state = 'done' THEN -m.product_qty
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0) AS forecast_qty
GROUP BY product_id, product_tmpl_id, state, date, company_id, warehouse_id
);
"""
        self.env.cr.execute(query)


#eigen kopie des reports für auffüllungs-query mod
#im ersten select, die bedingung für date komplet tentfernt, date wird noch gebildet, aber nicht mehr zum filtern genutzt
class BbiReportStockQuantity(models.Model):
    _name = 'bbi.report.stock.quantity'
    _auto = False
    _description = 'Stock Quantity Report bbi mod for Replenishment'

    date = fields.Date(string='Date', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    state = fields.Selection([
        ('forecast', 'Forecasted Stock'),
        ('in', 'Forecasted Receipts'),
        ('out', 'Forecasted Deliveries'),
    ], string='State', readonly=True)
    product_qty = fields.Float(string='Quantity', readonly=True)
    move_ids = fields.One2many('stock.move', readonly=True) #wird nicht benutzt
    company_id = fields.Many2one('res.company', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', readonly=True)

    def init(self):
        """
        Because we can transfer a product from a warehouse to another one thanks to a stock move, we need to
        generate some fake stock moves before processing all of them. That way, in case of an interwarehouse
        transfer, we will have an outgoing stock move for the source warehouse and an incoming stock move
        for the destination one. To do so, we select all relevant SM (incoming, outgoing and interwarehouse),
        then we duplicate all these SM and edit the values:
            - product_qty is kept if the SM is not the duplicated one or if the SM is an interwarehouse one
                otherwise, we set the value to 0 (this allows us to filter it out during the SM processing)
            - the source warehouse is kept if the SM is not the duplicated one
            - the dest warehouse is kept if the SM is not the duplicated one and is not an interwarehouse
                OR the SM is the duplicated one and is an interwarehouse
        """
        tools.drop_view_if_exists(self._cr, 'bbi_report_stock_quantity')
        query = """
CREATE or REPLACE VIEW bbi_report_stock_quantity AS (
WITH
    existing_sm (id, product_id, tmpl_id, product_qty, date, state, company_id, whs_id, whd_id) AS (
        SELECT m.id, m.product_id, pt.id, m.product_qty, m.date, m.state, m.company_id, whs.id, whd.id
        FROM stock_move m
        LEFT JOIN stock_location ls on (ls.id=m.location_id)
        LEFT JOIN stock_location ld on (ld.id=m.location_dest_id)
        LEFT JOIN stock_warehouse whs ON ls.parent_path like concat('%/', whs.view_location_id, '/%')
        LEFT JOIN stock_warehouse whd ON ld.parent_path like concat('%/', whd.view_location_id, '/%')
        LEFT JOIN product_product pp on pp.id=m.product_id
        LEFT JOIN product_template pt on pt.id=pp.product_tmpl_id
        WHERE pt.type = 'product' AND
            (whs.id IS NOT NULL OR whd.id IS NOT NULL) AND
            (whs.id IS NULL OR whd.id IS NULL OR whs.id != whd.id) AND
            m.product_qty != 0 AND
            m.state NOT IN ('draft', 'cancel', 'done')
    ),
    all_sm (id, product_id, tmpl_id, product_qty, date, state, company_id, whs_id, whd_id) AS (
        SELECT sm.id, sm.product_id, sm.tmpl_id,
            CASE
                WHEN is_duplicated = 0 THEN sm.product_qty
                WHEN sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id THEN sm.product_qty
                ELSE 0
            END,
            sm.date, sm.state, sm.company_id,
            CASE WHEN is_duplicated = 0 THEN sm.whs_id END,
            CASE
                WHEN is_duplicated = 0 AND NOT (sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id) THEN sm.whd_id
                WHEN is_duplicated = 1 AND (sm.whs_id IS NOT NULL AND sm.whd_id IS NOT NULL AND sm.whs_id != sm.whd_id) THEN sm.whd_id
            END
        FROM
            GENERATE_SERIES(0, 1, 1) is_duplicated,
            existing_sm sm
    )
SELECT
    MIN(id) as id,
    product_id,
    product_tmpl_id,
    state,
    date,
    sum(product_qty) as product_qty,
    company_id,
    warehouse_id
FROM (SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN 'out'
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN 'in'
        END AS state,
        m.date::date AS date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0 AND
        m.state != 'done'
    UNION ALL
    SELECT
        -q.id as id,
        q.product_id,
        pp.product_tmpl_id,
        'forecast' as state,
        date.*::date,
        q.quantity as product_qty,
        q.company_id,
        wh.id as warehouse_id
    FROM
        GENERATE_SERIES((now() at time zone 'utc')::date - interval '3month',
        (now() at time zone 'utc')::date + interval '3 month', '1 day'::interval) date,
        stock_quant q
    LEFT JOIN stock_location l on (l.id=q.location_id)
    LEFT JOIN stock_warehouse wh ON l.parent_path like concat('%/', wh.view_location_id, '/%')
    LEFT JOIN product_product pp on pp.id=q.product_id
    WHERE
        (l.usage = 'internal' AND wh.id IS NOT NULL) OR
        l.usage = 'transit'
    UNION ALL
    SELECT
        m.id,
        m.product_id,
        m.tmpl_id as product_tmpl_id,
        'forecast' as state,
        GENERATE_SERIES(
        CASE
            WHEN m.state = 'done' THEN (now() at time zone 'utc')::date - interval '3month'
            ELSE m.date::date
        END,
        CASE
            WHEN m.state != 'done' THEN (now() at time zone 'utc')::date + interval '3 month'
            ELSE m.date::date - interval '1 day'
        END, '1 day'::interval)::date date,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL AND m.state = 'done' THEN m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL AND m.state = 'done' THEN -m.product_qty
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN -m.product_qty
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.product_qty
        END AS product_qty,
        m.company_id,
        CASE
            WHEN m.whs_id IS NOT NULL AND m.whd_id IS NULL THEN m.whs_id
            WHEN m.whd_id IS NOT NULL AND m.whs_id IS NULL THEN m.whd_id
        END AS warehouse_id
    FROM
        all_sm m
    WHERE
        m.product_qty != 0) AS forecast_qty
GROUP BY product_id, product_tmpl_id, state, date, company_id, warehouse_id
);
"""
        self.env.cr.execute(query)


class StockWarehouseOrderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"


    def restore_orderpoint_info(self,supInfos):
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        action['context'] = self.env.context
        orderpoints = self.env['stock.warehouse.orderpoint'].search([])
        for op in orderpoints:
            for item in supInfos:
                #print(op.product_id.id)
                if op.product_id.id == item['product_id']:
                    op.supplier_id = item['supplier_id']
                    op.vendor_id = item['vendor_id']

        return action

    def _get_orderpoint_action(self):
        """Create manual orderpoints for missing product in each warehouses. It also removes
        orderpoints that have been replenish. In order to do it:
        - It uses the report.stock.quantity to find missing quantity per product/warehouse
        - It checks if orderpoint already exist to refill this location.
        - It checks if it exists other sources (e.g RFQ) tha refill the warehouse.
        - It creates the orderpoints for missing quantity that were not refill by an upper option.
        return replenish report ir.actions.act_window
        """

        #action = self.env["ir.actions.actions"]._for_xml_id("stock.action_orderpoint_replenish")
        #action['context'] = self.env.context
        # Search also with archived ones to avoid to trigger product_location_check SQL constraints later
        # It means that when there will be a archived orderpoint on a location + product, the replenishment
        # report won't take in account this location + product and it won't create any manual orderpoint
        # In master: the active field should be remove
        #todo snoozed behandeln ???
        to_delete = self.env['stock.warehouse.orderpoint'].search([('trigger','=','manual')])
        std_supplier = []

        #workaroud löschen aller orderpoints und apspeichern der supinfo
        for op in to_delete:
            #print(op)
            if op.supplier_id:
                std_supplier.append({'supplier_id':op.supplier_id.id,'product_id':op.product_id.id,'vendor_id':op.vendor_id.id,})
            op.unlink()
        orderpoints = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search([])

        # Remove previous automatically created orderpoint that has been refilled.
        orderpoints_removed = orderpoints._unlink_processed_orderpoints()
        orderpoints = orderpoints - orderpoints_removed - to_delete
        to_refill = defaultdict(float)
        all_product_ids = []
        all_warehouse_ids = []
        # Take 3 months since it's the max for the forecast report
        # Das bedeutet, wenn man den Forcasted Report ausgibt werden nur Produkte angezeigt, deren Bedarfmeldungen innerhalb von 3 Monaten liegen.
        # Ein MO die heute (31.08.) eröffnet wird, wird noch angezeigt, wenn das geplannte Datum am 30.11. ist, aber verschwindet, wenn das Datum der 1.12 ist.
        # EDIT: Hanning Liu months von 3 auf 24 gesetzt um die Leadtage zu erhöhen
        to_date = add(fields.date.today(), months=24)
        # report.story.quantity zeigt den forcasted reported zu allen Produkten an und ist somit eine Erweiterung zum stock.quant


        #das Grundproblem ist, der forecast ist keine abfrage relaer werte zundern eine geschätzte menge



        qty_by_product_warehouse = self.env['bbi.report.stock.quantity'].read_group(
            #edited tk: auch hier den filter auf date komplett entfernt
            [('state', '=', 'forecast')],
            ['product_id', 'product_qty', 'warehouse_id'],
            ['product_id', 'warehouse_id'], lazy=False)

        #print(len(qty_by_product_warehouse))
        #print(qty_by_product_warehouse[0])
        print(len(allStorablesWHStock = self.env['product.product'].with_context(location=8).search([('detailed_type','=','product')])))
        print(len(allStorablesINVStock = self.env['product.product'].with_context(location=21).search([('detailed_type','=','product')])))

        return

        for item in qty_by_product_warehouse:
            if item['product_id'][0] == 77776:
                print('\n#\n#\n#\n1')
                print(item)

                #todo 2 eigene sql abfragen WH/Stock
                #warehouse 1 zugänge, location_dest_id = 8 group by product_id sum(qty)
                #warehouse 1 abgänge, location_id = 8 group by product_id sum(qty)
                #dif ist menge zum füllen

                #WH/INV
                #warehouse 2 zugänge, location_dest_id = 21 group by product_id sum(qty)
                #warehouse 2 abgänge, location_id = 21 group by product_id sum(qty)
                #dif ist menge zum füllen



        for group in qty_by_product_warehouse:

        #    if p.virtual_available < 0.0:

            #setzt Warehouse id Stock = 1 Inventar = 2
            #    if p.warehouse_id
            warehouse_id = group.get('warehouse_id') and group['warehouse_id'][0]
            # filtert den Forecast nach Produkte mit einer Prognose unter 0
            if group['product_qty'] >= 0.0 or not warehouse_id:
                continue
            # alle Produkte mit einer Prognose über 0 werden in all_product_ids abgespeichert
            all_product_ids.append(group['product_id'][0])
            all_warehouse_ids.append(warehouse_id)
            # to refill = alle aufzufüllenden Produkte mit dem Format (73628, 1): -5.0 / nur negative Product_qty durch vorherige Abfrage
            to_refill[(group['product_id'][0], warehouse_id)] = group['product_qty']
        # wenn keine Produkte zum auffüllen vorhanden sind bricht die Methode hier ab

        if not to_refill:
            return self.restore_orderpoint_info(std_supplier)

        # Recompute the forecasted quantity for missing product today but at this time
        # with their real lead days.
        # Berechnung gruppiert nach leaddays
        #nachtrag tilo: ich denke hier werden die lead_days betrachtet und am ende des blocks weitere
        #einträge entfernt,
        #da wir mal versuchen wollen, die Auffüllung unabhängig von den lead days zu gestalten, wird die zeile unten auskommentiert
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
            #pwh_per_day ist ein Gruppierung der Produkte nach den Leadtagen. D.h. 10 Leadtage --> xxx, xxx, xxx PRoduct
            #overwrite TK leadtimes künstlich hochsetzen, damit auffüllungsliste alles enthält, was offen ist
            pwh_per_day[(lead_days, warehouse)].append(product.id)

        #print (str(pwh_per_day))

        # group product by lead_days and warehouse in order to read virtual_available
        # in batch
        for (days, warehouse), p_ids in pwh_per_day.items():
            products = self.env['product.product'].browse(p_ids)
            qties = products.with_context(
                warehouse=warehouse.id,
                to_date=fields.datetime.now() + relativedelta.relativedelta(days=1460) # Mod TK: hier statisch alle zugänge über 4 jahre verrechnen
            ).read(['virtual_available'])

            #print(str(qties) + " test")
            for qty in qties:
                if float_compare(qty['virtual_available'], 0, precision_rounding=product.uom_id.rounding) >= 0:
                    key_to_remove.append((qty['id'], warehouse.id))
                else:
                    to_refill[(qty['id'], warehouse.id)] = qty['virtual_available']

        for key in key_to_remove:  #Auffüllung sollte damit nicht mehr auf die lead times achten
            del to_refill[key]
        if not to_refill:
            return self.restore_orderpoint_info(std_supplier)

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
        return self.restore_orderpoint_info(std_supplier)
