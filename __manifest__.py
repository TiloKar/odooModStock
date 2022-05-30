# -*- coding: utf-8 -*-

{
  'name': 'bbi_mod_stock',
  'author': "Tilo Karczewski",
  'version': '0.13',
  'category': 'MRP',
  'description': """
     - Batchbuchungen aus csv als E-BOM, Mai 2022
     - Wizard Klasse für Popups, Mai 2022
     - Erweiterung Produkt um Webshopeigenschaft, umgezogen aus bbi_mod_stock in Mai 22

    """,
  'depends': [
    'base',
    'mrp',
  ],
  'data': [
    'views/mrp_bom_form_bbi.xml',
    'views/bbi_message_wizard.xml',
    'security/ir.model.access.csv',
    'views/product_template_form_view_bbi.xml',
    'views/product_template_tree_view_bbi.xml',
  ],
}
