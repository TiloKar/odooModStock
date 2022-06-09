from odoo import api, fields, models
import csv, base64, sys, xlrd
from odoo.exceptions import ValidationError

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    csv_file = fields.Binary(string='CSV File')

    output = fields.Char(string='internal output')

    autoCreateProducts = fields.Boolean(
        string = 'auto create',
        default=False,
        help='Check this, if batch read should create missing products automatically, handle with care!',
        store=False,
        readonly=False,)

    #bereitet Liste aus Konstruktions exceldatei Stückliste vor
    def makeLinesFromKbom(self):
        try:
            raw = base64.decodestring(self.csv_file) #vorbereitung binary
        except:
            raise ValidationError('Datei erst hochladen!')
        try:
            book = xlrd.open_workbook(file_contents=raw)
        except:
            raise ValidationError('Datei Fehler!')

        sheet = book.sheets()[0]

        list = []
        for i in range(sheet.nrows):
            if i < 2:
                continue
            entry = []
            entry.append("{:.0f}".format(sheet.cell(i, 1).value))
            entry.append(str(sheet.cell(i, 2).value).replace('\n',''))
            list.append(entry)

        return self.addLinesFromBom(list)

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
        if len(self.bom_line_ids) != 0:
            errors += 1
            message += " BOM must be empty for batch import\n"
        else:
            for row in list:
                result = self.env['product.template'].search([('default_code', '=', row[1])]) # product_template id.ermitteln
                if len(result) > 0:
                    result_p = self.env['product.product'].search([('product_tmpl_id', '=', result[0].id)]) # passend product_product.id ermitteln
                    #output_str = str(result[0].id) + "-"
                    datasets.append({
                        'product_tmpl_id': result[0].id,
                        'product_id' : result_p[0].id,
                        'product_qty': int(row[0]),
                        'product_uom_id': result[0].uom_id.id,
                        'bom_id': self.id
                    })
                else:
                    errors += 1
                    message += " unknown scancode: " + row[1] + "\n"
                    #output_str = output_str + "0-"

        #self.output = message
        if errors == 0:
            self.env['mrp.bom.line'].create(datasets)
            self.output = len(self.bom_line_ids)
            return True
        else:
            raise ValidationError(message)

    #ausformulierung der Prüfbedingung für bom.lines, interne id und qty müssen gleich sein
    def bom_line_duplicates_condition(self, bom, line):
        for bom_line in bom.bom_line_ids:
            if self.bom_line_ids[line].product_qty == bom_line.product_qty and self.bom_line_ids[line].product_tmpl_id == bom_line.product_tmpl_id:
                return True
        return False

    #prüft rekursiv, ob die BOM schon strukturgleich existiert
    def check_bom_duplicates_rek(self, boms, line):
        rek_boms = boms.filtered(lambda bom: self.bom_line_duplicates_condition(bom, line))
        if len(rek_boms) == 0:
            return False #abbruch, die kandidatenliste ist leer, obwohl noch nicht alle lines geprüft worden
        if (line + 1) < len(self.bom_line_ids):
            return self.check_bom_duplicates_rek(rek_boms, line + 1) #falls noch ungeprüfte lines existieren und kandidaten verfügbar sind
        #wenn der code bis hierhin kommt (alle lines sind durch und es gibt noch Kandidaten) dann Exception!
        message = "bom duplicates exists for: \n\n"
        for bom in rek_boms :
            message += "scancode: " + str(bom.product_tmpl_id.default_code) + " name: " + str(bom.product_tmpl_id.name) + "\n"
        raise ValidationError(str(message))

    @api.constrains('bom_line_ids')
    def _check_bom_duplicates(self):
        #alle kandidaten in boms aufnehmen die gleiche zeilenzahl haben und nicht die bom selbst sind
        boms = self.env['mrp.bom'].search([]).filtered(lambda b: len(b.bom_line_ids) == len(self.bom_line_ids) and b.product_tmpl_id.id != self.product_tmpl_id.id)
        # bei leere boms gleich hier raus sonst in rekusion einsteigen
        #if len(self.bom_line_ids) == 0:  #kollidiert mit batch import
        #    raise ValidationError(str('leere Stücklisten machen so gar keinen Sinn!'))
        if len(boms) == 0:
            return False
        return self.check_bom_duplicates_rek(boms, 0)
