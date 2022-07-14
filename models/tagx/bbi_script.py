from odoo import api, fields, models
import csv, base64, sys, xlrd, xlwt, datetime
from odoo.exceptions import ValidationError
from io import BytesIO, StringIO

class BbiScripte(models.Model):
    _name = "bbi.scripts"
    _description = "Skripte für TagX und danach"

    name = fields.Char(store = True, required = True , string = 'Script Report Bezeichnung')

    myFile = fields.Binary(string='Datei zum verarbeiten')
    myFile_file_name = fields.Char(String='Name')
