# -*- coding: utf-8 -*-
# bbi Customisation für Batchbuchungen aus csv als interner Transferauftrag auf Kommilager
# @author: Tilo K
# @date:    April 2022
#

{
  'name': 'bbi mod bom tilo',
  'version': '0.10',
  'category': 'MRP',
  'description': """
     - Batchbuchungen aus csv als BOM

    """,
  'depends': [
    'base',
    'mrp',
  ],
  'data': [
    'views/mrp_bom_form_bbi.xml',
  ],
}
