import os
import sys
import re
from datetime import date, datetime, timezone
from pwsvgxml import *
from math import sqrt

"""
Dieses Skript wurde aus dem Rankingordner importiert
und für die Zwecke des CMS angepasst
"""

class RankingContent:
    """
    Verarbeitet eine Hitliste mit einer Schlüsseldatei.
    Die Initialisierung mit RankingContent(hitlist_filename, keys_filename)
    erstellt direkt die zum Rendern benötigten Daten.

    Es ist nach der Initialisierung zunächst ::get_cats_cnt() abzufragen,
    damit ausreichend viele Seiten erzeugt werden.

    Anschließend kann jeweils mit ::render_page ein Knoten angegeben werden,
    in den eine Seite hineingeschrieben werden kann.
    """
    def __init__ (self, hitlist_file, key_file):
        self.hitlist_file = hitlist_file
        self.key_file = key_file
        self._render_offset = 0

        ###
        # Die einzelnen Keys den Namen zuordnen
        ###
        self.keys2namesmap = {}
        keysfile = open(key_file, 'r')
        rx = re.compile('([0-9]+): "([^"]+)"; "([^"]+)"')

        for line in keysfile:
            m = rx.match(line)
            if not m:
                print("Fehlerhafte Zeile in der Aufschlüsselungsdatei " + keysfilename + ":")
                print("  --> " + line)
                print("  Erwartete Syntax: <key>: \"<Name>\"; \"<Kategorie>\"")
            else:
                key = m.group(1)
                name = m.group(2)

                self.keys2namesmap[int(key)] = name;
        
        ###
        # Die Kategorien einlesen
        ###
        self.categories = [] # list<CatHarvest>
        with open(hitlist_file) as infile:
            state = 0 # Status des Parsers
                      #   0: Neutral
                      #   1: Zuletzt Titel einer Kategorie eingelesen
                      #   2: Zuletzt eine 'm'-Position eingelesen
                      #   3: Zuletzt eine 'f'-Position eingelesen
                      #   4: Zuletzt eine 'p'-Position eingelesen

            rx = re.compile(' (.)#([0-9]): ([0-9.]+) ([0-9]+) ([0-9.]+)')
            cnt = 1
            lineno = 1
            catharvest = None

            for line in infile:
                m = rx.match(line)

                if m and m.group(1) == 'f':
                    if state == 4 or state == 0:
                        print("Illegal: von state " + str(state) + " eine f-Position (Z. " + str(lineno) + ")")
                        continue

                    catharvest.addResult('f', self.name_for_key(m.group(3)), m.group(5))
                    #rint("debug: name_for_key(" + m.group(3) + ") => " + name_for_key(m.group(3)))
                    state = 3

                elif m and m.group(1) == 'm':
                    if state == 4 or state == 0:
                        print("Illegal: von state " + str(state) + " eine m-Position (Z. " + str(lineno) + ")")

                    catharvest.addResult('m', self.name_for_key(m.group(3)), m.group(5))
                    state = 2

                elif m and m.group(1) == 'p':
                    if state != 4 and state != 1:
                        print("Illegal: von state " + str(state) + " eine p-Position (Z. " + str(lineno) + ")")
                    pairkeys = m.group(3).split(".")
                    catharvest.addResult('p', self.name_for_key(pairkeys[0]) + " und " + self.name_for_key(pairkeys[1]), m.group(5))
                    state = 4

                elif not m:
                    if catharvest != None:
                        self.categories.append(catharvest)

                    catharvest = CatHarvest(line.replace('\-', '').replace("\n", ""))

                    cnt += 1
                    state = 1

                lineno += 1

    def get_cats_cnt (self):
        return len(self.categories)

    def name_for_key (self, key):
        ikey = int(key)
        if not ikey in self.keys2namesmap:
            print("?? name_for_key: Unbekannter Schlüssel " + str(key))
            return str(key)
        else:
            return self.keys2namesmap[ikey]

    def render_page (self, node:libxml2.xmlNode) -> int:
        """
        Verarbeitet soviele Kategorien, wie in den gegebenen @node
        hineinpassen.
        Rückgabewert: Anzahl der noch verbleibenden Kategorien
        """
        # Zwei Spalten im widget erzeugen
        width = float(node.prop("width"))
        height = float(node.prop("height"))
        col1 = SvgEquiarealBox(((width-4)/2, height), Orientation.VERTICAL)
        col2 = SvgEquiarealBox(((width-4)/2, height), Orientation.VERTICAL)
        count = col1.subdivide_by_approx_size(35)
        col2.subdivide_by_approx_size(35)

        # Beginne, die einzelnen Kategorien zu verarbeiten
        for box in col1.children:
            cat = self.categories[self._render_offset]
            cat.saveIn(box)

            self._render_offset += 1
            if self._render_offset >= len(self.categories):
                break

        if self._render_offset < len(self.categories):
            for box in col2.children:
                cat = self.categories[self._render_offset]
                cat.saveIn(box)

                self._render_offset += 1
                if self._render_offset >= len(self.categories):
                    break

        x = float(node.prop('x'))
        y = float(node.prop('y'))
#        col1.set_prop('x', x)
#        col2.set_prop('y', y)
#        col1.set_prop('x', x + width/2)
#        col2.set_prop('y', y)
        col1.x = x
        col1.y = y
        col2.x = x + (width/2) + 2
        col2.y = y
        node.addChild(col1.render())
        node.addChild(col2.render())

        return len(self.categories) - self._render_offset


CHART_BLOCK_HEIGHT = 3
def make_score_rect (max_width, width_rate, base_x):
    rect = SvgNode("rect", (base_x, 0))
    
    #new_width_rate = sqrt(2*abs(float(width_rate)) - float(width_rate)**2)
    new_width_rate = abs(float(width_rate) - 0.8 + 1/((float(width_rate)-0.5)**2 +1))
    
    width = float(max_width)*float(new_width_rate)
    if float(width_rate) < 0:
        rect.x -= width
    rect.set_prop("width", str(round(width, 3)))
    rect.set_prop("height", str(CHART_BLOCK_HEIGHT))
    return rect

MAX_RESULTS_PER_CATEGORY = 5
SvgEquiarealBox.USE_BOX_DEBUGGER = False

###
# Eine Klasse, um Ergebnisdaten zu einer Kategorie zu harvesten
# und in svg zu schreiben
###
class CatHarvest:
    def __init__ (self, catname):
        self.category_name = catname
        self.mres = []
        self.wres = []
        self.pres = []

    def addResult (self, gender, name, score):
        if gender == 'w' or gender == 'f':
            list = self.wres
        elif gender == 'm':
            list = self.mres
        else:
            list = self.pres

        list.append([name, score])

    def saveIn (self, node:SvgEquiarealBox):
        node.orientation = Orientation.VERTICAL
        line_dimension = node.subdivide_simple(MAX_RESULTS_PER_CATEGORY+1)
        
        heading = SvgTextNode(self.category_name, Position.CENTER)
        heading.x = node.width/2
        heading.set_font_size(13, "pt")
        heading.set_style_property("font-family", "Lato")
        heading.set_style_property("font-weight", "bold")
        node.children[0].add_child(heading)
        
        if len(self.pres) == 0:
            self._saveIn_mw(node, line_dimension)
        else:
            self._saveIn_p(node, line_dimension)
        
    def _saveIn_mw (self, node, line_dimension):
        for i in range(1, MAX_RESULTS_PER_CATEGORY+1):
            g = node.children[i]
            
            try:
                name = self.mres[i-1][0]
                score = self.mres[i-1][1]
                rect = make_score_rect(line_dimension[0]/2, -1*float(score), line_dimension[0]/2)
#               rect.set_style_property("fill", "#f111ff")
                rect.set_style_property("fill", "#ff2b8c")
                g.add_child(rect)
                #g.add_child(SvgTextNode(name, Position.START).set_font_size(1.4 * CHART_BLOCK_HEIGHT, "px"))
                text = SvgTextNode(name, Position.START)
                text.set_font_size(line_dimension[1]*0.7, "px")
                text.set_style_property('font-family', 'Lato')
                g.add_child(text)
            except IndexError:
                pass
            
            try:
                name = self.wres[i-1][0]
                score = self.wres[i-1][1]
                rect = make_score_rect(line_dimension[0]/2, score, line_dimension[0]/2)
                rect.set_style_property("fill", "#11bbff")
                g.add_child(rect)
                text = SvgTextNode(name, Position.END)
                # text.set_font_size(1.4 * CHART_BLOCK_HEIGHT, "px")
                text.set_font_size(line_dimension[1]*0.7, "px")
                text.set_style_property('font-family', 'Lato')
                text.x += line_dimension[0]
                g.add_child(text)
            except IndexError:
                pass
                
    def _saveIn_p (self, node, line_dimension):
        for i in range(1, MAX_RESULTS_PER_CATEGORY+1):
            g = node.children[i]
            try:
                name = self.pres[i-1][0]
                score = self.pres[i-1][1]
                
                rect = make_score_rect(line_dimension[0], score, line_dimension[0]/2)
                rect.set_style_property("fill", "#6bc111")
                length = float(rect.properties['width'])/2
                rect.x -= length
                g.add_child(rect)
                
                text = SvgTextNode(name, Position.CENTER)
                #text.set_font_size(1.4 * CHART_BLOCK_HEIGHT, "px")
                text.set_font_size(line_dimension[1]*0.7, "px")
                text.set_style_property("font-family", "Lato")
                text.x += line_dimension[0]/2
                g.add_child(text)
            except IndexError:
                pass
    
    
    def saveInSvg (self, groupnode):
        raise Exception("Method deprecated, use CatHarvest::saveIn()")

def page_setup(width, height):
    """Unterteile die Seite in zwei Teilseiten, erstelle je 14 Ergebnisboxen und gib das Gesamt-Element und die Boxen zurück"""
    page = SvgEquiarealBox((width, height), Orientation.HORIZONTAL)
    page.subdivide(2)
    
    tiny_boxes = []
    
    for i in range(2):
        side = page.children[i]
        side.hmargin = 0.04*float(width)
        side.vmargin = 0.04*float(height)
        side.padding = 0.03*float(width)
        side.orientation = Orientation.HORIZONTAL
        
        side.subdivide(2)
        
        for j in range(2):
            subside = side.children[j]
            subside.orientation = Orientation.VERTICAL
            subside.subdivide(7)
            
            for box in subside.children:
                tiny_boxes.append(box)

    return (page, tiny_boxes)

