from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp
from datetime import date
import logging
import datetime
from datetime import timedelta

_logger = logging.getLogger(__name__)

class sale_order(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_create_purchase_order(self):

        names_to_skip = [x.upper() for x in ['DHL_DELIVERY',
                                'C_SHIPPING',
                                'LOCAL FREIGHT',
                                'FCA',
                                'info:']]
        domain_to_skip = [('name','ilike',x) for x in names_to_skip]
        pipes = ['|' for x in range(len(domain_to_skip)-1)]
        domain_to_skip = pipes + domain_to_skip

        products_to_skip = self.env['product.product'].search(domain_to_skip)
        _logger.debug('Product names to skip %s - %s', domain_to_skip, products_to_skip)

        for sale in self:
	    if not sale.selected_supplier:
                raise exceptions.ValidationError(_('No supplier set for order %s' % sale.name))
            if not sale.requested_delivery_date:
                raise exceptions.ValidationError(_('Requested delivery date not set for sales order %s' % sale.name))
            if not sale.state in ['progress','manual']:
                raise exceptions.ValidationError(_('Order should be confirmed in order to create POs'))

            customer_location = self.env['ir.property'].with_context(company_id=sale.company_id).search([('name','=','property_stock_customer')])[0]
            #pricelist=self.env['ir.property'].with_context(company_id=sale.company_id).search([('name','=','property_product_pricelist_purchase')])[0]
            location_ref = int(customer_location.value_reference.split(',')[-1])
            #pricelist_ref = int(pricelist.value_reference.split(',')[-1])

            # print "CUSTLOC", customer_location, location_ref, type(location_ref)

            lines = self.env['sale.order.line'].search([('order_id','=',sale.id)])
            index = 0
	    partner_id = None
	    requested_delivery = None
            for line in lines:
                po = {'company_id': sale.partner_id.company_id.id,
                	  'currency_id': sale.selected_supplier.property_product_pricelist_purchase.currency_id.id,
	                  #'name': sale.name,
        	          'partner_id': sale.selected_supplier.id,
                	  'location_id': location_ref,
	                  'pricelist_id': sale.selected_supplier.property_product_pricelist_purchase.id,
        	          'invoice_method': 'manual',
                	  'dest_address_id': sale.partner_shipping_id.id,
			  'sale_order_id': sale.id,
			  'confirmed_date': None,
	                  }
                po_lines = []
		if line.product_id.product_tmpl_id.is_pack:
			if not requested_delivery:
				d_requested_date = datetime.datetime.strptime(sale.requested_date, "%Y-%m-%d").date()
				#while n_index < (n_check_top):
				#	d_index_date = d_index_date - datetime.timedelta(days=n_index)
				#	if d_index_date.weekday() in [5,6]:
				#		n_additional_days = n_additional_days + 1
				#	n_index = n_index + 1
				requested_delivery = datetime.datetime.strptime(sale.requested_date, "%Y-%m-%d").date() \
					- datetime.timedelta(days=(line.calculated_leadtime - line.manufacturing_leadtime))
				if requested_delivery.weekday() == 5:
					requested_delivery = requested_delivery - datetime.timedelta(days=1)
				if requested_delivery.weekday() == 6:
					requested_delivery = requested_delivery - datetime.timedelta(days=2)
			line_product = None
			for line_pack in line.product_id.product_tmpl_id.wk_product_pack:
        	        	if line.product_id.name.upper() in names_to_skip:
	        	            _logger.info('Not making PO line for product %s', line.product_id)
        	        	    continue
	                	else:
				    if line_pack.product_name.product_tmpl_id.ntty_id != '':
					line_product = line_pack.product_name.id
					partner_id = line_pack.product_name.supplier_id.id
       	        			# cost_unit = line.unit_cost
					pricelist = sale.selected_supplier.property_product_pricelist_purchase
					return_pricelist = pricelist.price_get(line_product, line.product_uom_qty or 1.0, partner_id or False,\
						 context = {'uom': line.product_uom.id, 'date': str(date.today())})
					cost_unit = return_pricelist[pricelist.id]
					if pricelist.currency_id.id != sale.currency_id.id:
						cost_unit = cost_unit / line.quoted_rate
					break
			# Checks MOV
			if line_product:
				suppinfo = self.env['product.supplierinfo'].search([('partner_id','=',sale.selected_supplier.id),\
							('product_tmpl_id','=',line_product.product_tmpl_id.id)])
				if suppinfo:
					if suppinfo.mov:
						if (cost_unit * line.product_uom_qty) < suppinfo.mov:
							cost_unit = suppinfo.mov / line.product_uom_qty
		else:
			if line.product_id.default_code == 'NRE':
				cost_unit = line.nre_cost
				line_product = line.product_id.id
			else:
				line_product = line.product_id.id
				pricelist = sale.selected_supplier.property_product_pricelist_purchase
				return_pricelist = pricelist.price_get( line_product, line.product_uom_qty or 1.0, sale.selected_supplier.id or False,\
				 context = {'uom': 1, 'date': str(date.today())})
				cost_unit = return_pricelist[pricelist.id]
                        d_requested_date = datetime.datetime.strptime(sale.requested_date, "%Y-%m-%d").date()
			d_requested_delivery = d_requested_date + datetime.timedelta(days=2)
			if d_requested_delivery.weekday() == 5:
				d_requested_delivery = d_requested_delivery + datetime.timedelta(days=2)
			if d_requested_delivery.weekday() == 6:
				d_requested_delivery = d_requested_delivery + datetime.timedelta(days=1)
			requested_delivery = str(d_requested_delivery)
		

	
               	vals_line = {'name': line.name,
                        'product_uom': line.product_uom.id,
                        'sale_order': sale.id,
                        'price_unit': cost_unit,
                        'leadtime': line.delay,
                        'sequence': line.sequence + index,
                        'product_qty' : line.product_uom_qty,
                        'company_id': line.company_id.id,
                        'product_id': line_product,
                        # 'date_planned': sale.requested_delivery_date, # Must be updated later.
                  }
		if requested_delivery:
			vals_line['date_planned'] = requested_delivery
		else:
                        vals_line['date_planned'] = sale.requested_delivery_date, # Must be updated later.
      	        index += 1
		po['buffer_days'] = line.buffer_days
		#po['hub_days'] = ((line.calculated_leadtime - line.manufacturing_leadtime) - line.buffer_days) - line.additional_days)
	        po['order_line'] = po_lines
		if not po['partner_id']:
			po['partner_id'] = partner_id
		if requested_delivery:
			po['requested_delivery'] = requested_delivery
        	created_po = self.env['purchase.order'].create(po)
		vals_line['order_id'] = created_po.id
		created_line = self.env['purchase.order.line'].create(vals_line)
	        #required_shipping_date = created_po.calculate_shipping_date()
        	#for line in created_po.order_line:
	        #        line.date_planned = required_shipping_date

                _logger.info('Created purchase order %s / %s', created_po, created_po.name)

    @api.one
    def _compute_manufacturing_days(self):
        if self.order_line:
            return_value = 0
            for line in self.order_line:
                return_value += line.manufacturing_leadtime
	    self.manufacturing_days = return_value

    @api.one
    def _compute_additional_days(self):
        if self.order_line:
            return_value = 0
            for line in self.order_line:
		if line.sudo().product_id.default_code != 'NRE':
	                return_value += line.additional_days
	    self.additional_days = return_value

    @api.one
    def _compute_buffer_days(self):
        if self.order_line:
            return_value = 0
            for line in self.order_line:
		if line.sudo().product_id.default_code != 'NRE':
                	return_value += line.buffer_days
	    self.buffer_days = return_value

    @api.one
    def _compute_calculated_leadtime(self):
	return_value = 0
        if self.order_line:
            return_value = 0
            for line in self.order_line:
              	return_value += line.calculated_leadtime
        self.calculated_leadtime = return_value

    @api.one
    def _compute_hub_days(self):
	return_value = 0
	for line in self.order_line:
		if line.sudo().product_id.is_pack:
                	for product in line.sudo().product_id.wk_product_pack:
                        	if product.product_name.product_tmpl_id.ntty_id == '' or \
                                	not product.product_name.product_tmpl_id.ntty_id:
                			return_value = return_value + product.product_name.sale_delay

	self.hub_days = return_value

    partner_wkng_gerber = fields.Boolean(string='Wkng Gerber',related='partner_id.wkng_gerber',readonly=True)
    wkng_gerber = fields.Boolean(string='Override Wkng Gerber',default=False)
    hub_days = fields.Integer(string='Autoline Days',compute=_compute_hub_days)
    manufacturing_days = fields.Integer(string='Manufacturing Days', compute=_compute_manufacturing_days)
    additional_days = fields.Integer(string='Additional Days', compute=_compute_additional_days)
    buffer_days = fields.Integer(string='Buffer Days', compute=_compute_buffer_days)
    calculated_leadtime = fields.Integer(string='Calculated leadtime', compute=_compute_calculated_leadtime)
    purchase_ids = fields.One2many(comodel_name='purchase.order',inverse_name='sale_order_id')

    @api.multi
    def _get_purchase_order(self):
        po_line_model = self.env['purchase.order.line']
        for order in self:
		order.purchase_orders = None

    @api.one
    def _has_purchase_order(self):
	if self.purchase_ids:
		self.has_purchase_order = True
	else:
		self.has_purchase_order = False

