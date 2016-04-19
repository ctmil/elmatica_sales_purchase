from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp

import logging
import datetime

_logger = logging.getLogger(__name__)

class purchase_order(models.Model):
	_inherit = 'purchase.order'

	@api.one
	def _calc_hub_days20(self):
		#supplier = self.partner_id
		#import pdb;pdb.set_trace()
		#if supplier.delivery_method=='exw': # ExWorks
		#	self.hub_days = 0
		#else:
		# import pdb;pdb.set_trace()
		return_value = self.sale_order_id.calculated_leadtime - ( self.sale_order_id.manufacturing_days + self.sale_order_id.shipping_days \
			+ self.sale_order_id.additional_days + self.sale_order_id.buffer_days )
		self.hub_days = return_value


	sale_order_id = fields.Many2one('sale.order',string='Origin SO')
	hub_days = fields.Integer(string='Autoline days',compute=_calc_hub_days20)
