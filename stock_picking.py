import base64
from collections import OrderedDict
from openerp import api, models, exceptions, fields,  _
import openerp.addons.decimal_precision as dp
from openerp.exceptions import Warning

import logging
from iso3166 import countries
_logger = logging.getLogger(__name__)


class mail_compose_message(models.TransientModel):
    #_inherit = 'email_template.wizard.mail_compose_message'
    #_name = 'elmatica_invoice.mail.compose.message'
    _inherit = 'mail.compose.message'
    _description = 'Email compose wizard for supplier'

    @api.model
    def default_get(self, all_fields):
        res = super(mail_compose_message, self).default_get(all_fields)
        if self._context.get('active_model') != 'stock.picking':
            return res

        active_id = self._context.get('active_id', None)
        assert active_id
        picking = self.env['stock.picking'].browse([active_id])[0]

        if self._context.get('active_model') == 'res.partner' and self._context.get('active_ids'):
            res.update({'partner_ids': self._context.get('active_ids')})

        #reports_to_attach = [('ML', 'elmatica_invoice.report_mat_label'),
        #                     ('DOC', 'elmatica_sales_purchase.report_letter_of_conformity'),
        #                     ]
        reports_to_attach = [('SL', 'elmatica_wms.report_stock_picking_shipping_label_template'),
                             ('PS', 'elmatica_wms.report_stock_picking_20_template'),
                             ('DOC', 'elmatica_sales_purchase.elm_report_doc_document'),
                             ]
        # reports_to_attach = ['elmatica_wms.report_stock_shipping_label_action',]
        attachments = []
        for fileprefix, reportname in reports_to_attach:
            options_data = {}
            try:
                report = self.env['ir.actions.report.xml'].search([('report_name','=',reportname)])[0]
            except:
                raise Warning(_('Unable to find report %s' % reportname))

            if report.report_type == 'qweb-pdf':
                reportdata =  self.env['report'].get_pdf(picking, reportname, data=options_data)
            elif report.report_type == 'qweb-html':
                reportdata =  self.env['report'].get_html(picking, reportname, data=options_data)
            else:
                raise Warning('Unsupported report type for report %s: %s' % (reportname, report.report_type))

            suffix = report.report_type.split('-')[-1]
            po = picking.po_id

            filename = '%s-%s-%s.%s' % (fileprefix, po.name, picking.name, suffix)
            attachment_id = self.env['ir.attachment'].create({
                    'name': filename, # ufile.filename,
                    'datas': base64.encodestring(reportdata),
                    'datas_fname': filename,
                    #'res_model': model,
                    #'res_id': int(id)
                }) # , self._context)

            #attachment_id.wizard_id = self.id
            attachments.append(attachment_id.id)

        res['attachment_ids'] = [(6, 0, attachments)]


        #assert False
        return res



class stock_picking(models.Model):
    _inherit = 'stock.picking'

    @api.one
    def get_customer_name(self):
	return_value = 'N/A'
	if self.origin:
	    purchase_order = self.env['purchase.order'].search([('name','=',self.origin)])
	    if purchase_order:
		if purchase_order[0].sale_id:
		    return_value = purchase_order[0].sale_id.partner_id.name
	return return_value  

    @api.one
    def get_customer_part_number(self):
	if self.move_lines:
	    for move_line in self.move_lines:
	        if move_line.product_id.ntty_id != '':
		    self.customer_part_number = move_line.product_id.default_code

    @api.one
    def get_customer_part_name(self):
	if self.move_lines:
	    for move_line in self.move_lines:
	        if move_line.product_id.ntty_id != '':
		    self.customer_part_name = move_line.product_id.name_template

    @api.one
    def get_quantity(self):
	return_value = 0
	if self.move_lines:
	    for move_line in self.move_lines:
		if move_line.product_id.ntty_id != '':
		    return_value = return_value + move_line.product_qty
	self.quantity = return_value

    @api.one
    def get_rohs(self):
	return 'no'

    @api.one
    def get_ul(self):
	return 'no'

    @api.one
    def _compute_dhl_declared_value(self):
	return_value = 0
	#import pdb;pdb.set_trace()
	if self.move_lines and self.sale_id:
	    for move_line in self.move_lines:
		if  move_line.product_id.ntty_id:
			for sale_line in self.sale_id.order_line:
				if sale_line.product_id.is_pack:
					for product_pack in sale_line.product_id.wk_product_pack:
						if product_pack.product_name.id == move_line.product_id.id:
						        return_value = return_value + (sale_line.unit_cost * sale_line.product_uom_qty)
	self.dhl_declared_value = return_value

    customer_part_number = fields.Char('Customer Part Number',compute=get_customer_part_number)
    elmatica_part_number = fields.Char('Customer Part Number',compute=get_customer_part_number)
    customer_part_name = fields.Char('Customer Part Name',compute=get_customer_part_name)
    quantity = fields.Integer('Quantity',compute=get_quantity)
    dhl_declared_value = fields.Integer(string='DHL DeclaredValue',compute=_compute_dhl_declared_value)

 
    @api.multi
    def action_send_shipping_info(self):
        """
        Copied from action_invoice_sent.Opens up mail compose dialog
        """
        if 'template' in self._context:
            template_name = self._context['template']
        else:
            template_name = 'elmatica_invoice.email_template_shipping_information'

        title_window = self._context.get('title_window', _('Comment'))

        template = self.env.ref(template_name, False)
        assert template, 'Unable to find %s' % template_name
        assert len(self) == 1, 'This option should only be used for a single id at a time.'

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='stock.picking',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
            #mark_invoice_as_sent=False,
            #default_is_log=True,
            #is_log=True,
            internal_partners_only=True,
        )
        return {
            'name': title_window,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            #'res_model': 'elmatica_invoice.mail.compose.message', # 'compose.message', # 'mail.compose.message',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx}


