from odoo import api, fields, models
import base64, xlrd
from odoo.exceptions import ValidationError
from datetime import date

class BbiScripte(models.Model):
    _inherit = "bbi.scripts"

    #repariert uom fehler nach rangieren der einheit im produkt, pauschal für alle referenzierenden entitäten
    def getProductQuantities(self):
        print("getting quants")

        products= self.env['product.product'].search([('type','=','product')])
        ausgabe = 'product_product_id;code;name;lot_id;lot_name;qty_available;qty_context_stock\n'
        n = len(products)
        print("gebe quantities aus für {} zählbare produkte".format(n))
        i=0
        for p in products:
            #hier noch fallunterscheidung, wenn ein traced artikel, dann über
            #stock.production.lot iterieren und mehrer zeilen mit product_qty und  spalte "lot_id" füllen
            i+=1
            print("parse {} von {}".format(i,n))
            lotId=''
            lotName=''
            pName=''
            if p.name:
                pName=p.name.replace(';','|').replace('\n','|')
            pCode=''
            if p.default_code:
                pCode=p.default_code.replace(';','|').replace('\n','|')
            if p.tracking == 'lot':
                lots = self.env['stock.production.lot'].search([('product_id','=',p.id)])
                if len(lots) == 0:
                    pStock = str(p.with_context({'location' : 8}).qty_available).replace('.',',')
                    lotId  = 'not given'
                    ausgabe+= "{};{};{};{};{};{};{}\n".format(p.id,pCode,pName,lotId,lotName,str(p.qty_available).replace('.',','),pStock)
                else:
                    for lot in lots:
                        lotId = lot.id
                        lotName = '###{}###'.format(lot.name)
                        ausgabe+= "{};{};{};{};{};{};{}\n".format(p.id,pCode,pName,lotId,lotName,str(lot.product_qty).replace('.',','),str(lot.product_qty).replace('.',','))
            else:
                pStock = str(p.with_context({'location' : 8}).qty_available).replace('.',',')
                ausgabe+= "{};{};{};{};{};{};{}\n".format(p.id,pCode,pName,lotId,lotName,str(p.qty_available).replace('.',','),pStock)

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'product available.csv' # Name und Format des Downloads

    #einige raises von hand löschen an offen QM vorgängen in dbeaver (pickings und moves und lines mit dieser picking_id)
    #ERST !!!!! move und move_lines, dann pickings!!!
    #picking_id in (1885,2116,2277,2705)
    #id in (1885,2116,2277,2705)


    #der none block sind quantities, diese hier von hand bereinigen
    #moves und move_lines mit location_id = 9 or location_dest_id = 9 sind quants, diese löschen
    #dabei eine MO/00613 von 9 auf 15 reparieren ind location_dest_id
    #dabei LS-OUT-2020051400090 von 9 auf 8 in location_id
    #dann quants auf location_id  =9 löschen

    #move_line und moves mist location location_dest_id = 9 von hand löschen (nur noch quant moves)
    #dabei eine MO/00613 von 9 auf 15 reparieren

    def changeBadInputPickings(self):
        print("getting bad WH/IN inputs")

        query = """ SELECT picking_id,COUNT(picking_id)
                    FROM stock_move
                    WHERE location_dest_id = 9
                    GROUP BY picking_id
                    ORDER BY picking_id"""
        self.env.cr.execute(query)
        allInputPickings=self.env.cr.fetchall()
        pickingsDone = []

        ausgabe = 'picking;name\n'
        n = len(allInputPickings)
        i=0
        for p in allInputPickings:
            i+=1

            if isinstance(p[0], int):
                pId=p[0]
                #alle WH/IN pickings zugehend reparieren
                print("parse {} von {} id {}".format(i,n,pId))
                picking = self.env['stock.picking'].search([('id','=',pId)])
                moves = self.env['stock.move'].search([('picking_id','=',pId)])
                if len(picking) == 1:
                    if 'WH/IN' in picking.name:
                        ausgabe+= "{};{}geroutet auf 8\n".format(pId,picking.name)
                        for m in moves:
                            m.update({'location_dest_id' : 8})
                            moveLine= self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.update({'location_dest_id' : 8})
                        picking.update({'location_dest_id' : 8})
                        pickingsDone.append(pId)

                    #alle LS-OUT- pickings abgehend mit input als falschem ziel reparieren
                    if 'LS-OUT-' in picking.name:
                        ausgabe+= "{};{}geroutet auf 5 (falsche dest in move_line)\n".format(pId,picking.name)
                        for m in moves:
                            m.update({'location_dest_id' : 5})
                            moveLine= self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.update({'location_dest_id' : 8})
                        picking.update({'location_dest_id' : 5})
                        pickingsDone.append(pId)

                    #alle Lager/OUT/ pickings abgehend mit input als falschem ziel reparieren
                    if 'Lager/OUT/' in picking.name:
                        ausgabe+= "{};{}geroutet auf 5 (falsche dest in move_line)\n".format(pId,picking.name)
                        for m in moves:
                            m.update({'location_dest_id' : 5})
                            moveLine= self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.update({'location_dest_id' : 5})
                        picking.update({'location_dest_id' : 5})
                        pickingsDone.append(pId)

                    #alle #WH/OUT/ pickings abgehend mit input als falschem ziel reparieren
                    if 'WH/OUT/' in picking.name:
                        ausgabe+= "{};{}geroutet auf 5 (falsche dest in move_line)\n".format(pId,picking.name)
                        for m in moves:
                            m.update({'location_dest_id' : 5})
                            moveLine= self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.update({'location_dest_id' : 5})
                        picking.update({'location_dest_id' : 5})
                        pickingsDone.append(pId)
                    #WH/QM/ retouren unlink
                    if 'WH/QM/' in picking.name:
                        ausgabe+= "{};{}gelöschte QM Retoure\n".format(pId,picking.name)
                        for m in moves:
                            m.unlink()
                            moveLine= self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.unlink()
                        picking.unlink()
                        pickingsDone.append(pId)




        ausgabe+="unbehandelte pickings...\n"
        for p in allInputPickings:
            if p[0] not in pickingsDone:
                picking = self.env['stock.picking'].search([('id','=',p[0])])
                ausgabe+= "{};{}\n".format(p[0],picking.name)

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'fixed input pickings.csv' # Name und Format des Downloads

    #auch hier offen qm buchungen von hand löschen via dbeaver ERST MOve und move lines, dann PICKINGS!!!!
    #ERST !!!!! move und move_lines, dann pickings!!!
    #picking_id in (1772,1780,1782,1784,1787,1789,1791,1793,1795,1799,1803,1804,1807,1809,1812,1818,1827,1838,1848,1855,1857,1859,1863,1865,1867,1869,1873,1876,1878,1883,1892,1903,1907,1917,1925,1931,1935,1952,1954,1956,1958,1962,1979,1984,1986,1992,2017,2022,2024,2026,2028,2030,2035,2044,2051,2052,2060,2064,2072,2091,2097,2111,2115,2119,2123,2129,2154,2163,2168,2172,2206,2251,2255,2256,2257,2259,2260,2261,2262,2263,2264,2265,2266,2267,2268,2269,2270,2271,2272,2273,2275,2276,2280,2282,2296,2297,2354,2370,2371,2375,2378,2383,2389,2391,2393,2398,2403,2410,2411,2416,2418,2421,2424,2428,2457,2459,2474,2482,2514,2516,2518,2521,2548,2553,2561,2568,2570,2577,2580,2582,2589,2590,2625,2633,2643,2651,2665,2670,2677,2679,2680,2681,2682,2690,2693,2694,2697,2701,2702,2703,2709,2710,2711,2712,2713,2714,2715,2716,2717,2718,2719,2720,2721,2722,2723,2724,2725,2726,2727,2728,2729,2730,2732,2734,1774,1776,1778,1797,1801,1814,1816,1820,1822,1824,1829,1831,1833,1835,1842,1861,1871,1880,1886,1889,1894,1896,1898,1900,1905,1909,1911,1913,1915,1919,1923,1929,1933,1941,1947,1949,1966,1977,1988,1990,1994,1996,1998,2004,2007,2014,2039,2055,2058,2076,2078,2080,2082,2084,2086,2088,2102,2104,2106,2108,2113,2121,2134,2147,2149,2151,2159,2161,2166,2170,2284,2291,2293,2295,2299,2301,2303,2305,2307,2309,2311,2313,2315,2317,2319,2321,2323,2325,2327,2329,2331,2333,2335,2337,2339,2341,2343,2345,2347,2349,2352,2356,2361,2363,2372,2373,2374,2376,2377,2381,2382,2384,2395,2399,2400,2405,2407,2432,2434,2436,2438,2440,2441,2444,2447,2450,2462,2471,2476,2480,2485,2493,2495,2498,2500,2505,2509,2512,2526,2538,2543,2544,2545,2555,2557,2565,2575,2576,2579,2585,2587,2588,2591,2592,2593,2594,2595,2596,2597,2599,2601,2604,2606,2608,2610,2611,2612,2613,2614,2615,2616,2617,2618,2619,2620,2621,2622,2623,2627,2631,2637,2641,2646,2647,2648,2654,2655,2657,2658,2663,2668,2669,2675,2676,2685,2692,2696,2700,2704,2708,2731,2733,2735,27371676,1687,1689,1691,1693,1695,1697,1699,1701,1703,1707,1709,1711,1713,1715,1717,1719,1721,1723,1725,1727,1729,1731,1733,1735,1737,1740,1742,1744,1746,1748,1750,1752,2214,1677,2387,2442,2502,1921,2061,2015,2496,2489,2699,2549,2214,1677,2387,2442,2502,1921,2061,2015,2496,2489,2699,2549)
    #id in (1772,1780,1782,1784,1787,1789,1791,1793,1795,1799,1803,1804,1807,1809,1812,1818,1827,1838,1848,1855,1857,1859,1863,1865,1867,1869,1873,1876,1878,1883,1892,1903,1907,1917,1925,1931,1935,1952,1954,1956,1958,1962,1979,1984,1986,1992,2017,2022,2024,2026,2028,2030,2035,2044,2051,2052,2060,2064,2072,2091,2097,2111,2115,2119,2123,2129,2154,2163,2168,2172,2206,2251,2255,2256,2257,2259,2260,2261,2262,2263,2264,2265,2266,2267,2268,2269,2270,2271,2272,2273,2275,2276,2280,2282,2296,2297,2354,2370,2371,2375,2378,2383,2389,2391,2393,2398,2403,2410,2411,2416,2418,2421,2424,2428,2457,2459,2474,2482,2514,2516,2518,2521,2548,2553,2561,2568,2570,2577,2580,2582,2589,2590,2625,2633,2643,2651,2665,2670,2677,2679,2680,2681,2682,2690,2693,2694,2697,2701,2702,2703,2709,2710,2711,2712,2713,2714,2715,2716,2717,2718,2719,2720,2721,2722,2723,2724,2725,2726,2727,2728,2729,2730,2732,2734,1774,1776,1778,1797,1801,1814,1816,1820,1822,1824,1829,1831,1833,1835,1842,1861,1871,1880,1886,1889,1894,1896,1898,1900,1905,1909,1911,1913,1915,1919,1923,1929,1933,1941,1947,1949,1966,1977,1988,1990,1994,1996,1998,2004,2007,2014,2039,2055,2058,2076,2078,2080,2082,2084,2086,2088,2102,2104,2106,2108,2113,2121,2134,2147,2149,2151,2159,2161,2166,2170,2284,2291,2293,2295,2299,2301,2303,2305,2307,2309,2311,2313,2315,2317,2319,2321,2323,2325,2327,2329,2331,2333,2335,2337,2339,2341,2343,2345,2347,2349,2352,2356,2361,2363,2372,2373,2374,2376,2377,2381,2382,2384,2395,2399,2400,2405,2407,2432,2434,2436,2438,2440,2441,2444,2447,2450,2462,2471,2476,2480,2485,2493,2495,2498,2500,2505,2509,2512,2526,2538,2543,2544,2545,2555,2557,2565,2575,2576,2579,2585,2587,2588,2591,2592,2593,2594,2595,2596,2597,2599,2601,2604,2606,2608,2610,2611,2612,2613,2614,2615,2616,2617,2618,2619,2620,2621,2622,2623,2627,2631,2637,2641,2646,2647,2648,2654,2655,2657,2658,2663,2668,2669,2675,2676,2685,2692,2696,2700,2704,2708,2731,2733,2735,27371676,1687,1689,1691,1693,1695,1697,1699,1701,1703,1707,1709,1711,1713,1715,1717,1719,1721,1723,1725,1727,1729,1731,1733,1735,1737,1740,1742,1744,1746,1748,1750,1752,2214,1677,2387,2442,2502,1921,2061,2015,2496,2489,2699,2549,2214,1677,2387,2442,2502,1921,2061,2015,2496,2489,2699,2549)

    def changeBadOutputPickings(self):
        print("getting bad WH/IN inputs")

        query = """ SELECT picking_id,COUNT(origin)
                    FROM stock_move
                    WHERE location_id = 9
                    GROUP BY picking_id
                    ORDER BY picking_id"""
        self.env.cr.execute(query)
        allInputPickings=self.env.cr.fetchall()
        pickingsDone = []
        doneQM = []

        ausgabe = 'picking;name\n'
        n = len(allInputPickings)
        i=0
        for p in allInputPickings:
            i+=1

            if isinstance(p[0], int):
                pId=p[0]
                #alle WH/OUT/ pickings abgehend reparieren
                print("parse {} von {} id {}".format(i,n,pId))
                picking = self.env['stock.picking'].search([('id','=',pId)])
                moves = self.env['stock.move'].search([('picking_id','=',pId)])
                if len(picking) == 1:
                    if 'WH/OUT/' in picking.name:
                        ausgabe+= "{};{}geroutet auf 8\n".format(pId,picking.name)
                        for m in moves:
                            m.update({'location_id' : 8})
                            moveLine = self.env['stock.move.line'].search([('move_id','=',m.id)])
                            moveLine.update({'location_id' : 8})
                        picking.update({'location_id' : 8})
                        pickingsDone.append(pId)

                    #WH/QM/ 2. stufe unlink
                    #if 'WH/INT/' in picking.name:
                        #ausgabe+= "{};{}gelöschte QM Stufe\n".format(pId,picking.name)
                        #for m in moves:
                        #    moveLine = self.env['stock.move.line'].search([('move_id','=',m.id)])
                        #    moveLine.unlink()
                        #    m.unlink()
                        #picking.unlink()
                        #pickingsDone.append(pId)
        #repariere false Lager/ins
        intPicking = self.env['stock.picking'].search([('picking_type_id','=',1),('location_dest_id','=',13)])
        for p in intPicking:
            ausgabe+= "{};{}korrigierter lagerquell und zielort\n".format(p.id,p.name)
            p.update({'location_dest_id':8,'location_id':4})
        #print(doneQM)
        ausgabe+="unbehandelte pickings...\n"
        for p in allInputPickings:
            if p[0] not in pickingsDone:
                picking = self.env['stock.picking'].search([('id','=',p[0])])
                ausgabe+= "{};{}\n".format(p[0],picking.name)

        raw = ausgabe.encode(encoding='cp1252', errors='replace') # String encoden
        self.myFile = base64.b64encode(raw) # binärcode mit b64 encoden
        self.myFile_file_name = 'fixed output pickings.csv' # Name und Format des Downloads

        #vorgangstyp qualitätskontrolle archivieren
        #lager für vorgangstyp retoure (lager anpassen)
