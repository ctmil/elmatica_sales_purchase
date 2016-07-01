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
		if self.product_id.is_pack:
			for pack_line in self.product_id.wk_product_pack:
				if pack_line.product_name.product_tmpl_id.ntty_id and pack_line.product_name.product_tmpl_id.ntty_id != '':
					pcb_product = pack_line.product_name.id
			pickings = self.env['stock.picking'].search([('origin','=',self.order_id.name)])
			for picking in pickings:
				if picking.state == 'done':
					for move_line in picking.move_lines:
						if move_line.product_id.id == pcb_product:
							return_value = return_value + move_line.product_uom_qty
		self.delivered_qty = return_value	


	@api.one
	def _calc_undelivered_qty_v2(self):
		return_value = 0
		self.undelivered_qty = return_value	


	delivered_qty = fields.Float('Delivered', compute='_calc_delivered_qty_v2')
	undelivered_qty = fields.Float('Undelivered', compute='_calc_undelivered_qty')
 


