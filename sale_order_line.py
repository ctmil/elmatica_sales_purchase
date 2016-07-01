from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp
from datetime import date
import logging
import datetime
from datetime import timedelta

_logger = logging.getLogger(__name__)

class sale_order_line(models.Model):
	_inherit = 'sale.order.line'

	@api.one
	def _calc_delivered_qty_v2(self):
		return_value = 0
		:wq


	@api.one
	def _calc_undelivered_qty_v2(self):
		return_value = 0


	delivered_qty = fields.Float('Delivered', compute='_calc_delivered_qty_v2')
	undelivered_qty = fields.Float('Undelivered', compute='_calc_undelivered_qty')
 


