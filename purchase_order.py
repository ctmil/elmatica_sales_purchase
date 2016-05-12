from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp

import logging
import datetime

_logger = logging.getLogger(__name__)

class purchase_order(models.Model):
	_inherit = 'purchase.order'

	@api.one
	def _compute_related_ppo(self):
		pos = self.sudo().sale_order_id.purchase_ids
		return_value = None
		for po in pos:
			if po.order_type == 'PPO':
				return_value = po.id
		self.related_ppo = return_value			

	@api.one
	def _compute_related_tpo(self):
		pos = self.sudo().sale_order_id.purchase_ids
		return_value = None
		for po in pos:
			if po.order_type == 'TPO':
				return_value = po.id
		self.related_tpo = return_value			

	@api.one
	def _calc_hub_days20(self):
		supplier = self.partner_id
		#import pdb;pdb.set_trace()
		if supplier.delivery_method=='exw': # ExWorks
			self.hub_days = 0
		else:
			#return_value = self.sudo().sale_order_id.calculated_leadtime - ( self.sudo().sale_order_id.manufacturing_days \
			#	+ self.sudo().sale_order_id.shipping_days + self.sudo().sale_order_id.additional_days \
			#	+ self.sudo().sale_order_id.buffer_days )
                        return_value = 0
			order = self.sudo().sale_order_id
			for line in order.order_line:
	                        if line.product_id.is_pack:
	                                for product in line.product_id.wk_product_pack:
        	                                if product.product_name.product_tmpl_id.ntty_id == '' or \
							not product.product_name.product_tmpl_id.ntty_id:
                                	                return_value = return_value + product.product_name.sale_delay
			self.hub_days = return_value


	sale_order_id = fields.Many2one('sale.order',string='Origin SO')
	hub_days = fields.Integer(string='Autoline days',compute=_calc_hub_days20)
	related_ppo = fields.Many2one('purchase.order',string='Related PPO',compute=_compute_related_ppo)
	related_tpo = fields.Many2one('purchase.order',string='Related TPO',compute=_compute_related_tpo)
	wkng_gerber = fields.Boolean(string='Wkng Gerber',default=True)
