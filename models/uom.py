
from collections import defaultdict
from datetime import timedelta
from itertools import groupby

from operator import itemgetter

from odoo import _, api, tools, Command, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import clean_context, OrderedSet

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    #temporäres ausserkraftsetzen der raise
    @api.constrains('location_id')
    def check_location_id(self):
        for quant in self:
            if quant.location_id.usage == 'view':
                print("bypassing raise in check_location_id")
                #raise ValidationError(_('You cannot take products from or deliver products to a location of type "view" (%s).') % quant.location_id.name)


class StockMoveBbi(models.Model):
    _inherit = 'stock.move'
    _order = 'sequence, id'

    #temporäres ausserkraftsetzen der raise
    @api.constrains('product_uom')
    def _check_uom(self):
        moves_error = self.filtered(lambda move: move.product_id.uom_id.category_id != move.product_uom.category_id)
        if moves_error:
            user_warning = _('You cannot perform the move because the unit of measure has a different category as the product unit of measure.')
            for move in moves_error:
                user_warning += _('\n\n%s --> Product UoM is %s (%s) - Move UoM is %s (%s)') % (move.product_id.display_name, move.product_id.uom_id.name, move.product_id.uom_id.category_id.name, move.product_uom.name, move.product_uom.category_id.name)
            user_warning += _('\n\nBlocking: %s') % ' ,'.join(moves_error.mapped('name'))
            print("bypassing raise in _check_uom")
            #raise UserError(user_warning)


    #temporäres ausserkraftsetzen der raise
    def _do_unreserve(self):
        moves_to_unreserve = OrderedSet()
        for move in self:
            if move.state == 'cancel' or (move.state == 'done' and move.scrapped):
                # We may have cancelled move in an open picking in a "propagate_cancel" scenario.
                # We may have done move in an open picking in a scrap scenario.
                continue
            elif move.state == 'done':
                print("bypassing raise in _do_unreserve")
            #    raise UserError(_("You cannot unreserve a stock move that has been set to 'Done'."))
            moves_to_unreserve.add(move.id)
        moves_to_unreserve = self.env['stock.move'].browse(moves_to_unreserve)

        ml_to_update, ml_to_unlink = OrderedSet(), OrderedSet()
        moves_not_to_recompute = OrderedSet()
        for ml in moves_to_unreserve.move_line_ids:
            if ml.qty_done:
                ml_to_update.add(ml.id)
            else:
                ml_to_unlink.add(ml.id)
                moves_not_to_recompute.add(ml.move_id.id)
        ml_to_update, ml_to_unlink = self.env['stock.move.line'].browse(ml_to_update), self.env['stock.move.line'].browse(ml_to_unlink)
        moves_not_to_recompute = self.env['stock.move'].browse(moves_not_to_recompute)

        ml_to_update.write({'product_uom_qty': 0})
        ml_to_unlink.unlink()
        # `write` on `stock.move.line` doesn't call `_recompute_state` (unlike to `unlink`),
        # so it must be called for each move where no move line has been deleted.
        (moves_to_unreserve - moves_not_to_recompute)._recompute_state()
        return True

    # temporäres aufheben des uom errors für reparatur der Mengeneinheietne
    def write(self, vals):
        # Handle the write on the initial demand by updating the reserved quantity and logging
        # messages according to the state of the stock.move records.
        receipt_moves_to_reassign = self.env['stock.move']
        move_to_recompute_state = self.env['stock.move']
        if 'product_uom' in vals and any(move.state == 'done' for move in self):
            print("bypassing raise in stock_move.write(vals)")
            #raise UserError(_('TK: You cannot change the UoM for a stock move that has been set to \'Done\'.'))

        if 'product_uom_qty' in vals:
            move_to_unreserve = self.env['stock.move']
            for move in self.filtered(lambda m: m.state not in ('done', 'draft') and m.picking_id):
                if float_compare(vals['product_uom_qty'], move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                    self.env['stock.move.line']._log_message(move.picking_id, move, 'stock.track_move_template', vals)
            if self.env.context.get('do_not_unreserve') is None:
                move_to_unreserve = self.filtered(
                    lambda m: m.state not in ['draft', 'done', 'cancel'] and float_compare(m.reserved_availability, vals.get('product_uom_qty'), precision_rounding=m.product_uom.rounding) == 1
                )
                move_to_unreserve._do_unreserve()
                (self - move_to_unreserve).filtered(lambda m: m.state == 'assigned').write({'state': 'partially_available'})
                # When editing the initial demand, directly run again action assign on receipt moves.
                receipt_moves_to_reassign |= move_to_unreserve.filtered(lambda m: m.location_id.usage == 'supplier')
                receipt_moves_to_reassign |= (self - move_to_unreserve).filtered(lambda m: m.location_id.usage == 'supplier' and m.state in ('partially_available', 'assigned'))
                move_to_recompute_state |= self - move_to_unreserve - receipt_moves_to_reassign
        if 'date_deadline' in vals:
            self._set_date_deadline(vals.get('date_deadline'))
        # hier super call verändert, damit nicht die alte methode nochmal aufgerufen wird
        res= super(models.Model,self).write(vals)

        if move_to_recompute_state:
            move_to_recompute_state._recompute_state()
        if receipt_moves_to_reassign:
            receipt_moves_to_reassign._action_assign()
        return res

class ProductTemplateBbi(models.Model):
    _inherit = 'product.template'

    # ergänzungen um bei unit fehler automatisch die abhängigkeiten zu behandeln
    def write(self, vals):
        self._sanitize_vals(vals)
        if 'uom_id' in vals:
            new_uom = self.env['uom.uom'].browse(vals['uom_id'])
            updated = self.filtered(lambda template: template.uom_id != new_uom)
            done_moves = self.env['stock.move'].search([('product_id', 'in', updated.with_context(active_test=False).mapped('product_variant_ids').ids)], limit=1)
            ausgabe=""
            if done_moves:
                #unlock all moves with state done
                closed_moves = done_moves.filtered(lambda m: m.state == 'done')

                #bbi inherit alle stock_moves auf die einheit bringen

                #error_move_lines= self.env['stock.move'].search([])

                for line in done_moves:
                    ausgabe += "moves to handle {} origin {} reference {}\n".format(line.id, line.origin,line.reference)
                    #if line.product_id.product_tmpl_id.uom_id.id != self.uom_id.id:
                        #if line.state == 'done':
                        #    if line.picking_id:
                        #        print("try to fix uom bug in stock.move {} for {} in picking {} in state {} origin {} reference {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.picking_id.name,line.state,line.origin,line.reference))
                        #    else:
                        #        print("try to fix uom bug in stock.move {} for {} with no picking id in state {} origin {} reference {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.state,line.origin,line.reference))
                    print("updating product move {} for product {} with uom {}".format(line.id,line.product_id.default_code,new_uom))
                    line.update({'product_uom' : new_uom })

                #ende inherit
                print("bypassing raise in product_template.write(vals)")
                #raise UserError(_("You cannot change the unit of measure as there are already stock moves for this product. If you want to change the unit of measure, you should rather archive this product and create a new one.\n{}".format(ausgabe)))
        if 'type' in vals and vals['type'] != 'product' and sum(self.mapped('nbr_reordering_rules')) != 0:
            raise UserError(_('You still have some active reordering rules on this product. Please archive or delete them first.'))
        if any('type' in vals and vals['type'] != prod_tmpl.type for prod_tmpl in self):
            existing_move_lines = self.env['stock.move.line'].search([
                ('product_id', 'in', self.mapped('product_variant_ids').ids),
                ('state', 'in', ['partially_available', 'assigned']),
            ])
            if existing_move_lines:

                for line in existing_move_lines:
                    print("try to unreserve move_line {}".format(line.id))
                    line.update({'product_qty':0,'product_uom_qty':0})



                raise UserError(_("You can not change the type of a product that is currently reserved on a stock move. If you need to change the type, you should first unreserve the stock move."))
        if 'type' in vals and vals['type'] != 'product' and any(p.type == 'product' and not float_is_zero(p.qty_available, precision_rounding=p.uom_id.rounding) for p in self):
            raise UserError(_("Available quantity should be set to zero before changing type"))
        # hier super call verändert, damit nicht die alte methode nochmal aufgerufen wird
        return super(models.Model,self).write(vals)




class UoM(models.Model):
    _inherit = 'uom.uom'
    _order = "factor DESC, id"



    #außerkraft setzen der prüfung bis units repariert, via raise if failure
    def _compute_quantity(self, qty, to_unit, round=True, rounding_method='UP', raise_if_failure=False):
        """ Convert the given quantity from the current UoM `self` into a given one
            :param qty: the quantity to convert
            :param to_unit: the destination UoM record (uom.uom)
            :param raise_if_failure: only if the conversion is not possible
                - if true, raise an exception if the conversion is not possible (different UoM category),
                - otherwise, return the initial quantity
        """
        if not self or not qty:
            return qty
        self.ensure_one()

        if self != to_unit and self.category_id.id != to_unit.category_id.id:
            if raise_if_failure:
                raise UserError(_('The unit of measure %s defined on the order line doesn\'t belong to the same category as the unit of measure %s defined on the product. Please correct the unit of measure defined on the order line or on the product, they should belong to the same category.') % (self.name, to_unit.name))
            else:
                return qty

        if self == to_unit:
            amount = qty
        else:
            amount = qty / self.factor
            if to_unit:
                amount = amount * to_unit.factor

        if to_unit and round:
            amount = tools.float_round(amount, precision_rounding=to_unit.rounding, rounding_method=rounding_method)

        return amount


class BbiStockLocation(models.Model):
    _inherit = 'bbi.stock.location'

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def fixingUom(self):
        print("repairing uom in purchase_order_lines")
        lines= self.env['purchase.order.line'].search([])
        for line in lines:
            print("checking purchase order line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in order.line {} for product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in ale_order_line")
        lines= self.env['sale.order.line'].search([])
        for line in lines:
            print("checking sale_order_line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in sale.order.line {} product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in stock_moves")
        lines= self.env['stock.move'].search([])
        for line in lines:
            print("checking move {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom.id:
                print("try to fix uom bug in stock_move {} for product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom' : line.product_id.product_tmpl_id.uom_id.id })

        print("repairing uom in stock_move_line")
        lines= self.env['stock.move.line'].search([])
        for line in lines:
            print("checking stock_move_line {}".format(line.id))
            if line.product_id.product_tmpl_id.uom_id.id != line.product_uom_id.id:
                print("try to fix uom bug in stock.move.line {} product {} with uom {}".format(line.id,line.product_id.product_tmpl_id.default_code,line.product_id.product_tmpl_id.uom_id.name))
                line.update({'product_uom_id' : line.product_id.product_tmpl_id.uom_id.id })

        #stock quants?
