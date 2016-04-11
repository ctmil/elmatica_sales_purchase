from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp

import logging
import datetime

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
            if not sale.requested_delivery_date:
                raise exceptions.ValidationError(_('Requested delivery date not set for sales order %s' % sale.name))
            if not sale.state in ['progress','manual']:
                raise exceptions.ValidationError(_('Order should be confirmed in order to create POs'))

            customer_location = self.env['ir.property'].with_context(company_id=sale.company_id).search([('name','=','property_stock_customer')])[0]
            pricelist = self.env['ir.property'].with_context(company_id=sale.company_id).search([('name','=','property_product_pricelist_purchase')])[0]
            location_ref = int(customer_location.value_reference.split(',')[-1])
            pricelist_ref = int(pricelist.value_reference.split(',')[-1])

            # print "CUSTLOC", customer_location, location_ref, type(location_ref)

            lines = self.env['sale.order.line'].search([('order_id','=',sale.id)])
            index = 0
	    partner_id = None
            for line in lines:
                po = {'company_id': sale.company_id.id,
                	  'currency_id': sale.currency_id.id,
	                  #'name': sale.name,
        	          'partner_id': sale.selected_supplier.id,
                	  'location_id': location_ref,
	                  'pricelist_id': pricelist_ref,
        	          'invoice_method': 'manual',
                	  'dest_address_id': sale.partner_shipping_id.id,
			  'sale_order_id': sale.id,
	                  }
                po_lines = []
		if line.product_id.product_tmpl_id.is_pack:
			for line_pack in line.product_id.product_tmpl_id.wk_product_pack:
        	        	if line.product_id.name.upper() in names_to_skip:
	        	            _logger.info('Not making PO line for product %s', line.product_id)
        	        	    continue
	                	else:
				    if line_pack.product_name.product_tmpl_id.ntty_id != '':
					line_product = line_pack.product_name.id
					partner_id = line_pack.product_name.supplier_id.id
					break
		else:
			line_product = line.product_id.id
				

       	        cost_unit = line.unit_cost

               	vals_line = {'name': line.name,
                        'product_uom': line.product_uom.id,
                        'sale_order': sale.id,
                        'price_unit': cost_unit,
                        'leadtime': line.delay,
                        'sequence': line.sequence + index,
                        'product_qty' : line.product_uom_qty,
                        'company_id': line.company_id.id,
                        'product_id': line_product,
                        'date_planned': sale.requested_delivery_date, # Must be updated later.
                  }
      	        index += 1

	        po['order_line'] = po_lines
		if not po['partner_id']:
			po['partner_id'] = partner_id
        	created_po = self.env['purchase.order'].create(po)
		vals_line['order_id'] = created_po.id
		created_line = self.env['purchase.order.line'].create(vals_line)
	        required_shipping_date = created_po.calculate_shipping_date()
        	for line in created_po.order_line:
	                line.date_planned = required_shipping_date

                _logger.info('Created purchase order %s / %s', created_po, created_po.name)


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
	
