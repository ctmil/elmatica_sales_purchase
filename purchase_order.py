from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp

import logging
import datetime

_logger = logging.getLogger(__name__)

class purchase_order(models.Model):
	_inherit = 'purchase.order'

	@api.multi
	def _calc_hub_days20(self):
		for order in self:
			supplier = order.partner_id
			if supplier.delivery_method=='exw': # ExWorks
				order.hub_days = 0
			else:
				import pdb;pdb.set_trace()
				order.hub_days = order.sale_order_id.calculated_leadtime - ( order.sale_order_id.shipping_days \
					+ order.sale_order_id.additional_days + order.sale_order_id.buffer_days )


	sale_order_id = fields.Many2one('sale.order',string='Origin SO')
	hub_days = fields.Integer(string='Autoline days',compute=_calc_hub_days20)
