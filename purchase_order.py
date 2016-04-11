from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp

import logging
import datetime

_logger = logging.getLogger(__name__)

class purchase_order(models.Model):
    _inherit = 'purchase.order'

    sale_order_id = fields.Many2one('sale.order',string='Origin SO')
