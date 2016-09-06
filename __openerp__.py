{
    'name': 'Elmatica - Sales/Purchase',
    'category': 'Sales',
    'version': '0.2',
    'depends': ['elmatica_sales_customizations','elmatica_invoice','elmatica_purchase_flow','sale_crm','email_template','elmatica_wms','dhl_delivery_carrier'],
    'data': [
	'sale_view.xml',
	'declaration_of_conformity.xml',
	'po20_report.xml'
    ],
    'demo': [
    ],
    'qweb': [],
    # 'css': ['static/src/css/styles.css',],
    'installable': True,
}
