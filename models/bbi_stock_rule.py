import logging
from collections import defaultdict, namedtuple

from dateutil.relativedelta import relativedelta

from odoo import SUPERUSER_ID, _, api, fields, models, registry
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import float_compare, float_is_zero, html_escape
from odoo.tools.misc import split_every

_logger = logging.getLogger(__name__)

class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_lead_days(self, product, **values):
        """Returns the cumulative delay and its description encountered by a
        procurement going through the rules in `self`.
        :param product: the product of the procurement
        :type product: :class:`~odoo.addons.product.models.product.ProductProduct`
        :return: the cumulative delay and cumulative delay's description
        :rtype: tuple[int, list[str, str]]
        """
        delay = sum(self.filtered(lambda r: r.action in ['pull', 'pull_push']).mapped('delay'))
        #if delay == 0:
        #    delay = 365
        if self.env.context.get('bypass_delay_description'):
            delay_description = []
        else:
            delay_description = [
                (_('Delay on %s', rule.name), _('+ %d day(s)', rule.delay))
                for rule in self
                if rule.action in ['pull', 'pull_push'] and rule.delay
            ]
        return delay, delay_description
