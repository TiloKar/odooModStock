from odoo import api, fields, models
import csv, base64, sys, xlrd
from odoo.exceptions import ValidationError
from odoo import http
from odoo.http import request, content_disposition, route

class Picking(models.Model):
    _inherit = 'stock.picking'

    external_origin = fields.Char(
        string = 'externe LS-Nr.',
        help='LS-Nr des Lieferanten',
        store=True,
        readonly=False,)

    #bereitet Liste aus Elo csv Stückliste vor
    def makeLinesFromEbom(self):

        try:
            raw = base64.b64decode(self.csv_file) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')

        raw_list = raw.split(b'\n') #zerlegen zeilenweise
        str_list = [] # wird ein 2-dimensionales array aller zelleneinträge als rohstrings
        rowNum = 0 # zähler zeilen
        errors = 0
        message ="";
        for row in raw_list:
            if rowNum > 1:
                if len(row) > 0: # nicht kopfzeile und leere ignorieren
                    str_row = row.decode(encoding='cp1252', errors='replace').split(';') # spaltenweise zerlegen, mbcs ist für windows PCs optimiert
                    if len(str_row) > 2:
                        str_list.append(str_row)
                    else:
                        errors += 1
                        message += " file-row " + str(str_row) + " not valid\n"
            rowNum+= 1

        if len(str_list) == 0 :
            errors+= 1
            message += " file has no lines\n"

        list = []
        if errors == 0:
            rowNum = 0 # zähler zeilen
            for row in str_list: #normiren auf zwei-spaltenliste
                entry = []
                entry.append(row[1])
                entry.append(row[2].replace('\n',''))
                list.append(entry)
                if len(list[rowNum][0]) == 0:
                    errors += 1
                    message += " file-row " + str(rowNum) + " quantity not set\n"
                elif len(list[rowNum][1]) == 0:
                    errors += 1
                    message += " file-row " + str(rowNum) + " scancode not set\n"
                rowNum+= 1

        if errors != 0:
            raise ValidationError(message)
        else:
            return self.addLinesFromBom(list)

    def addLinesFromBom(self,list):

        datasets = [] # wird ein array mit den anzuhängenden dictionaries
        errors = 0
        message ="";
        if len(self.move_line_ids_without_package ) != 0:
            errors += 1
            message += " transfer-list must be empty for batch import\n"
        else:
            for row in list:
                result = self.env['product.template'].search([('default_code', '=', row[1])]) # product_template id.ermitteln
                if len(result) > 0:
                    result_p = self.env['product.product'].search([('product_tmpl_id', '=', result[0].id)]) # passend product_product.id ermitteln
                    #output_str = str(result[0].id) + "-"
                    datasets.append({
                        'name' : "[{}]{}".format(result[0].default_code,result_p[0].name),
                        'product_id' : result_p[0].id,
                        'product_uom_qty': int(row[0]),
                        'product_uom': result[0].uom_id.id,
                        'picking_id': self.id,
                        'location_id' :self.location_id.id,
                        'location_dest_id' :self.location_dest_id.id,

                    })
                else:
                    errors += 1
                    message += " unknown scancode: " + row[1] + "\n"
                    #output_str = output_str + "0-"

        #self.output = message
        if errors == 0:
            self.env['stock.move'].create(datasets)
            self.output = len(self.move_line_ids_without_package)
            return True
        else:
            raise ValidationError(message)
