import libxml2
from enum import Enum
from math import floor
from textextents import SplitTextIntoLines
import math

def set_extent (node:libxml2.xmlNode, pos:tuple, dimensions:tuple):
    node.setProp("x", str(round(pos[0], 3)))
    node.setProp("y", str(round(pos[1], 3)))
    node.setProp("width", str(round(dimensions[0], 3)))
    node.setProp("height", str(round(dimensions[1], 3)))

def add_nl (node:libxml2.xmlNode):
    nl = libxml2.newText("\n\n")
    node.addNextSibling(nl)

def new_svg_document (width, height, unit:str, root_tag = "svg") -> tuple:
    svg = libxml2.newDoc("1.0")
    root = libxml2.newNode(root_tag)
    root.setProp("width", str(width) + unit)
    root.setProp("height", str(height) + unit)
    root.setProp("viewport", "0 0 " + str(width) + " " + str(height))
    root.setProp("viewBox", "0 0 " + str(width) + " " + str(height))
    svg.setRootElement(root)
    return (svg, root)

def get_child_node_by_tag (node, tag):
    path = './/*[name()="' + tag + '"]'
#   print("## XPath: '" + path + "'")
    l = node.xpathEval(path)
#   print("   -> " + str(len(l)) + " Ergebnisse")
    return l

def get_child_node_by_id (node, node_id):
    path = './/*[@id="' + node_id + '"]'
#   print("## XPath: '" + path + "'")
    l = node.xpathEval(path)
#   print("   -> " + str(len(l)) + " Ergebnisse")
    return l

def style_string_override(style, key, value):
    kvpairs = style.split(';')
    lookfor = key + ':'
    pairslist = []

    i = 0
    for kv in kvpairs:
        if kv.startswith(lookfor):
            pairslist.append(i)

        i += 1

    if len(pairslist) == 0:
        # Es gab die Property vorher noch nicht
        kvpairs.append(key + ':' + value)
    elif len(pairslist) != 1:
        raise Exception("Die Property " + key + " kommt mehrfach im stylestring vor")
    else:
        i = pairslist[0]
        kvpairs[i] = key + ':' + value

    newstyle = ""
    for i in kvpairs:
        newstyle += i
        newstyle += ';'
    return newstyle

def style_string_get (style_string, key):
    kvpairs = style_string.split(';')
    lookfor = key + ":"

    for kv in kvpairs:
        if kv.startswith(lookfor):
            index = kv.index(":")
            return kv[index+1:]

    raise Exception("Style-Schlüssel '{}' nicht gefunden".format(key))

def translate_x (items, document = None, delta_x = 0, x_coord = None, adjust_width = False):
    if type(items) == list and type(items[0]) == str:
        itemslist = []
        for item in items:
            assert(document != None)
            itemslist.append(get_child_node_by_id(document, item)[0])
    elif type(item) == list:
        itemslist = items
    elif type(item) == str:
        itemslist = get_child_node_by_id(document, item)
        assert(document != None)
    else:
        itemslist = [item]

    for item in itemslist:
        oldx = float(item.prop("x"))
        if x_coord != None:
            item.setProp("x", str(x_coord))
            if adjust_width:
                item.setProp("width", str(float(item.prop('width')) + oldx - x_coord))
        else:
            item.setProp("x", str(oldx + delta_x))
            if adjust_width:
                item.setProp("width", str(float(item.prop('width')) + delta_x))

class Orientation(Enum):
    VERTICAL = 1
    HORIZONTAL = 2

class Position(Enum):
    START = 1
    MIDDLE = 2
    END = 3
    BEGIN = START
    CENTER = MIDDLE

    def to_string (self):
        if self == Position.START:
            return "start"
        elif self == Position.MIDDLE:
            return "middle"
        else:
            return "end"

class SvgNode:
    def __init__ (self, name, relative_position=(0,0)):
        self.name = name
        self.x = relative_position[0]
        self.y = relative_position[1]
        self.properties = {}
        self.style_properties = {}
        self.children = []

    def render (self) -> libxml2.xmlNode:
        node = libxml2.newNode(self.name)

        # Harvest style property
        propstring = ""
        for key, value in self.style_properties.items():
            propstring += key + ":" + value + ";"
        if "" != propstring:
            self.set_prop("style", propstring)

        # XXX this if clause is an experiment
        if self.name != "g":
            node.setProp("x", str(round(self.x, 2)))
            node.setProp("y", str(round(self.y, 2)))
        for key, value in self.properties.items():
            node.setProp(key, str(value))

        for child in self.children:
            # Die Koordinaten des Kindknotens müssen zuvor angepasst werden
            child.x += self.x
            child.y += self.y
            node.addChild(child.render())

        add_nl(node)
        return node

    def set_prop (self, name, value):
        self.properties[name] = value
        return self

    def set_style_property (self, key:str, value:str):
        self.style_properties[key] = value
        return self

    def add_child (self, child):
        self.children.append(child)
        return self

    def set_style_template (self, style:dict):
        for key, value in style.items():
            self.set_style_property(key, value)

class SvgTextNode(SvgNode):
    """ Repräsentation eines Textknotens. Man bemerke: Die y-Koordinate bezieht sich auf die Baseline, welche wiederum von der Schriftgröße abhängt; die vom User gesetze y-Koordinate bezieht sich hingegen auf die obere Kante. Folglich wird erst beim .render()-Aufruf die y-Koordinate um die Schriftgröße erhöht."""

    USE_BOX_DEBUGGER = False

    def __init__ (self, text, alignment=Position.START):
        super().__init__ ("text")
        self.text = text
        self.align = alignment
        self.style_properties["font-size"] = "3.53" # 10pt
        self.style_properties["font-family"] =  "Nimbus Sans L"
        self.set_prop("baseline", "top")

    # 1 pt = 0.353mm
    def set_font_size (self, size, unit="pt"):
        if unit == "mm" or unit == "px":
            self.set_style_property("font-size", str(size))
        elif unit == "cm":
            self.set_style_property("font-size", str(float(size)*0.1))
        elif unit == "pt":
            self.set_style_property("font-size", str(round(float(size)*0.353, 3)))
        else:
            raise Exception("Nicht unterstützte Einheit '" + unit + "'; mm, px, cm oder pt verwenden")
        return self

    def render (self) -> libxml2.xmlNode:
        self.set_prop("dy", float(self.style_properties["font-size"]))
        self.set_style_property("text-anchor", self.align.to_string())

        # Actually render
        node = super().render()
        node.addChild(libxml2.newText(self.text))
        return node

class SvgEquiarealBox(SvgNode):
    """Sammelt SvgNode-Elemente, denen jeweils dieselbe Breite oder Höhe zugewiesen wird."""
    
    def __init__ (self, dimensions:tuple, orientation):
        super().__init__('g')
        self.width = dimensions[0]
        self.height = dimensions[1]
        for i in dimensions:
            assert (i > 0)
        self.orientation = orientation
        self.hmargin = 0
        self.vmargin = 0
        self.padding = 0
        self.children = []
    
    def set_style_property (self, key, value):
        raise TypeError("SvgEquiarealBox does not implement style properties")

    def subdivision_size (self, count):
        """Die Ausdehnungen jedes einzelnen Elements bei gleichmäßiger Unterteilung in @count Stücke.
        Dabei ist offenbar Gesamtlänge = n*Einzellänge + (n-1)*Padding <=> Einzellänge = (Gesamtlänge + Padding)/n - Padding"""
        dimen = 0
        if self.orientation == Orientation.HORIZONTAL:
            dimen = self.width - 2*self.hmargin
        else:
            dimen = self.height - 2*self.vmargin

        singledimen = (dimen + self.padding)/count - self.padding

        if self.orientation == Orientation.HORIZONTAL:
            return (singledimen, self.height - 2*self.vmargin)
        else:
            return (self.width - 2*self.hmargin, singledimen)

    def subdivide (self, count):
        """Erstelle @count verschiedene Kind-SvgEquiarealBox-Knoten mit der passenden Breite und Höhe"""
        if len(self.children) != 0:
            raise Exception("There are already " + str(len(self.children)) + " children nodes")
        
        dimensions = self.subdivision_size(count)
        for i in range(count):
            self.children.append(SvgEquiarealBox(dimensions, Orientation.HORIZONTAL))

#       print("dbg: subdivide (" + str(round(self.width)) + ", " + str(round(self.height)) + ") into " + str(count) + " slices of (" + str(round(dimensions[0])) + ", " + str(round(dimensions[1])) + ")")
        return dimensions

    def subdivide_simple (self, count):
        """Wie subdivide(), jedoch erstelle <g>-SvgNodes"""
        if len(self.children) != 0:
            raise Exception("There are already children nodes")
        
        dimensions = self.subdivision_size(count)
        for i in range(count):
            self.children.append(SvgNode("g"))

        return dimensions

    def subdivide_by_approx_size (self, size:float):
        """Erstelle verschiedene Kind-Knoten wie subdivide(); jedoch berechne die Anzahl derselben, sodass sie ungefähr zur gegebenen Größe passt. Die @size ist dabei die Länge oder Breite, je nach orientation.
        Gibt die Anzahl der erzeugten Kindknoten zurück."""
        # Gesamtlänge = n*Einzellänge + (n-1)*Padding <=> n = (Gesamt+Padding)/(Einzel+Padding)

        total = 0
        if self.orientation == Orientation.HORIZONTAL:
            total = self.width - 2*self.hmargin
        else:
            total = self.height - 2*self.vmargin

        count = (total + self.padding) / (size + self.padding)
        return self.subdivide(floor(count))

    def render (self) -> libxml2.xmlNode:
        basex = self.x + self.hmargin
        basey = self.y + self.vmargin

        node = libxml2.newNode("g")
        if len(self.children) == 0:
            return node

        item_extent = 0
        if self.orientation == Orientation.HORIZONTAL:
            item_extent = self.subdivision_size(len(self.children))[0]
        else:
            item_extent = self.subdivision_size(len(self.children))[1]

        for child in self.children:
            child.x += basex
            child.y += basey
            chnode = child.render()

            if self.orientation == Orientation.HORIZONTAL:
                basex += item_extent
                basex += self.padding
            else:
                basey += item_extent
                basey += self.padding

            node.addChild(chnode)

        if self.USE_BOX_DEBUGGER == True:
            outer = SvgNode("rect", (self.x, self.y))
            outer.set_prop("width", str(self.width)).set_prop("height", str(self.height)).set_prop("style", "fill-opacity:0;stroke-width:1;stroke:#5aeb5b;")
            inner = SvgNode("rect", (self.x + self.hmargin, self.y + self.vmargin))
            inner.set_prop("width", str(self.width - 2*self.hmargin)).set_prop("height", str(self.height - 2*self.vmargin)).set_prop("style", "fill-opacity:0;stroke-width:1;stroke:#813ace;")
            node.addChild(outer.render())
            node.addChild(inner.render())

        add_nl(node)
        return node

###
# Textsatzfunktionen.
# Benötigen die pwsvgxml-Klassen eigentlich gar nicht, aber liegen hier, um outgesourct werden zu können.
###

def set_text_content_from_text2 (node:libxml2.xmlNode, text:str, font = "Quicksand", ptsize = 13, lineskip = 1, parskip = 2, markup = False) -> tuple:
    """
    Liest auch die Höhe des Knotens aus. Wenn der Text nicht ganz in den
    Knoten hereinpasst, gibt die Funktion den Rest des Textes zurück.
    Diese Funktion gibt ein Tupel zurück: (Remaining_String, Text_height). Wenn nur der String von Interesse ist,
    kann die Hilfsfunktion set_text_content_from_text genutzt werden.
    """
    width = round(float(node.prop("width")))
    
    #assert(text != None)
    if text == None:
        # Ist das eine gute Idee?
        return ("", 0)

    # Einige Makros wurden eingebaut. Das Makro §§ für Überschriften wird unten aufgelöst:
    text = text.replace('\n§sprüche', "\n§§~ /// :D ///").replace(' -- ', ' – ')
    remaining = None
    try:
        i = text.index('\n§pagebreak')
        k = i + len('\n§pagebreak')
        remaining = text[k:]
        text = text[:i]
    except Exception as ex:
        pass

    layout = SplitTextIntoLines(text, font, ptsize, math.ceil(width), markup)
    layout.start()

    xcoord = float(node.prop("x"))
    is_first_line = True
    pxsize = ptsize * 0.353

    remaining_height = float(node.prop("height")) - (pxsize*0.4) - parskip
    height = 0
    empty_height = 0

    while True:
        data = layout.pop_line()
        if data == None:
            return (remaining, height)
        (line, new_paragraph) = data

        dy = ((lineskip * pxsize) + (new_paragraph * parskip) * (not is_first_line))
        if not line or line.strip() == '':
            empty_height += dy * (not is_first_line)
            # Leere <tspan>-Knoten zählen bei dy nicht mit. Sie werden später aufgerechnet.
#           print("## skip empty line")
            continue

        dy += empty_height
        empty_height = 0
        remaining_height -= dy
        height += dy

        tspan = libxml2.newNode("tspan")
        tspan.setProp("dy", str(round(dy, 3)))
        tspan.setProp("x", str(xcoord))
        if line.startswith('§§~'): # Formatierungs-Makros
            line = line[3:].strip()
            tspan.setProp("style", "font-weight:bold;text-align:center;text-anchor:center;")
            tspan.setProp("x", str(xcoord + width/2))
        elif line.startswith('§§'):
            line = line[2:].strip()
            tspan.setProp("style", "font-weight:bold;")
        tspan.setContent(line)
        node.addChild(tspan)

        is_first_line = False

        if remaining_height < 0:
            # Den verbliebenen Text harvesten
            remstring = ""
            while True:
                part = layout.pop_line()
                if part == None:
                    break
                else:
                    if part[1] == True:
                        remstring += "\n"
                    remstring += part[0].strip() + " "
            if remaining:
                return (remstring + remaining, height)
            else:
                return (remstring, height)

def set_text_content_from_text (node:libxml2.xmlNode, text:str, font = "Quicksand", ptsize = 13, lineskip = 1, parskip = 2, markup = False) -> str:
    """ Wie set_text_content_from_text2(), aber diese Funktion gibt nur den Remaining_String zurück. """
    return set_text_content_from_text2(node, text, font, ptsize, lineskip, parskip, markup)[0]

def set_text_content_from_file (node:libxml2.xmlNode, filename:str, font = "Quicksand", ptsize = 13, lineskip = 1, parskip = 2, markup = False) -> str:
    """
    Liest auch die Höhe des Knotens aus. Wenn der Text nicht ganz in den
    Knoten hereinpasst, gibt die Funktion den Rest des Textes zurück.
    """
    width = round(float(node.prop("width")))
    
    if filename == '/dev/null' or filename == '%':
        return set_text_content_from_text(node, "", font, ptsize, lineskip, parskip, markup)

    with open(filename) as fd:
        try:
            text = fd.read()
        except Exception as ex:
            print("Lesefehler bei Datei " + filename)
            raise ex

    return set_text_content_from_text (node, text, font, ptsize, lineskip, parskip, markup)


def set_text_content_get_height (node:libxml2.xmlNode, text:str, font = "Quicksand", ptsize = 13, lineskip = 1, parskip = 2, markup = False) -> int:
    """
    Berechnet aufgrund der Eingabe die nötige Höhe des Knotens.
    Die Breite wird aus den Knoteneigenschaften ausgelesen
    """
    width = round(float(node.prop("width")))
    text = text.replace('§sprüche', "§§ --- :D ---")

    layout = SplitTextIntoLines(text = text, font = font, ptsize = ptsize, width = width, markup = markup)
    layout.start()

    xcoord = node.prop("x")
    is_first_line = True
    pxsize = ptsize * 0.353

    height = 0
    empty_height = 0

    while True:
        data = layout.pop_line()
        if data == None:
            break
        (line, new_paragraph) = data
        
        dy = ((lineskip * pxsize) + (new_paragraph * parskip * (not is_first_line)))
        height += dy
        if line == '':
            empty_height += dy
            # Leere <tspan>-Knoten zählen bei dy nicht mit. Sie werden später aufgerechnet.
            continue
        else:
            dy += empty_height
            empty_height = 0

        tspan = libxml2.newNode("tspan")
        tspan.setProp("dy", str(round(dy, 3)))
        tspan.setProp("x", xcoord)
        if line.startswith('§§~'): # Formatierungs-Makros
            line = line[3:].strip()
            tspan.setProp("style", "font-weight:bold;text-align:center;text-anchor:center;")
            tspan.setProp("x", xcoord + width/2)
        elif line.startswith('§§'):
            line = line[2:].strip()
            tspan.setProp("style", "font-weight:bold;")
        tspan.setContent(line)
        node.addChild(tspan)

        is_first_line = False

    return height - empty_height

def set_text_content_from_text_twocolumn (node:libxml2.xmlNode, text:str, font = "Quicksand", ptsize = 13, lineskip = 1, parskip = 2, markup = False, columnsep = 2) -> str:
    """
    Liest auch die Höhe des Knotens aus. Wenn der Text nicht ganz in den
    Knoten hereinpasst, gibt die Funktion den Rest des Textes zurück.
    """
    node.setName('g')

    pos = (float(node.prop('x')), float(node.prop('y')))
    dim = (float(node.prop('width')), float(node.prop('height')))
    coldim = ((dim[0] - columnsep)/2, dim[1])
    col1pos = pos
    col2pos = (pos[0] + coldim[0] + columnsep, pos[1])

    col1 = libxml2.newNode('text')
    col2 = libxml2.newNode('text')
    set_extent(col1, col1pos, coldim)
    set_extent(col2, col2pos, coldim)

    remaining = set_text_content_from_text (col1, text, font, ptsize, lineskip, parskip, markup)
    if remaining and remaining.strip() != '':
        remaining = set_text_content_from_text (col2, remaining.strip(), font, ptsize, lineskip, parskip, markup)

    node.addChild(col1)
    node.addChild(col2)

    return remaining


