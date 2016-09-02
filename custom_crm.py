# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import models, fields, api, _
from openerp.osv import osv, fields
from datetime import datetime
from dateutil import parser
from datetime import date

	
class crm_make_sale(osv.osv_memory):
    """ Make sale  order for crm """

    _inherit = "crm.make.sale"
    _description = "Make sales"

    def makeOrder(self, cr, uid, ids, context=None):
	"""
        This function  create Quotation on given case.
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of crm make sales' ids
        @param context: A standard dictionary for contextual values
        @return: Dictionary value of created sales order.
        """
        # update context: if come from phonecall, default state values can make the quote crash lp:1017353
        context = dict(context or {})
        context.pop('default_state', False)        
        
        case_obj = self.pool.get('crm.lead')
        sale_obj = self.pool.get('sale.order')
	sale_line_obj = self.pool.get('sale.order.line')
        partner_obj = self.pool.get('res.partner')
        data = context and context.get('active_ids', []) or []

        for make in self.browse(cr, uid, ids, context=context):
            partner = make.partner_id
            if not partner:
                 raise osv.except_osv(_('Insufficient Data!'), _('No customer defined for this opportunity.'))
            partner_addr = partner_obj.address_get(cr, uid, [partner.id],
                    ['default', 'invoice', 'delivery', 'contact'])
            pricelist = partner.property_product_pricelist.id
            fpos = partner.property_account_position and partner.property_account_position.id or False
            payment_term = partner.property_payment_term and partner.property_payment_term.id or False
            new_ids = []
            for case in case_obj.browse(cr, uid, data, context=context):
		product_name = case.product_name.id 		
	        original_contact = None
		if not partner and case.partner_id:
		    if case.partner_id.is_company:
	                    partner = case.partner_id
		    else:
	                    partner = case.parent_id.partner_id
			    original_contact = case.partner_id.id
                    fpos = partner.property_account_position and partner.property_account_position.id or False
                    payment_term = partner.property_payment_term and partner.property_payment_term.id or False
                    partner_addr = partner_obj.address_get(cr, uid, [partner.id],
                            ['default', 'invoice', 'delivery', 'contact'])
                    pricelist = partner.property_product_pricelist.id
                if not case.requested_date:
		    requested_date = str(date.today())
		else:
		    requested_date = case.requested_date
                    # raise osv.except_osv(_('Insufficient Data!'), _('No requested_date for this opportunity.'))
                if False in partner_addr.values():
                    raise osv.except_osv(_('Insufficient Data!'), _('No address(es) defined for this customer.'))

		if partner:
			if not partner.is_company:
				partner = partner.parent_id
			        original_contact = case.partner_id.id
		if partner.wkng_gerber or case.product_name.wkng_gerber:
			wkng_gerber = True
		else:
			wkng_gerber = False
                vals = {
                    'origin': ('Opportunity: %s') % str(case.id),
                    'section_id': case.section_id and case.section_id.id or False,
                    'categ_ids': [(6, 0, [categ_id.id for categ_id in case.categ_ids])],
                    'partner_id': partner.id,
		    'opportunity_id': case.id,
                    'pricelist_id': pricelist,
                    'partner_invoice_id': partner_addr['invoice'],
                    'partner_shipping_id': partner_addr['delivery'],
                    'date_order': fields.datetime.now(),
                    'fiscal_position': fpos,
                    'payment_term':payment_term,
		    'requested_date': requested_date,
		    'requested_delivery_date': requested_date,
		    'customer_project': case.customer_project,
		    'technical_contact': case.technical_contact.id,
		    'procurement_contact': case.procurement_contact.id,
		    'original_contact': original_contact,
                    'note': sale_obj.get_salenote(cr, uid, [case.id], partner.id, context=context),
		    'wkng_gerber': wkng_gerber,
                }
                if partner.id:
                    vals['user_id'] = partner.user_id and partner.user_id.id or uid
                if partner.sale_warn_msg:
                    vals['custom_message'] = partner.sale_warn_msg
                new_id = sale_obj.create(cr, uid, vals, context=context)
                sale_order = sale_obj.browse(cr, uid, new_id, context=context)
		sale_line_obj.create(cr,uid,{'order_id':new_id,'product_id':product_name},context=None)
                case_obj.write(cr, uid, [case.id], {'ref': 'sale.order,%s' % new_id})
	        # result =  super(sale_order, self).onchange_partner_id(cr, uid, [sale_order.id], partner.id, context=context)
	        result = sale_order.onchange_partner_id(partner.id, context=context)

                new_ids.append(new_id)
                message = ("Opportunity has been <b>converted</b> to the quotation <em>%s</em>.") % (sale_order.name)
                case.message_post(body=message)
            if make.close:
                case_obj.case_mark_won(cr, uid, data, context=context)
            if not new_ids:
                return {'type': 'ir.actions.act_window_close'}
	    view_id = self.pool.get('ir.ui.view').search(cr,uid,[('name','=','sale.order.form')],order='id asc',limit=1)
	    if view_id:
		view_id = view_id
	    else:
		view_id = False
            if len(new_ids)<=1:
                value = {
                    'domain': str([('id', 'in', new_ids)]),
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'sale.order',
                    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name' : ('Quotation'),
                    'res_id': new_ids and new_ids[0]
                }
            else:
                value = {
                    'domain': str([('id', 'in', new_ids)]),
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'res_model': 'sale.order',
                    #'view_id': 'sale.view_order_form',
		    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name' : ('Quotation'),
                    'res_id': new_ids
                }
            return value
	
class crm_lead2opportunity_partner(osv.osv_memory):
    _inherit = 'crm.lead2opportunity.partner'

    _columns = {
	'qty': fields.integer('Quantity',default=1,required=True)
	}

    def action_apply(self, cr, uid, ids, context=None):
        """
        Convert lead to opportunity or merge lead and opportunity and open
        the freshly created opportunity view.
        """
        if context is None:
            context = {}

        lead_obj = self.pool['crm.lead']
        partner_obj = self.pool['res.partner']

        w = self.browse(cr, uid, ids, context=context)[0]
        opp_ids = [o.id for o in w.opportunity_ids]
	#import pdb;pdb.set_trace()
	vals = {
            'section_id': w.section_id.id,
	    'customer_project': w.customer_project,
        }
        if w.partner_id:
            vals['partner_id'] = w.partner_id.id
        if w.name == 'merge':
            lead_id = lead_obj.merge_opportunity(cr, uid, opp_ids, context=context)
            lead_ids = [lead_id]
            lead = lead_obj.read(cr, uid, lead_id, ['type', 'user_id'], context=context)
            if lead['type'] == "lead":
                context = dict(context, active_ids=lead_ids)
                vals.update({'lead_ids': lead_ids, 'user_ids': [w.user_id.id]})
                self._convert_opportunity(cr, uid, ids, vals, context=context)
            elif not context.get('no_force_assignation') or not lead['user_id']:
                vals.update({'user_id': w.user_id.id})
                lead_obj.write(cr, uid, lead_id, vals, context=context)
        else:
	    n_qty = w.qty
	    if n_qty < 1:
		n_qty = 1
            lead_ids = context.get('active_ids', [])
	    temp_lead_id = lead_ids[0]
	    lead = lead_obj.browse(cr,uid,temp_lead_id)
	    if lead.partner_id.is_company:
		if lead.partner_id.technical_contact:
			vals['technical_contact'] = lead.partner_id.technical_contact.id
		if lead.partner_id.procurement_contact:
			vals['procurement_contact'] = lead.partner_id.procurement_contact.id
	    else:
		if lead.partner_id.technical_contact:
			vals['technical_contact'] = lead.partner_id.technical_contact.id
		else:
	    		if lead.partner_id.parent_id.technical_contact:
				vals['technical_contact'] = lead.partner_id.parent_id.technical_contact.id
		if lead.partner_id.procurement_contact:
			vals['procurement_contact'] = lead.partner_id.procurement_contact.id
		else:
		    	if lead.partner_id.parent_id.procurement_contact:
				vals['procurement_contact'] = lead.partner_id.parent_id.procurement_contact.id
	    if lead.product_name:
		if lead.product_name.product_tmpl_id.ntty_id:
			vals['ntty_id'] = lead.product_name.product_tmpl_id.ntty_id
	    if 'section_id' not in vals.keys():
		#stage_id = self.pool.get('crm.case.stage').search(cr,uid,[('name','=','TD Unassigned')])
		stage_id = self.pool.get('crm.case.stage').search(cr,uid,[('sequence','=',10)])
		if stage_id:
			vals['stage_id'] = stage_id[0]
	    else:
		#stage_id = self.pool.get('crm.case.stage').search(cr,uid,[('name','=','TD Unassigned')])
		team = self.pool.get('crm.case.section').browse(cr,uid,vals['section_id'])
		if team.name == 'Technical' and 'user_id' not in vals.keys():
			stage_id = self.pool.get('crm.case.stage').search(cr,uid,[('sequence','=',10)])
			if stage_id:
				vals['stage_id'] = stage_id[0]
	    original_name = lead.name
	    vals['name'] = lead.name + ' - 1 of ' + str(n_qty)
	    #if w.title_action:
		#vals['title_action'] = w.title_action
	    #if w.date_action:
		#vals['date_action'] = w.date_action
            #lead_obj.write(cr, uid, temp_lead_id, vals, context=context)
	    temp_lead_ids = [temp_lead_id]
	    for index in range(n_qty - 1):
		    name = ''
		    for lead in self.pool.get('crm.lead').browse(cr,uid,lead_ids):
			name = original_name
		    # name = name + ' - ' + str(index+1) + ' of ' + str(n_qty - 1)
		    name = name + ' - ' + str(index+2) + ' of ' + str(n_qty)
		    lead_id = self.pool.get('crm.lead').copy(cr,uid,temp_lead_id)
		    # This is where we copy attachments
		    attachment_ids = self.pool.get('ir.attachment').search(cr,uid,[('res_id','=',temp_lead_id),('res_model','=','crm.lead')])
		    for attachment_id in attachment_ids:
			attach_id = self.pool.get('ir.attachment').copy(cr,uid,attachment_id)
			vals_attachment = {
				'res_id': lead_id,
				}
			return_id = self.pool.get('ir.attachment').write(cr,uid,[attach_id],vals_attachment)
		    return_id = self.pool.get('crm.lead').write(cr,uid,[lead_id],{'name':name})
		    temp_lead_ids.append(lead_id)
       	    vals.update({'lead_ids': temp_lead_ids, 'user_ids': [w.user_id.id]})
	    #del vals['title_action']
	    #del vals['date_action']
            self._convert_opportunity(cr, uid, ids, vals, context=context)
            # self._convert_opportunity(cr, uid, temp_lead_ids, vals, context=context)
       	    for lead in lead_obj.browse(cr, uid, lead_ids, context=context):
                if lead.partner_id and lead.partner_id.user_id != lead.user_id:
       	            partner_obj.write(cr, uid, [lead.partner_id.id], {'user_id': lead.user_id.id}, context=context)
		vals = {
        	    'section_id': w.section_id.id,
		    'customer_project': w.customer_project,
        	}
	        if w.title_action:
		    vals['title_action'] = w.title_action
	        if w.date_action:
		    vals['date_action'] = w.date_action
		lead.write(vals)
		

        return self.pool.get('crm.lead').redirect_opportunity_view(cr, uid, lead_ids[0], context=context)

