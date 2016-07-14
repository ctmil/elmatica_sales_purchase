from openerp import models, fields, api, _
from openerp.osv import osv
from openerp.exceptions import except_orm
from StringIO import StringIO
import urllib2, httplib, urlparse, gzip, requests, json
import openerp.addons.decimal_precision as dp
import logging
import datetime
from openerp.fields import Date as newdate

#Get the logger
_logger = logging.getLogger(__name__)

class sale_order(models.Model):
	_inherit = 'sale.order'

	@api.one
	def _compute_shipping_days(self):
		destination = self.partner_id.country_id
		return_value = 0
		if not destination:
			self.shipping_days = 0
		else:
			if self.incoterm and self.incoterm.code in ('FCA', 'EXW'):
				self.shipping_days = 0
			else:
				days = self.env['elmatica_purchase_flow.shipping_days'].search([('to_country','=',destination.id)])
				if len(days)!=1:
					raise exceptions.Warning('Unable to retrieve shipping days for %s.' % destination.code)
			        self.shipping_days = days.shipping_days

	shipping_days = fields.Integer(string='Shipping days',compute=_compute_shipping_days)

class sale_order_line(models.Model):
	_inherit = 'sale.order.line'

	@api.one
	def _compute_calculated_leadtime_20(self):
		if self.product_id.product_tmpl_id.ntty_id and self.product_id.product_tmpl_id.ntty_id != '':
			self.calculated_leadtime = self.buffer_days + self.leadtime + self.additional_days + self.shipping_days
		else:
			return_value = 0
			if self.product_id.is_pack:
				max_leadtime = 0
				for product in self.product_id.wk_product_pack:
					if product.product_name.product_tmpl_id.ntty_id and product.product_name.product_tmpl_id.ntty_id != '':
						return_value = return_value + self.pcb_leadtime 
					else:
						if product.product_name.sale_delay > max_leadtime:
							max_leadtime = product.product_name.sale_delay
				if max_leadtime > 0:
					return_value = return_value + max_leadtime
				self.calculated_leadtime = return_value
			else:
				return_value = self.product_id.sale_delay 
				self.calculated_leadtime = return_value + self.shipping_days


	@api.one
	def _compute_shipping_days(self):
		if self.product_id.default_code != 'NRE' and self.incoterm.code != 'FCA':
			self.shipping_days = self.order_id.shipping_days
		else:
			self.shipping_days = 0

	shipping_days = fields.Integer(string='Shipping days',compute=_compute_shipping_days)
        calculated_leadtime = fields.Integer(string='Calculated Leadtime',compute=_compute_calculated_leadtime_20)

