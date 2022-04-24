# -*- coding: utf-8 -*-
# bbi Customisation für Batchbuchungen aus csv als interner Transferauftrag auf Kommilager
# @author: Tilo K
# @date:    April 2022
#

{
  'name': 'bbi mod stock 1',
  'version': '0.1',
  'category': 'Stock',
  'description': """
     - Batchbuchungen aus csv als interner Transferauftrag auf Kommilager

    """,
  'depends': [
    'base',
    'stock',
  ],
  'data': [
    'views/stock_view_picking_form_bbi.xml',
  ],
}
