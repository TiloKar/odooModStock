from odoo import api, fields, models
import csv, base64, sys, xlrd, xlwt, datetime
from odoo.exceptions import ValidationError
from io import BytesIO, StringIO

class BbiStockLocation(models.Model):
    _name = "bbi.stock.location"
    _description = "Eigene Lagerorte als Attribute an product_template"

    name = fields.Char(store = True, required = True , string = 'Kurzbezeichnung')
    room = fields.Char(store = True, string = 'Raumbezeichnung')
    comment = fields.Char(store = True, string = 'Kommentar')
