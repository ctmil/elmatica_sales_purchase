
from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from openerp import workflow

import logging

tooling_products = ['[TOOLING]','NRE']

def find_originators(sale_ids):
    # mapping from originator to dest
    org = {}
    for order in sale_ids:
        for line in order.order_line:
            if line.originating_from:
                if not line.originating_from.id in org:
                    org[line.originating_from.id] = []
                org[line.originating_from.id].append(line.id)
                _logger.info('find_originators %s %s', line.id, org[line.originating_from.id])

    _logger.info('find_originators returning %s', org)
    return org


class sale_advance_payment_inv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    advance_payment_method = fields.Selection(selection_add=[('services', 'Invoice Tooling'),
                                                             ('delivered', 'Invoice Delivered Goods')])

    @api.multi
    def create_invoices(self):
        " copied from sale_make_invoice_advance.py "
        """ create invoices for the active sales orders """
        sale_obj = self.env['sale.order']
        act_window = self.env['ir.actions.act_window']
        #wizard = self.browse(cr, uid, ids[0], context)
        assert self._context.get('active_model') == 'sale.order'
        sale_ids = self.env['sale.order'].browse(self._context.get('active_ids', []))
        sale_ids.ensure_one()
	import pdb;pdb.set_trace()
        if self.advance_payment_method in ('all', 'services', 'delivered'):
            originators = find_originators(sale_ids)
            # Find previously invoiced lines
            def collect(line, zum=0):
                if zum:
                    assert line.invoiced_qty

                zum += line.invoiced_qty
                if not line.id in originators:
                    _logger.info('Collecting1 from %s was %d %d', line.id, line.invoiced_qty, zum)
                    return zum

                org = self.env['sale.order.line'].browse(originators[line.id])
                for o in org:
                    _logger.info('Collecting from %s for %s', o.id, line.id)
                    zum += collect(o, 0)
                    _logger.info('Collected from %s for %s = %d', o.id, line.id, zum)
                return zum

            lines = [x for x in sale_ids.order_line if x.product_id.name_template != 'info:' and not x.invoiced]
            if self.advance_payment_method == 'delivered':
                matching_lines = []
                for line in lines:
                    if line.delivered_qty and line.undelivered_qty:
                        previously_invoiced = collect(line)
                        l2 = line.copy()
                        qty_to_invoice = round(line.delivered_qty) #  - previously_invoiced)
                        assert qty_to_invoice > 0
                        l2.invoiced_qty = qty_to_invoice
                        line.product_uom_qty -= qty_to_invoice
                        l2.product_uom_qty = qty_to_invoice
                        l2.originating_from = line.id
                        l2.state = line.state
                        matching_lines.append(l2)
                    elif line.delivered_qty:
                        matching_lines.append(line)
                        
                lines = matching_lines
            elif self.advance_payment_method == 'services':
                matching_lines = []
                for line in lines:
		    import pdb;pdb.set_trace()
                    matches = [x for x in tooling_products if line.name.find(x)==0]
                    if matches:
                        matching_lines.append(line)

                lines = matching_lines
                #lines = [x for x in lines if x.name.find('[TOOLING]')!=0 ]
            if not lines:
                return {'type': 'ir.actions.act_window_close'}

            res = self.make_invoices(lines)

            # create the final invoices of the active sales orders
            ######## originalen res = sale_ids.manual_invoice()
            #res = sale_obj.manual_invoice(cr, uid, sale_ids, context)
            if self._context.get('open_invoices', False):
                return res
            return {'type': 'ir.actions.act_window_close'}

        if self.advance_payment_method == 'lines':
            # open the list view of sales order lines to invoice
            res = act_window.for_xml_id(self._cr, self._uid, 'sale', 'action_order_line_tree2', self._context)
            res['context'] = {
                'search_default_uninvoiced': 1,
                'search_default_order_id': sale_ids and sale_ids[0].id or False,
            }
            return res
        assert self.advance_payment_method in ('fixed', 'percentage')

        inv_ids = []
        for sale_id, inv_values in self._prepare_advance_invoice_vals():
            inv_ids.append(self._create_invoices(inv_values, sale_id))

        if self._context.get('open_invoices', False):
            return self.open_invoices(inv_ids)
        return {'type': 'ir.actions.act_window_close'}

