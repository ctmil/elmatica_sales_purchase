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
				if self.incoterm.code == 'FCA':
                			self.shipping_days = 1
				elif self.incoterm.code == 'EXW':
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
        def _compute_calculated_leadtime(self):
		old_leadtime = self.super(sale_order_line,self)._compute_calculated_leadtime()
		self.calculated_leadtime = old_leadtime + self.shipping_days

	@api.one
	def _compute_shipping_days(self):
		self.shipping_days = self.order_id.shipping_days

	shipping_days = fields.Integer(string='Shipping days',compute=_compute_shipping_days)
