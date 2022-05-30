# -*- coding: utf-8 -*-
# bbi Customisation für Batchbuchungen aus csv als interner Transferauftrag auf Kommilager
# @author: Tilo K
# @date:    April 2022
#

{
  'name': 'bbi_mod_bom',
  'version': '0.12',
  'category': 'MRP',
  'description': """
     - Batchbuchungen aus csv als BOM
     - Wizard Klasse für Popups

    """,
  'depends': [
    'base',
    'mrp',
  ],
  'data': [
    'views/mrp_bom_form_bbi.xml',
    'views/bbi_message_wizard.xml',
    'security/ir.model.access.csv',
  ],
}
