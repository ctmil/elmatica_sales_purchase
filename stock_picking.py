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

	import pdb;pdb.set_trace()
        active_id = self._context.get('active_id', None)
        assert active_id
        picking = self.env['stock.picking'].browse([active_id])[0]

        if self._context.get('active_model') == 'res.partner' and self._context.get('active_ids'):
            res.update({'partner_ids': self._context.get('active_ids')})

        reports_to_attach = [('ML', 'elmatica_invoice.report_mat_label'),
                             ('DOC', 'elmatica_invoice.report_doc'),
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
