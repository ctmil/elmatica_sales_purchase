
from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning
from openerp import workflow

import logging
from situation import prepare_invoice

tooling_products = ['[TOOLING]','NRE']

_logger = logging.getLogger(__name__)


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

    """
    @api.multi
    def create_service_invoices(self):
        self.ensure_one()

        sale_ids = self._context.get('active_ids', [])
        assert len(sale_ids) == 1
        sale = self.env['sale.order'].browse(sale_ids)
        service_lines = [x for x in sale.order_line if x.product_id.type == 'service']
        inv = self.make_invoices(service_lines)
        if self._context.get('open_invoices', False):
            return inv
        return {'type': 'ir.actions.act_window_close'}

    @api.v7
    def create_invoices(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        if wizard.advance_payment_method == 'services':
            return wizard.create_service_invoices()
        else:
            return super(sale_advance_payment_inv, self).create_invoices(cr, uid, ids, context)
    """
    # copied from sale_line_invoice.py
    def make_invoices(self, lines):
        """
             To make invoices.

             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs
             @param context: A standard dictionary

             @return: A dictionary which of fields with values.

        """

        res = False
        invoices = {}

        #TODO: merge with sale.py/make_invoice
        def make_invoice(order, lines):
            """
                 To make invoices.

                 @param order:
                 @param lines:

                 @return:

            """
            inv = self._prepare_invoice(order, lines)
            inv = prepare_invoice(order, inv) # Set our stuff


            prop = order.env['ir.property']
            rec_dom = [('name', '=', 'property_account_receivable'), ('company_id', '=', inv['company_id'])]
            pay_dom = [('name', '=', 'property_account_payable'), ('company_id', '=', inv['company_id'])]
            res_dom = [('res_id', '=', 'res.partner,%s' % order.partner_id.id)]
            rec_prop = prop.search(rec_dom + res_dom) or prop.search(rec_dom)[0]
            pay_prop = prop.search(pay_dom + res_dom) or prop.search(pay_dom)[0]
            rec_account = rec_prop.get_by_record(rec_prop)
            pay_account = pay_prop.get_by_record(pay_prop)

            inv['account_id'] = rec_account.id
            inv_id = self.env['account.invoice'].create(inv)
            return inv_id

        sales_order_line_obj = self.env['sale.order.line']
        sales_order_obj = self.env['sale.order']
        for line in lines:
            if (not line.invoiced) and (line.state not in ('draft', 'cancel')):
                if not line.order_id in invoices:
                    invoices[line.order_id] = []
                line_id = line.invoice_line_create()
                for lid in line_id:
                    invoices[line.order_id].append(lid)
        for order, il in invoices.items():
            res = make_invoice(order, il)
            self._cr.execute("INSERT INTO sale_order_invoice_rel "\
                    "(order_id,invoice_id) values (%s,%s)", (order.id, res.id))
            #sales_order_obj.invalidate_cache(['invoice_ids'], [order.id])
            order.invalidate_cache(['invoice_ids'])
            flag = True
            #sales_order_obj.message_post([order.id], body=_("Invoice created"))
            order.message_post(body=_("Invoice for services created"))
            data_sale = sales_order_obj.browse(order.id)
            for line in data_sale.order_line:
                if not line.invoiced and line.state != 'cancel':
                    flag = False
                    break
            if flag:
                line.order_id.write({'state': 'progress'})
                workflow.trg_validate(self._uid, 'sale.order', order.id, 'all_lines', self._cr)

        if not invoices:
            raise exceptions.Warning(_('Warning!'), _('Invoice cannot be created for this Sales Order Line due to one of the following reasons:\n1.The state of this sales order line is either "draft" or "cancel"!\n2.The Sales Order Line is Invoiced!'))
        if self._context.get('open_invoices', False):
            return self.open_invoices(res)
        return {'type': 'ir.actions.act_window_close'}

    def _prepare_invoice(self, cr, uid, order, lines, context=None):
        a = order.partner_id.property_account_receivable.id
        if order.partner_id and order.partner_id.property_payment_term.id:
            pay_term = order.partner_id.property_payment_term.id
        else:
            pay_term = False
        return {
            'name': order.client_order_ref or '',
            'origin': order.name,
            'type': 'out_invoice',
            'reference': "P%dSO%d" % (order.partner_id.id, order.id),
            'account_id': a,
            'partner_id': order.partner_invoice_id.id,
            'invoice_line': [(6, 0, lines)],
            'currency_id' : order.pricelist_id.currency_id.id,
            'comment': order.note,
            'payment_term': pay_term,
            'fiscal_position': order.fiscal_position.id or order.partner_id.property_account_position.id,
            'user_id': order.user_id and order.user_id.id or False,
            'company_id': order.company_id and order.company_id.id or False,
            'date_invoice': fields.date.today(),
            'section_id': order.section_id.id,
        }

    def open_invoices(self, invoice_ids):
        """ open a view on one of the given invoice_ids """
        ir_model_data = self.env['ir.model.data']
        form_res = ir_model_data.get_object_reference('account', 'invoice_form')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference('account', 'invoice_tree')
        tree_id = tree_res and tree_res[1] or False

        if isinstance(invoice_ids[0], models.Model):
            invoice = invoice_ids[0].id
        else:
            invoice = invoice_ids[0]

        return {
            'name': _('Invoice'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'account.invoice',
            'res_id': invoice,
            'view_id': False,
            'views': [(form_id, 'form'), (tree_id, 'tree')],
            'context': {'type': 'out_invoice'},
            'type': 'ir.actions.act_window',
        }
