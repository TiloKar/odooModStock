# -*- coding: utf-8 -*-

{
  'name': 'bbi_mod_stock',
  'author': "Hanning Liu, Tilo Karczewski",
  'version': '0.20',
  'category': 'MRP',
  'description': """
     - Batchbuchungen aus csv als E-BOM, Mai 2022
     - Wizard Klasse für Popups, Mai 2022, entfernt und gegen raise validationError() in Juni 22 ersetzt
     - Erweiterung Produkt um Webshopeigenschaft, umgezogen aus bbi_mod_stock in Mai 22
     - mbcs an linux systemen als codec nicht verfügbar, cp1252?, gefixt Juni 22
     - Verriegelung Batchbuchung gegen bereits gefüllte BOM_lines ,Juni 22
     - Ersatzteil Haken am Produkt, Lagerorte, Juni 22
     - Schweißdoku in BOM Kopf und produktberührend in BOM-line, anzeige in MO line als "MCert",
      wenn in bom-line gehakt und im MO kopf gehakt, per xpath in Qweb pdf angezeigt, Juni 22
     - Blendenmanagement mit virtuellen Produkten, Verriegelung gegen bereits erzeugungte,
      strukturgleiche BOMs,als allgemeine rekursive Methode auf deep compare von BOMS realisiert,
      Hinweis auf Duplikat-Produkt in validation error, Juni 22, fixes im Juni
     - K-BOM import aus excel ergänzt, constraits auf bom_line ids eingekürzt, Juni 22
     - E-BOM auch für interne transfers verfügbar, Juni 22
     - Inventurbestand aus Excel-Zählung kann über Form ansicht der bbi lagerorte automatisch in Inventurpostion "to apply" verwandelt werden
     - TODO handling von losnummern bereits beim zählen vorbereiten und auch automatisch parsen
     - offene Projektbedarfe aus terminal werden für das erste Projektblatt automatisch als MO übernommen
     - TODO noch schleife über alle Blätter rum und die MO noch bestätigen (eventuell gleich die Methoden identifizieren und nutzen...)
     - TODO für bedarfe kopieren und weiterhin mit move_lines versehen bis zum abschließen
     - TODO Hinweise auf erweiterte Wareneingangskontrolle im internen Transfer von WH/Input klarer stylen
     - TODO Erstzteil Export aus BOM einer explodierten stückliste für den Baum (eventuell auch matrixdarstellung mit Struktur)
     - TODO Idee strukturstücklisten aus solid works parsen
     - TODO idee: auto-anlegen der produkte unter K-Referenz und name bei auswahl von autoCreateProducts

    """,
  'depends': [
    'base',
    'mrp',
  ],
  'data': [
    'views/mrp_bom_form_bbi.xml',
    'views/mrp_production_form_bbi.xml',
    'security/ir.model.access.csv',
    'views/product_template_form_view_bbi.xml',
    'views/product_template_tree_view_bbi.xml',
    'views/bbi_location_menu_action.xml',
    'report/report_mrp_order.xml',
    'report/report_barcode_label.xml',
    'report/report_action_label.xml',
    'views/bbi_stock_move_line_quants_uid.xml',
    'views/product_template_search_view_bbi.xml',
    'views/bbi_stock_warehouse_orderpoint_tree_editable.xml',
    'views/bbi_stock_warehouse_orderpoint_reorder_search.xml',
  ],
}
