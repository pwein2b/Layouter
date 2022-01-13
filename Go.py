#!/usr/bin/python3
from pwsvgxml import *
from GoMacros import *
import libxml2
from PIL import Image
import sys
import traceback
import pprint
from textextents import SplitTextIntoLines
import math
from pathlib import Path
from pprint import pprint, pformat
import re
import colorhelper
import importlib

default_text_style = "font-style:normal;font-size:4.5px;line-height:1;font-family:Quicksand;-inkscape-font-specification:'Quicksand, Normal';text-align:end;letter-spacing:0px;word-spacing:0px;white-space:pre;"
default_text_style_template = {
        'font-size': '4.5px',
        'font-family': 'Quicksand',
        'text-align': 'end'}
content_text_style = "font-style:normal;font-size:4.5px;line-height:1;font-family:Lato,Roboto,sans-serif;-inkscape-font-specification:'Quicksand, Normal';text-align:end;letter-spacing:0px;word-spacing:0px;white-space:pre;"
content_text_style_template = {
        'font-size': '4.5px',
        'font-family': 'Lato, Roboto, sans-serif',
        'text-align': 'end'}

###
# Wrapper für libxml2-Dokumente, die nicht mit pwsvgxml erstellt wurden
###
def load_svg_with_context (filename:str, context) -> libxml2.xmlDoc:
    doc = libxml2.parseFile(filename)
    
    # für Bilder muss ein weiterer Namespace geladen werden
    root = doc.getRootElement()
    root.setProp('xmlns:xlink', 'http://www.w3.org/1999/xlink')

    try:
        colorbox = get_child_node_by_id (doc, 'colorbox')[0]
        newstyle = style_string_override(colorbox.prop("style"), "fill", context.colorbox)
        colorbox.setProp('style', newstyle)
    except Exception as ex:
        #context.message_for_current_page("Kann die Farbe der colorbox nicht setzen. " + filename)
        #print("   (" + str(ex) + ")")
        pass

    try:
        pageno = get_child_node_by_id (doc, 'pageno')[0]
        pageno.setContent(str(context.pageno))
    except Exception as ex:
        context.message_for_current_page("Kann die Seitenzahl nicht setzen")
        print("(" + str(ex) + ")")

    return doc

def harvest_options (options:list) -> str:
    """ An verschiedenen Stellen werden Strings nach Leerzeichen gesplittet. Andernorts müssen sie wieder zusammengesetzt
    werden, mit Leerzeichen zwischen den einzelnen Tokens. Diese Funktion hilft aus. """
    result = ""
    for token in options:
        result += token + " "

#   print("## harvest_options. n={:} -> '".format(len(options)) + result[0:-1] + "'")
    return result[0:-1]

def get_headlinetspan (doc:libxml2.xmlNode):
    try:
        node = get_child_node_by_id(doc, 'headlinetspan')[0]
        return node
    except IndexError:
        try:
            node = get_child_node_by_id(doc, 'headline')[0]
            return get_child_node_by_tag(node, 'tspan')[0]
        except IndexError:
            raise Exception('Kann den Knoten headlinetspan überhaupt nicht finden.')

def strip_unit_float (text:str)->float:
    rx = re.compile('([0-9.,]+)')
    m  = rx.match(text)
    if m == None:
        raise Exception("Der Text " + text + " kann nicht als Dezimalbruch mit Einheitensuffix interpretiert werden")

    return float(m.group(1))

def right_or_left (pageno, postfix = '.svg'):
    if pageno % 2:
        return "Rechts" + postfix
    else:
        return "Links" + postfix

def get_file_content (filename):
    with open(filename) as fd:
        return fd.read()

def calculate_image_dimension (image_filename, preferred_width = None, preferred_height = None, force_portrait = False, max_height = False, max_width = False, prefer_natural_dimension = False):
    try:
        img = Image.open(image_filename)
        origsize = img.size

        rotate = 0
        if force_portrait and origsize[1] < origsize[0]:
            origsize = (origsize[1], origsize[0])
            rotate = 90

        if prefer_natural_dimension:
            factor = 1.0
        else:
            if preferred_width != None:
                factor = float(preferred_width)/float(origsize[0])
            elif preferred_height != None:
                factor = float(preferred_height)/float(origsize[1])
            else:
                factor = 1.0

            if factor != 1.0 and factor > 0.02:
                factor = factor * 0.99

#       if rotate != 0:
#           # Vertauschen der Dimensionen wieder rückgängig machen, damit der aufrufende Code die Kontrolle hat
#           origsize = (origsize[1], origsize[0])

        if max_width and (origsize[0]*factor)>max_width:
            return calculate_image_dimension (image_filename, preferred_width = max_width, preferred_height = preferred_height, force_portrait = force_portrait, max_height = max_height, max_width = max_width)
        if max_height and (origsize[1]*factor)>max_height:
            return calculate_image_dimension (image_filename, preferred_width = preferred_width, preferred_height = max_height, force_portrait = force_portrait, max_height = max_height, max_width = factor * origsize[0])

        return (factor * origsize[0], factor * origsize[1], rotate)
    except FileNotFoundError:
        print(" | Fehler: Bilddatei '" + image_filename + "' nicht gefunden")
        print("   Setze Standardgröße")
        if preferred_width != None:
            return (preferred_width, preferred_width, 0)
        elif preferred_height != None:
            return (preferred_height, preferred_height, 0)
        else:
            return (50,50)
    except RecursionError:
        print(" | Rekursionsfehler in calculate_image_dimension mit '" + image_filename + "'")
        print("   preferred_width: {}  preferred_height: {}".format(preferred_width, preferred_height))
        print("   max_width:       {}  max_height:       {}".format(max_width, max_height))
        print("   force_portrait:  {}  prefer_natural_dimension: {}".format(force_portrait, prefer_natural_dimension))

def create_image_with_href (href:str) -> libxml2.xmlNode:
    n = libxml2.newNode('image')
    n.setProp('href', '../' + href)
    n.setProp('sodipodi:absref', str(Path(href).absolute()))
    n.setProp('xlink:href', '../' + href)
    return n

def generate_toc_item_node (toc_item:dict, pos:tuple, width:float) -> libxml2.xmlNode:
    node = libxml2.newNode('g')
    node.setProp('width', str(width))

    pageno = SvgTextNode("")
    pageno.set_style_template(default_text_style_template)
    pageno.text = str(toc_item['pageno'])
    pageno.set_prop('y', str(pos[1]))
    pageno.set_prop('x', str(pos[0] + width - 15))
    pageno.set_style_property('fill', toc_item['colorbox'])

    gradient = str(hash(toc_item['colorbox']))

    title = libxml2.newNode('text')

    if toc_item['type'] == 'small' or toc_item['type'] == 'small_bold':
        if toc_item['type'] == 'small_bold':
            title.setProp('style', content_text_style.replace('4.5px', '5px') + ";font-weight:bold")
        else:
            title.setProp('style', content_text_style.replace('4.5px', '5px'))
        pageno.set_font_size(8, 'px')
        title.setProp('y', str(pos[1] + 8))
        title.setProp('x', str(pos[0] + 8))
        title.setContent(toc_item['title'])

        node.setProp('height', '10')

    else:
        title.setProp('style', default_text_style.replace('4.5px', '10px'))
        title.setProp('y', str(pos[1]))
        title.setProp('x', str(pos[0] + 8))
        title.setProp('width', str(width - 50))

        pageno.set_font_size(10, 'px')
        title_h = set_text_content_get_height(title, toc_item['title'], ptsize = 10*2.83)
        title.setProp('height', str(title_h + 2))
#       print("++ width " + str(width-50))
#       print("++ ptsize " + str(10*2.83))
#       print("++ (style prop) " + title.prop('style'))
#       print("++ got height " + str(title_h + 2))

        rect = libxml2.newNode('rect')
        rect.setProp('x', str(pos[0]))
        rect.setProp('y', str(pos[1]))
        rect.setProp('width', str(width))
        height = title_h + 2
        rect.setProp('height', str(height))
        rect.setProp('fill', 'url(#tocgrad' + gradient + ')')
        # der Gradient wurde oben im <defs>-Bereich definiert.
        rect.setProp('rx', str(height/2))
        rect.setProp('ry', str(height/2))

        node.setProp('height', rect.prop('height'))

        node.addChild(rect)

    node.addChild(title)
    node.addChild(pageno.render())
    return node

def validate_parameters (parameters, valid_options):
    newparameters = parameters.copy()
    for key, value in parameters.items():
        if not key in valid_options:
            print("Parameter-Validierung: Fehler: Ungültiger Parameter " + key)
            newparameters.pop(key)
            continue

        possible = valid_options[key]
        if type(possible) == list:
            if not value in possible:
                print("Parameter-Validierung: Fehler: Ungültiger Wert " + str(value) + " zu Schlüssel " + key)
                newparameters[key] = possible[0]
                continue
        else:
            # Es gibt einen Standardwert, aber ansonsten keine begrenzte Liste mit Möglichkeiten. Die Validierung wird von der Funktion übernommen.
            pass
       
    # Rückgabewert: Das Parameter-Dictionary, aber fehlende mögliche Optionen auf Standardwerte gesetzt.
    # Standardwert ist jeweils die erste Auswahlmöglichkeit im valid_options dict.
    for key, possible_options in valid_options.items():
        if not key in parameters:
            if type(possible_options) == list:
                newparameters[key] = possible_options[0]
            else:
                newparameters[key] = possible_options

    return newparameters

###
# Content-Erzeuger:
###

def new_content_manual (assembler, options:list):
    assembler.pageno += 1
    print(" | Seite " + str(assembler.pageno) + " muss manuell erstellt werden ")

    # Erstelle stattdessen Blanko-Seite mit Warnhinweis
    (doc, root) = new_svg_document(210, 297, "mm")
    node = SvgTextNode("BLANKO", Position.CENTER).set_font_size(50, "pt")
    node.set_style_property("text-align", "center")
    node.set_prop("x", "105")
    root.addChild(node.render())
    if len(options) > 0:
        node.set_prop("y", "100")
        node.text = options[0]
        root.addChild(node.render())
    assembler.add_page(assembler.pageno, doc)
    doc.freeDoc()

def new_content_person (assembler, options:list, parameters:dict = {}):
    if len(options) > 5:
        assembler.message_for_current_page("Zu viele Argumente zu person. Es kann derzeit nur ein Zusatzfoto verarbeitet werden.")
    elif len(options) < 4:
        message ="Zu wenig Argumente. Erwarte person <Titel> <Pretext-Datei> <Haupttext-Datei> <Bild-Datei>. Es liegen " + str(len(options)) + " Argumente (und zusätzlich " + str(len(parameters)) + " --Parameter) vor:\n" + pformat(options)
        raise Exception(message)

    parameters = validate_parameters(parameters,
            {'pretext-pos': ['right', 'top'],
             'maintext-layout': ['standard', 'twocolumn'],
             'maincolumn-strict': ['off', 'on'],
             'portrait-max-width': '120',
             'portrait-max-height': '120',
             'pretext-highlight': '#e7faff'})
    # Zusätzlicher Parametercheck:
    if parameters['pretext-pos'] != 'top' and parameters['maintext-layout'] != 'standard':
        parameters['maincolumn-strict'] = 'on'

    assembler.pageno += 1

    sidecolumn_exists = False # In D's Vorlage wird die Textposition mit sidecolumn und textarea berechnet

    name = options[0]
    pretext_filename = assembler.get_path(options[1])
    pretextstr = get_file_content(pretext_filename).strip()
    maintext_filename = assembler.get_path(options[2])
    maintextstr = get_file_content(maintext_filename)
    image_filename = assembler.get_path(options[3])
    if len(options) == 5:
        addpic_filename = assembler.get_path(options[4])
    else:
        addpic_filename = None

    template = assembler.load_template(headline = name, intent = "person")

    # Ausdehnungen berechnen
    fullcontentarea = get_child_node_by_id(template, 'fullcontentarea')[0]
    try:
        # Eventuell nehmen wir textarea statt contentarea
        contentarea = get_child_node_by_id(template, 'textarea')[0]
        sidecolumn_exists = True
    except:
        # oder es gibt keine, was ja auch nicht zwingend erforderlich ist.
        contentarea = get_child_node_by_id(template, 'contentarea')[0]
    content_dimensions = (float(contentarea.prop('width')), float(contentarea.prop('height')))
    content_pos = (float(contentarea.prop('x')), float(contentarea.prop('y')))
    image_dimensions = calculate_image_dimension(image_filename, preferred_height = 60, force_portrait = True, max_width = int(parameters['portrait-max-width']), max_height = int(parameters['portrait-max-height']))
    if parameters['pretext-pos'] == 'top':
        pretext_dimensions = (content_dimensions[0] - image_dimensions[0] - 5, image_dimensions[1])
        pretext_pos = (content_pos[0] + image_dimensions[0] + 5, content_pos[1])
        image_pos = content_pos
        # maintext_{pos,dimensions} werden unten berechnet.
    else:
        pretext_minwidth = 50 * (pretextstr != '')
        pretext_dimensions = (max(image_dimensions[0], pretext_minwidth), content_dimensions[1] - image_dimensions[1] - 5)
        # Testen, ob es besondere Vorgaben gibt:
        try:
            sidecolumn = get_child_node_by_id(template, "sidecolumn")[0]
            image_pos = (float(sidecolumn.prop('x')), float(sidecolumn.prop('y')))
            # Neuberechnung der Bildgröße
            max_width = float(sidecolumn.prop('width'))
            image_dimensions = calculate_image_dimension(image_filename, preferred_height = 60, force_portrait = True, max_width = int(min(max_width, int(parameters['portrait-max-width']))), max_height = int(parameters['portrait-max-height']))
            maintext_dimensions = content_dimensions
        except:
            image_pos = (content_pos[0] + content_dimensions[0] - pretext_dimensions[0], content_pos[1])
            maintext_dimensions = (content_dimensions[0] - pretext_dimensions[0], content_dimensions[1])
#       pretext_pos = (image_pos[0] + image_dimensions[0] - pretext_dimensions[0], image_pos[1] + image_dimensions[1])
        pretext_pos = (image_pos[0], image_pos[1] + image_dimensions[1] + 5)
        maintext_pos = content_pos

    # Objekte erstellen
    # 1) Bild
    image = create_image_with_href(image_filename)
    if image_dimensions[2] != 0: # Muss gedreht werden, um Hochformat zu sein
        set_extent(image, image_pos, (image_dimensions[1], image_dimensions[0]))
        # das Rotationszentrum ist (x,y)+max(dim)*(1,1)
        rotdim = max(image_dimensions[0], image_dimensions[1]) /2
        image.setProp('transform', 'rotate(270,' + str(image_pos[0]+rotdim) + ',' + str(image_pos[1]+rotdim) + ')')
    else:
        set_extent(image, image_pos, image_dimensions)

    # 2) Pre-Text
    #    wenn kein Pre-Text gesetzt wurde, beginnen wir hier schon
    #    mit dem Haupttext - jedenfalls im 'pretext-pos'='top' - Modus
    pretext = libxml2.newNode("text")
    set_extent(pretext, pretext_pos, pretext_dimensions)
    pretext.setProp("style", content_text_style)
    if parameters['pretext-pos'] == 'top' and pretextstr == '':
        maintextstr = set_text_content_from_text (pretext, maintextstr, font="Lato")
        pretextheight = image_dimensions[1]
    else:
        pretextheight = set_text_content_get_height (pretext, pretextstr, font = "Lato")
        if pretextheight > pretext_dimensions[1]:
            assembler.message_for_current_page("Der Prätext passt nicht ganz in die dafür vorgesehene Box.")

    if pretextstr != '':
        pretextrect = libxml2.newNode('rect')
        set_extent(pretextrect, pretext_pos, (pretext_dimensions[0], pretextheight + 2))
        pretextrect.setProp('style', 'fill:{}'.format(parameters['pretext-highlight']))
        contentarea.addChild(pretextrect)

    if parameters['pretext-pos'] == 'top':
#       print("pretextheight: {:}; image_dimensions: {:}".format(pretextheight, image_dimensions))
        pretextheight = max(pretextheight, image_dimensions[1])
#       print("content_pos: ", content_pos)
        pretext_padding = 3 * (pretextstr != '') + 1
        maintext_pos = (content_pos[0], content_pos[1] + pretextheight + pretext_padding)
        maintext_dimensions = (content_dimensions[0], content_dimensions[1] - pretextheight - 10)

    # 3) ggf. Zusatzfoto
    if addpic_filename:
        addimg = create_image_with_href(addpic_filename)
        dimension = calculate_image_dimension(addpic_filename, preferred_height = 60, max_width = content_dimensions[0]-image_dimensions[0], max_height = 60)
        if dimension[2] != 0:
            rotdim = max(image_dimensions[0], image_dimensions[1]) /2
            image.setProp('transform', 'rotate(270,' + str(image_pos[0]+rotdim) + ',' + str(image_pos[1]+rotdim) + ')')
            set_extent(addimg, (pretext_pos[0], pretext_pos[1] + pretextheight + 5), (dimension[1], dimension[0]))
        else:
            set_extent(addimg, (pretext_pos[0], pretext_pos[1] + pretextheight + 5), dimension)
        
        pretext_dimensions = (pretext_dimensions[0]-dimension[0], pretext_dimensions[1])
        contentarea.addChild(addimg)

    # 4) Haupt-Text
    maintext2 = None
    if parameters['pretext-pos'] != 'top' and parameters['maincolumn-strict'] != 'on':
        # Wenn der Prätext nicht zu groß ist, wird der Haupttext zunächst in der kleineren Spalte daneben
        # gesetzt, aber unterhalb des Prätextes zu einer großen Spalte vereinigt.
        # Damit es genau passt mit den Zeilenabständen, wird das Format des maintext2-Knotens erst unten gesetzt.
        maintext2_dimensions = (content_dimensions[0], content_dimensions[1] - pretextheight - image_dimensions[1] -15) # approx
        if sidecolumn_exists:
            maintext2_pos = (float(fullcontentarea.prop('x')), pretext_pos[1] + pretextheight + 10)
        else:
            maintext2_pos = (content_pos[0], pretext_pos[1] + pretextheight + 10)

        if maintext2_dimensions[1] < 18: # Platz für 5 Zeilen
            pass
        else:
            maintext2 = libxml2.newNode("text")
            maintext2.setProp("style", content_text_style)
            set_extent(maintext2, maintext2_pos, maintext2_dimensions)
            # Wird unten mit Text gefüllt, hier manipulieren wir zunächst maintext_dimensions:
            maintext_dimensions = (maintext_dimensions[0], maintext_dimensions[1] - maintext2_dimensions[1])

            contentarea.addChild(maintext2)

    maintext = libxml2.newNode("text")
    set_extent(maintext, maintext_pos, maintext_dimensions)
#   print("maintext_pos: ", maintext_pos)
    maintext.setProp("style", content_text_style)

    if parameters['maintext-layout'] == 'twocolumn':
        remaining_text = set_text_content_from_text_twocolumn(maintext, maintextstr, font="Lato")
    else:
        (remaining_text, text_height) = set_text_content_from_text2 (maintext, maintextstr, font = "Lato")

        if maintext2 != None and remaining_text != None:
            # Nachberechnung des Umfangs von maintext2
            maintext2y_translate = content_pos[1] + text_height - maintext2_pos[1]
            maintext2x_translate = content_pos[0] - maintext2_pos[0]
            maintext2_pos = (maintext2_pos[0], content_pos[1] + text_height)
            maintext2_dimensions = (maintext2_dimensions[0] + maintext2x_translate, maintext2_dimensions[1] + maintext2y_translate)
            set_extent(maintext2, maintext2_pos, maintext2_dimensions)
            remaining_text = set_text_content_from_text(maintext2, remaining_text, font = "Lato")

    # Objekte zusammenfügen
    contentarea.addChild(image)
    contentarea.addChild(pretext)
    contentarea.addChild(maintext)
    contentarea.setName("g")
    contentarea.setProp("style", "")
    fullcontentarea.setName("g")
    fullcontentarea.setProp("style", "")

    # Abspeichern
    assembler.add_page(assembler.pageno, template)
    template.freeDoc()

    while remaining_text != None and remaining_text.strip() != '':
        # Es ist noch Haupttext übrig geblieben, erstelle neue Seite
#       print("## es ist noch Haupttext mit Länge {:} über, er beginnt mit '{:}'".format(len(remaining_text), remaining_text[0:29]))
        assembler.pageno += 1
        template = assembler.load_template(headline = "")
        area = get_child_node_by_id(template, 'fullcontentarea')[0]
        area.setName('text')
        area.setProp('style', content_text_style)
        if parameters['maintext-layout'] == 'twocolumn':
            remaining_text = set_text_content_from_text_twocolumn(area, remaining_text, font = "Lato")
        else:
            remaining_text = set_text_content_from_text(area, remaining_text, font = "Lato")

        contentarea = get_child_node_by_id(template, 'contentarea')[0]
        contentarea.setProp('style', '')
        contentarea.setName('g')

        assembler.add_page(assembler.pageno, template)
        template.freeDoc()

def new_content_altneu (assembler, options:list, parameters:dict = {}):
    if len(options) != 3:
        raise Exception("Unzulässige Anzahl von Parametern. Erwarte altneu <titel> <erstes bild> <zweites bild>.")

    parameters = validate_parameters(parameters,
            {'second-image-position':
                [ 'bottom', 'below-first' ],
            'padding': '0' })

    title = options[0]
    img1file = assembler.get_path(options[1])
    img2file = assembler.get_path(options[2])
    assembler.pageno += 1
    template = assembler.load_template(headline = title)

    # Originale Bilddimensionen laden und angemesen aufteilen.
    contentarea = get_child_node_by_id(template, "contentarea")[0]
    ca_dim = (float(contentarea.prop('width')), float(contentarea.prop('height')))
    ca_pos = (float(contentarea.prop('x')), float(contentarea.prop('y')))

    # Volle Breite für Bild Eins. Höhe darf nicht mehr als 2/3 betragen.
    img1_dim = calculate_image_dimension(img1file, max_width = ca_dim[0], preferred_width = ca_dim[0], max_height = (2/3)*ca_dim[1])
    remaining_height = ca_dim[1] - img1_dim[1]
    img2_dim = calculate_image_dimension(img2file, max_width = ca_dim[0], preferred_width = ca_dim[0], max_height = remaining_height)

    # Positionen berechnen. Beide Bilder horizontal zentriert, zweites Bild vertikal unten anliegend.
    img1_pos = (ca_pos[0] + (0.5 * (ca_dim[0] - img1_dim[0])),
                ca_pos[1])
    if parameters['second-image-position'] == 'below-first':
        img2_pos = (ca_pos[0] + (0.5 * (ca_dim[0] - img2_dim[0])),
                    ca_pos[1] + img1_dim[1] + float(parameters['padding']))
    else:
        img2_pos = (ca_pos[0] + (0.5 * (ca_dim[0] - img2_dim[0])),
                    ca_pos[1] + ca_dim[1] - img2_dim[1])

    # Knoten erzeugen und einfügen
    img1_node = create_image_with_href(img1file)
    set_extent(img1_node, img1_pos, img1_dim)
    img2_node = create_image_with_href(img2file)
    set_extent(img2_node, img2_pos, img2_dim)

    contentarea.setName('g')
    contentarea.setProp('style', '')
    contentarea.addChild(img1_node)
    contentarea.addChild(img2_node)

    assembler.add_page(assembler.pageno, template)
    template.freeDoc()

def new_content_einspaltig (assembler, options:list):
    if len(options) != 3:
        raise Exception("Unzulässige Anzahl von Parametern. Erwarte einspaltig <Titel> <Text-Datei> <Bild-Datei>")

    title = options[0]
    textfile = assembler.get_path(options[1])
    imgfile = assembler.get_path(options[2])

    assembler.pageno += 1
    template = assembler.load_template(headline = title)

    # Template der ersten Seite laden
    fca = get_child_node_by_id(template, 'fullcontentarea')[0]
    fca.setName('g')
    contentarea = get_child_node_by_id(template, 'contentarea')[0]
    contentarea.setProp('style', '')
    contentarea.setName('g')

    # Positionen berechnen und Bild einfügen
    content_position = (float(contentarea.prop('x')), float(contentarea.prop('y')))
    content_dimension = (float(contentarea.prop('width')), float(contentarea.prop('height')))
    image_dimension = calculate_image_dimension(imgfile, preferred_width = content_dimension[0])
    image = create_image_with_href(imgfile)
    set_extent(image, content_position, image_dimension)

    if image_dimension[1] > (content_dimension[1]*2):
        assembler.message_for_current_page("Foto ist sehr groß (" + str(round(image_dimension[1], 3)) + " Einheiten) / Inhaltsbereich hat nur Höhe " + str(round(content_dimension[1], 3)) + ".")

    # Möglicherweise wird im Text im {<Dateiname>} ein Zusatzfoto codiert.
    # Dann speichern wir zunächst den eigentlichen Text und setzen ihn bis zum Foto um.
    # Der Rest des Strings, also <Dateiname>}..., wird in der Variablen photo_and_text gespeichert.
    fulltext = get_file_content(textfile)
    parts = fulltext.partition('{')
    if parts[1] == '{':
        text = parts[0]
        photo_and_text = parts[2]
        assembler.message_for_current_page("Zusatzfoto im Einspaltigen Layout gefunden.")
    else:
        text = fulltext
        photo_and_text = None

    # Textknoten
    text_position = (content_position[0], content_position[1] + image_dimension[1])
    text_dimension = (content_dimension[0], content_dimension[1] - image_dimension[1])
    textnode = libxml2.newNode('text')
    set_extent(textnode, text_position, text_dimension)
    textnode.setProp('style', content_text_style)
    remaining_text = set_text_content_from_text(textnode, text, font = 'Lato', ptsize = 4.5*2.83)

    if photo_and_text:
        # es fehlt noch das Zusatzfoto. Kommt es auf diese oder auf die nächste Seite?
        if remaining_text:
            # auf die nächste. hier nichts tun.
            pass
        else:
            # auf diese Seite. Y-Koordinate bestimmen, in dem wir den Text auf einen fiktiven Knoten setzen:
            imaginary_node = libxml2.newNode('text')
            set_extent(imaginary_node, text_position, text_dimension)
            textheight = set_text_content_get_height(imaginary_node, text, font='Lato', ptsize=4.5*2.83)
            parts = photo_and_text.partition('}')
            photo_filename = parts[0]
            remaining_text = parts[2]
            photo_dimension = calculate_image_dimension(photo_filename, preferred_width = content_dimension[0]/3, max_width = content_dimension[0], max_height = content_dimension[1] - textheight)
            photo_position = (content_position[0], content_position[1]+textheight+2)

            photo = create_image_with_href(photo_filename)
            set_extent(photo, photo_position, photo_dimension)
            contentarea.addChild(photo)

            # Variable zurücksetzen, damit das Foto nicht ein zweites Mal hinzugefügt wird:
            photo_and_text = None

            imaginary_node.freeNode()

    # Seite speichern und gegebenenfalls auf neuer Seite fortfahren
    contentarea.addChild(image)
    contentarea.addChild(textnode)
    assembler.add_page(assembler.pageno, template)
    if remaining_text == "" or remaining_text == None:
        return

    template.freeDoc()

    pagecnt = 1
    while remaining_text and remaining_text.strip() != "":
        # Template der nächsten Seite laden
        assembler.pageno += 1
        pagecnt += 1
        template = assembler.load_template(headline = "")
        template_root = template.getRootElement()

        fca = get_child_node_by_id(template, 'fullcontentarea')[0]
        content_dimensions = (float(fca.prop('width')), float(fca.prop('height')))
        content_position = (float(fca.prop('x')), float(fca.prop('y')))
        fca.setName('text')
        fca.setProp('style', content_text_style)
        remaining = set_text_content_from_text(fca, remaining_text, font="Lato", ptsize=4.5*2.83)

        if photo_and_text:
            # Es gibt noch ein Zusatzfoto, welches auf diese Seite gehört.
            # Wir berechnen die Y-Koordinate mit einem fiktiven Knoten
            imaginary_node = libxml2.newNode('text')
            set_extent(imaginary_node, content_position, content_dimensions)
            textheight = set_text_content_get_height(imaginary_node, remaining_text, font='Lato', ptsize=4.5*2.83)
            parts = photo_and_text.partition('}')
            photo_filename = assembler.get_path(parts[0])
            remaining_text = parts[2]
            photo_dimension = calculate_image_dimension(photo_filename, preferred_width = content_dimensions[0]/3, max_width = content_dimensions[0], max_height = content_dimensions[1] - textheight)
            photo_position = (content_position[0], content_position[1]+textheight+2)

            photo = create_image_with_href(photo_filename)
            set_extent(photo, photo_position, photo_dimension)
            template_root.addChild(photo)

            # Gegebenenfalls folgt noch Text; hierfür erstellen wir einen neuen Knoten.
            restnode = libxml2.newNode('text')
            restnode.setProp('style', content_text_style)
            set_extent(restnode, (photo_position[0], photo_position[1] + photo_dimension[1] + 10), (content_dimensions[0], content_dimensions[1] - textheight - photo_dimension[1] - 15))
            if remaining_text:
                remaining = set_text_content_from_text (restnode, remaining_text, font="Lato", ptsize=4.5*2.83)
                template_root.addChild(restnode)


            imaginary_node.freeNode()

        remaining_text = remaining

        contentarea = get_child_node_by_id(template, 'contentarea')[0]
        contentarea.setProp('style', '')
        contentarea.setName('g')

        # Speichern und abschließen
        assembler.add_page(assembler.pageno, template)
        template.freeDoc()


def new_content_seite (assembler, options:list):
    # Wir laden die SVG-Seite und manipulieren schlicht die viewBox-Eigenschaft
    #  mal so, mal so.
    if len(options) > 1:
        assembler.message_for_current_page("Zu viele Argumente. Erwarte: seite <Datei>")

    filename = options[0]
    if filename.endswith('.svg'):
        document = libxml2.parseFile(assembler.get_path(options[0]))
        root = get_child_node_by_tag(document, 'svg')[0]

        assembler.pageno += 1
        hscale = 210 / strip_unit_float(root.prop('width'))
        vscale = 297 / strip_unit_float(root.prop("height"))
#       root.setProp("viewBox", "0 0 210 297") -- eben nicht! sonst wird nur dieser Ausschnitt der Seite dargestellt.
        root.setProp("viewport", "0 0 210 297")
        root.setProp("width", "210mm")
        root.setProp("height", "297mm")
        root.setProp("transform", "scale(" + str(round(hscale, 2)) + " " + str(round(vscale, 2)) + ")")
    else:
        document = libxml2.newDoc("1.0")
        root = libxml2.newNode("svg")
        root.setProp('version', '1.0')
        root.setProp('xmlns:xlink', 'http://www.w3.org/1999/xlink')
        root.setProp('xmlns:sodipodi', 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')
        document.setRootElement(root)

        assembler.pageno += 1
        root.setProp("viewBox", "0 0 210 297")
        root.setProp("viewport", "0 0 210 297")
        root.setProp("width", "210mm")
        root.setProp("height", "297mm")

        img = create_image_with_href(assembler.get_path(filename))
        img.setProp('width', '210')
        img.setProp('height', '297')
        root.addChild(img)

    assembler.add_page(assembler.pageno, document)
    document.freeDoc()

def new_content_bildseite (assembler, options:list):
    # Wir laden die SVG-Seite und manipulieren schlicht die viewBox-Eigenschaft
    #  mal so, mal so.
    # Die innere Funktion ist eine Vereinfachung der calculate_image_dimension
    def calculate_dimension (original:tuple, maximum:tuple) -> tuple:
        factor = min(maximum[0]/original[0], maximum[1]/original[1])
        return (original[0]*factor, original[1]*factor)
    def get_svg_dimension (filepath) -> tuple:
        doc = libxml2.parseFile(filepath)
        svg = doc.getRootElement()
        viewBox = svg.prop("viewBox").split(' ')
        dimension = (float(viewBox[2]), float(viewBox[3]))
        doc.freeDoc()
        return dimension
    def get_raster_dimension (image_filename):
        with Image.open(image_filename) as img:
            origsize = img.size
        return origsize

    if len(options) > 2:
        assembler.message_for_current_page("Zu viele Argumente. Erwarte: bildseite <Datei> <Titel>")
    if len(options) == 1:
        headlinetext = ""
    else:
        headlinetext = options[1]

    assembler.pageno += 1
    template = assembler.load_template(headline = headlinetext)
    if headlinetext == "":
        ca = get_child_node_by_id(template, "fullcontentarea")[0]
    else:
        ca = get_child_node_by_id(template, "contentarea")[0]
    cadimension = (float(ca.prop('width')), float(ca.prop('height')))

    filename = assembler.get_path(options[0])
    if filename.endswith('.svg'):
        dimension = calculate_dimension(get_svg_dimension(filename), cadimension)
        img = create_image_with_href(filename)
        x = float(ca.prop("x"))
        y = float(ca.prop("y"))
        set_extent(img, (x, y), dimension)
        template.getRootElement().addChild(img)
    else:
        dimension = calculate_dimension(get_raster_dimension(filename), cadimension)
        img = create_image_with_href(filename)
        x = float(ca.prop("x"))
        y = float(ca.prop("y"))
        set_extent(img, (x, y), dimension)
        template.getRootElement().addChild(img)

    for nodeid in ['fullcontentarea', 'contentarea']:
        node = get_child_node_by_id(template, nodeid)[0]
        node.setName('g')
        node.setProp('style', '')

    assembler.add_page(assembler.pageno, template)

    template.freeDoc()

def new_content_doppelseite (assembler, options:list):
    # Wir laden die SVG-Doppelseite und manipulieren schlicht die viewBox-Eigenschaft
    #  mal so, mal so.
    if len(options) > 1:
        assembler.message_for_current_page("Zu viele Argumente. Erwarte: doppelseite <Datei>")

    document = libxml2.parseFile(assembler.get_path(options[0]))
    root = get_child_node_by_tag(document, 'svg')[0]

    # eine Seite
    assembler.pageno += 1
    root.setProp("viewBox", "0 0 210 297")
    root.setProp("viewport", "0 0 210 297")
    root.setProp("width", "210mm")
    root.setProp("height", "297mm")
    assembler.add_page(assembler.pageno, document)

    # andere Seite
    assembler.pageno += 1
    root.setProp("viewBox", "210 0 210 297")
    root.setProp("viewport", "210 0 210 297")
    assembler.add_page(assembler.pageno, document)

    document.freeDoc()

def new_content_toc (assembler, options:list):
    if len(options) > 0:
        title = options[0]
    else:
        title = "Inhaltsverzeichnis"

    # Die verwendeten Gradienten müssen am Anfang der Datei im <defs>-Bereich deklariert werden.
    defs = libxml2.newNode('defs')
    colorset = {'gray',}
    for item in assembler.toc:
        colorset.add(item['colorbox'])
    for color in colorset:
        grad = libxml2.newNode('linearGradient')
        grad.setProp('id', 'tocgrad' + str(hash(color)))
        grad.setProp('x1', '0%')
        grad.setProp('x2', '100%')
        grad.setProp('y1', '0%')
        grad.setProp('y2', '0%')

        stop1 = libxml2.newNode('stop')
        stop1.setProp('offset', '0%')
        stop1.setProp('style', 'stop-color:' + color + ';stop-opacity:1:')

        stop2 = libxml2.newNode('stop')
        stop2.setProp('offset', '1000%')
        stop2.setProp('style', 'stop-color:white;stop-opacity:0:')

        grad.addChild(stop1)
        grad.addChild(stop2)
        defs.addChild(grad)

    i = 0 # Ausgabeseite
    j = 0 # TOC-Eintrag
    while j < len(assembler.toc):
        assembler.pageno += 1

        if i == 0:
            headlinetext = title
        else:
            headlinetext = ""
        template = assembler.load_template(headlinetext, intent = "toc")
        template.children.addChild(defs)

        fca = get_child_node_by_id(template, 'fullcontentarea')[0]
        fca.setProp('style', '')
        fca.setName('g')
        try:
            contentarea = get_child_node_by_id(template, 'textarea')[0]
            # für gewisse Seitenstile
        except:
            contentarea = get_child_node_by_id(template, 'contentarea')[0]
        contentarea.setName('g')
        contentarea.setProp('style', '')

        headline = get_headlinetspan(template)
        if i != 0:
            contentarea = fca
        basex = float(contentarea.prop("x"))
        basey = float(contentarea.prop("y"))

        remaining_height = float(contentarea.prop("height"))
        height = float(contentarea.prop("height"))
        width = float(contentarea.prop("width")) - 8
        while remaining_height > 25 and j < len(assembler.toc):
            tocitem = assembler.toc[j]
#           print("## tocitem:")
#           print("   ")
#           pprint(tocitem)
#           print(" # width: " + str(width))
            node = generate_toc_item_node(tocitem, (basex, basey+height-remaining_height), width)
#           print(" # got height: " + node.prop("height"))
            contentarea.addChild(node)
            remaining_height -= float(node.prop("height"))

            j += 1

        assembler.add_page(assembler.pageno, template)

        i += 1

    if i != 0:
        print("Inhaltsverzeichnis: " + str(j) + " Einträge auf " + str(i) + " Seiten ausgegeben")
    else:
        print("Mangels Einträgen kein Inhaltsverzeichnis erstellt")

def new_content_artikel (assembler, options:list, parameters:dict = {}):
    if len(options) < 2:
        print("artikel:")
        print("   Erwarte: artikel <Titel> <Textdatei>, jedoch " + str(len(options)) + " gefunden:")
        pprint(options)
        raise Exception("Ungültige Anzahl von Argumenten.")
    elif len(options) > 2:
        assembler.message_for_current_page("Zu viele Argumente. Erwarte: artikel <Titel> <Textdatei>")

    parameters = validate_parameters(parameters, {'layout': ['standard', 'twocolumn']})

    title = options[0]
    textfile = assembler.get_path(options[1])
    assembler.pageno += 1

    doc = assembler.load_template(headline = title)

    # Text setzen
    content_area = find_textarea(doc)
    content_area.setName('text')
    content_area.setProp('style', content_text_style)
    if parameters['layout'] == 'standard':
        remaining_text = set_text_content_from_file(content_area, textfile, font = "Lato")
    else:
        text = get_file_content(textfile)
        remaining_text = set_text_content_from_text_twocolumn(content_area, text, font = "Lato")

    # Speichern der ersten und ggf. einzigen Seite
    fullcontentarea = get_child_node_by_id(doc, "fullcontentarea")[0]
    fullcontentarea.setProp('style', '')
    fullcontentarea.setName('g')
    assembler.add_page(assembler.pageno, doc)
    doc.freeDoc()

    # ggf. weitere Seiten
    while remaining_text and remaining_text.strip() != '':
        assembler.pageno += 1
        doc = assembler.load_template(headline = "")
        content_area = get_child_node_by_id(doc, 'contentarea')[0]
        content_area.setName('text')
        content_area.setProp('style', '')
        content_area = get_child_node_by_id(doc, 'fullcontentarea')[0]
        content_area.setName('text')
        content_area.setProp('style', content_text_style)
        headline = get_child_node_by_id(doc, 'headline')[0]
        headline.setContent('')

        if parameters['layout'] == 'standard':
            remaining_text = set_text_content_from_text(content_area, remaining_text, font = "Lato")
        else:
            remaining_text = set_text_content_from_text_twocolumn(content_area, remaining_text, font = "Lato")

        assembler.add_page(assembler.pageno, doc)
        doc.freeDoc()

def new_content_textargumente (assembler, options:list, parameters:dict = {}):
    if len(options) < 2:
        print("textargumente:")
        print("   Erwarte: textargumente <Titel> <Absätze>, jedoch " + str(len(options)) + " gefunden:")
        pprint(options)
        raise Exception("Ungültige Anzahl von Argumenten.")

    parameters = validate_parameters(parameters, {'layout': ['standard', 'twocolumn']})

    title = options[0]
    text = ""
    for paragraph in options[1:]:
        text += paragraph + "\n"
    assembler.pageno += 1

    doc = assembler.load_template(headline = title)

    # Text setzen
    content_area = get_child_node_by_id(doc, 'contentarea')[0]
    content_area.setName('text')
    content_area.setProp('style', content_text_style)
    if parameters['layout'] == 'standard':
        remaining_text = set_text_content_from_text(content_area, text, font = "Lato")
    else:
        text = get_file_content(textfile)
        remaining_text = set_text_content_from_text_twocolumn(content_area, text, font = "Lato")

    # Speichern der ersten und ggf. einzigen Seite
    fullcontentarea = get_child_node_by_id(doc, "fullcontentarea")[0]
    fullcontentarea.setProp('style', '')
    fullcontentarea.setName('g')
    assembler.add_page(assembler.pageno, doc)
    doc.freeDoc()

    # ggf. weitere Seiten
    while remaining_text and remaining_text.strip() != '':
        assembler.pageno += 1
        doc = assembler.load_template(headline = "")
        content_area = get_child_node_by_id(doc, 'contentarea')[0]
        content_area.setName('text')
        content_area.setProp('style', '')
        content_area = get_child_node_by_id(doc, 'fullcontentarea')[0]
        content_area.setName('text')
        content_area.setProp('style', content_text_style)
        headline = get_child_node_by_id(doc, 'headline')[0]
        headline.setContent('')

        if parameters['layout'] == 'standard':
            remaining_text = set_text_content_from_text(content_area, remaining_text, font = "Lato")
        else:
            remaining_text = set_text_content_from_text_twocolumn(content_area, remaining_text, font = "Lato")

        assembler.add_page(assembler.pageno, doc)
        doc.freeDoc()

def new_content_portraits (assembler, options:list):
    """
    Erzeuge Seiten mit Kacheln von Portraitfotos. Pro Zeile zwei Personen,
    je ein Bild mit Maske und eines ohne; darunter der Name. Insgesamt
    3 Zeilen Bilder pro Seite.
    Die Bilder liegen als *.Maske.downsample.jpg und *.downsample.jpg im Unterordner,
    der im ersten Argument angegeben ist.
    """
    if len(options) != 2:
        raise Exception("Unzulässige Anzahl Argumente; erwarte portraits <Unterordner> <Überschrift>")
    title = options[1]

    imgfiles = [i for i in [str(i) for i in Path(options[0]).iterdir()] if i.endswith('.downsample.jpg')]
    imgfiles.sort()
    names = [i.replace('-', ' ').replace('.Maske.downsample.jpg', '').split('_') for i in imgfiles if i.endswith('.Maske.downsample.jpg')]
    # Da 6 Namen pro Seite vorgesehen sind, die Namensliste entsprechend slicen
    names_slices = [ names[i:i+6] for i in
            range(0, 6 * math.ceil(len(names)/6), 6)]

    page_cnt = 0
    total_cnt = 0
    # Die Scheibchen seitenweise abarbeiten
    for names in names_slices:
        assembler.pageno += 1
        page_cnt += 1
        template = assembler.load_template(headline = title)

        contentarea = get_child_node_by_id(template, 'contentarea')[0]
        fullcontentarea = get_child_node_by_id(template, 'fullcontentarea')[0]
        contentarea.setProp('style', '')
        contentarea.setName('g')
        fullcontentarea.setProp('style', '')
        fullcontentarea.setName('g')

#       if page_cnt != 1:
#           contentarea = fullcontentarea

        # Ausdehnung der einzelnen Elemente
        itemheight = rowheight = float(contentarea.prop('height'))/3
        rowwidth = float(contentarea.prop('width')) -5
        itemwidth = rowwidth/2 -2
        ca_basex = float(contentarea.prop('x'))
        ca_basey = float(contentarea.prop('y'))

        # Die einzelnen Namen abhandeln
        item_cnt = 0
        for name_array in names:
            name = name_array[1].split('/')[-1] + ' ' + name_array[0].split('/')[-1]
            maskimg = (name_array[0] + '_' + name_array[1]).replace(' ', '-') + '.Maske.downsample.jpg'
            purimg = (name_array[0] + '_' + name_array[1]).replace(' ', '-') + '.downsample.jpg'

            col = item_cnt % 2
            row = (item_cnt-col) / 2
            basex = ca_basex + (col * itemwidth) + (10 * col)
            basey = ca_basey + (row * itemheight)

            dimension = (0, 0)
            # Bildknoten
            if not Path(maskimg).exists():
                assembler.message_for_current_page('Maskenbild ' + maskimg + ' nicht gefunden')
            else:
                dimension = calculate_image_dimension(maskimg, preferred_height = itemheight - 10, force_portrait = True, max_width = itemwidth/2)
                img = create_image_with_href(maskimg)
                pos = (basex + 5, basey)
#               img.setProp('x', str(basex + 5))
#               img.setProp('y', str(basey))
#               img.setProp('height', str(dimension[1]))
#               img.setProp('width', str(dimension[0]))
                if dimension[2] != 0: #rotieren, damit es hochformatig wird
                    maxdim = max(dimension[0], dimension[1]) /2
                    img.setProp('transform', 'rotate(270,' + str(pos[0]+maxdim) + ',' + str(pos[1]+maxdim) + ')')
                    set_extent(img, pos, (dimension[1], dimension[0]))
                else:
                    set_extent(img, pos, dimension)

                contentarea.addChild(img)

#           if not Path(purimg).exists():
#               assembler.message_for_current_page('Purbild ' + purimg + ' nicht gefunden')
#           else:
#               dimension = calculate_image_dimension(purimg, preferred_height = itemheight - 10, force_portrait = True, max_width = itemwidth/2)
                img = create_image_with_href(purimg)
                pos = (basex + 5 + min(dimension[0], dimension[1]), basey)
                if dimension[2] != 0: #rotieren, damit es Hochformatig wird
                    maxdim = max(dimension[0], dimension[1]) /2
                    img.setProp('transform', 'rotate(270,' + str(pos[0]+maxdim) + ',' + str(pos[1]+maxdim) + ')')
                    set_extent(img, pos, (dimension[1], dimension[0]))
                else:
                    set_extent(img, pos, dimension)

                contentarea.addChild(img)

            # Textknoten
            desc = libxml2.newNode('text')
            desc.setProp('style', default_text_style.replace('end', 'center') + ';text-anchor:center;')
            desc.setProp('text-anchor', 'middle')
            desc.setContent(name)
            desc.setProp('x', str(round(basex + itemwidth/2 + 3)))
            desc.setProp('y', str(round(basey + dimension[1] + 7)))
#           desc.setProp('y', str(round(basey + itemheight -13)))
            contentarea.addChild(desc)

            item_cnt += 1
            total_cnt += 1

        assembler.add_page(assembler.pageno, template)
        template.freeDoc()

    assembler.message_for_current_page('Kacheln zu ' + str(total_cnt) + ' Namen in ' + str(page_cnt) + ' Seiten vollendet')

def new_content_empty (assembler, options):
    assembler.pageno += 1
    assembler.message_for_current_page("Leere Seite eingefügt, damit der Constraint 'Linke oder Leere Seite' erfüllt wird.")
    if len(options) != 0:
        print(" | " + options[0])

    # Erstelle Blanko-Seite
    (doc, root) = new_svg_document(210, 297, "mm")
    assembler.add_page(assembler.pageno, doc)
    doc.freeDoc()

###
# Hauptklasse
###
class Assembler:
    def __init__ (self, infile):
        self.infile = infile
        self.lineno = 0
        self.pageno = 0
        self.colorbox = "black"
        self.layout_style = "A"
        self.custom_layout_styles = {}
        self.searchpath = ['.']
        self.macros = {'pass': Macro('pass', ['0', '']),
                'pageno': LambdaMacro('pageno', lambda assembler, arguments: str(assembler.pageno))}
        self.immutable_macros = [] # Erweiterungsmodule können Makros, welche sie deklarieren, als unveränderlich setzen.
        self.trace = False
        self.tagline = ""
        self.end_hook = []

        self.tocfile = None
        self.tocfile_extern = True
        # Falls die Instanz als Subassembler genutzt wird, setzt der Superassembler die TOC-file.
        # Diese muss jedoch nach Ende der Schreibarbeit geschlossen werden, aber noch nicht durch den Subassembler.
        # Daher setzt ::start(), wenn kein Superassembler die Tocfile gesetzt hat, tocfile_extern auf False;
        # auf diese Weise kann unterschieden werden, ob die Instanz am Ende von ::start() tocfile.close() aufrufen soll.

    def function_import (self, options:list):
        filename = self.get_path(options[0])
        print("(" + filename)

        with open(filename) as file:
            subassembler = Assembler(file)
            subassembler.pageno = self.pageno
            subassembler.trace = self.trace
            subassembler.tagline = self.tagline
            subassembler.searchpath = self.searchpath
            subassembler.colorbox = self.colorbox
            subassembler.layout_style = self.layout_style
            subassembler.tocfile = self.tocfile
            subassembler.custom_layout_styles = self.custom_layout_styles
            for export_macro in options[1:]:
                if not export_macro in self.macros:
                    print("!! Makro " + export_macro + " kann nicht exportiert werden")
                subassembler.macros[export_macro] = self.macros[export_macro]
                if export_macro in self.immutable_macros:
                    subassembler.immutable_macros += export_macro
            subassembler.start()

        # Ergebnisse übernehmen:
        self.pageno = subassembler.pageno
        self.trace = subassembler.trace
        self.tagline = subassembler.tagline

        # .. bevor die veränderten Makros übernommen werdne, schließen wir aus, dass auch konstante Makros überschrieben werden:
        for name in self.immutable_macros:
            if name in subassembler.macros:
                del subassembler.macros[name]
#       print(self.immutable_macros)
#       print(" # nach Ausschluss der immutable Macros werden folgende Makros reimportiert:")
#       for name in subassembler.macros:
#           print("   - " + name)
        self.macros.update(subassembler.macros)

        print(")")

    def start (self):
        print("Beginne mit der Verarbeitung der Datei")

        # Das bestehende TOC einlesen, falls vorhanden
        self.toc = []
        try:
            tocfd = open(self.infile.name + '.TOC')
            for line in tocfd:
                parts = line.rstrip().partition(':')
                opts = parts[0]
                title = parts[2]
                options = opts.split(' ')
                self.toc.append({
                    'title': title,
                    'pageno': int(options[0]),
                    'type': options[1],
                    'colorbox': options[2]})
            tocfd.close()
        except Exception as ex:
            print("Suche nach TOC-Datei fehlgeschlagen: " + str(ex))

        # Zum Schreiben in das TOC wird für die Dauer des Vorgangs die tocfile geöffnet, es sei denn, tocfile wurde duch den superassembler gesetzt
        #  (siehe function_import)
        if self.tocfile == None:
            self.tocfile = open(infile.name + '.TOC', 'w')
            self.tocfile_extern = False

        for line in self.infile:
            self.lineno += 1
            self.parse_line (line)

        # End-Hook
        self.lineno += 1
        for command in self.end_hook:
            self.parse_command(command)

        if not self.tocfile_extern:
            self.tocfile.close()

    rx_subexpansion = re.compile(r"(?<!\\)<([^\>]|\\>)+>")
    def parse_line (self, line:str):
        # Kommentar entfernen
        line = line.split('#')[0].strip()

        if len(line) == 0:
#           print("## leere Zeile")
            return

        # Der erste Token entscheidet, ob es sich um eine vordefinierte Funktion handelt (@), einen Makro-Aufruf ($) oder um einen Inhaltstyp.
        # Ein Makro-Aufruf kann zu mehreren Einzelkommandos expandieren, die mit '::::' voneinander getrennt sind. Die Trennung erfolgt jedoch erst nach
        # der Expansion.
        if line[0] == '$':
            # Makro-Definition oder Aufruf
            expansion = self.macro_call(line.split(' ')[1:]) or ""

            self.trace_expand(line, expansion)

            try:
                for command in expansion.split('::::'):
                    self.trace_command(command)
                    self.parse_command(command)
            except Exception as ex:
                if type(ex) == KeyboardInterrupt:
                    print("KeyboardInterrupt beim Verarbeiten von Zeile {:}".format(self.lineno))
                    exit(0)
                print("Fehler beim Verarbeiten von Zeile " + str(self.lineno) + ":")
                print("  Makro-Expansion zu >" + expansion + "<")
                print("  Fehler " + str(ex))
                print(traceback.format_exc())
        else:
            try:
                self.parse_command(line)
            except Exception as ex:
                if type(ex) == KeyboardInterrupt:
                    print("KeyboardInterrupt beim Verarbeiten von Zeile {:}".format(self.lineno))
                    exit(0)
                print("Fehler beim Verarbeiten von Zeile {:}".format(self.lineno))
                print(traceback.format_exc())

    def parse_command (self, line:str):
        if not line or line.strip() == "":
            return

        if line.find('::::') != -1:
            commands = line.strip().split('::::')
            for command in commands:
                self.trace_command(command)
                self.parse_command(command)

            return

        # Möglicherweise liegt ein <>-Subaufruf vor, der ähnlich funktioniert wie $() in bash.
        while m := self.rx_subexpansion.search(line):
            subterm = m.group(0)
            try:
                expansion = self.macro_call(subterm[1:-1].split(' '))
                line = line.replace(subterm, expansion)
                self.trace_expand(subterm, expansion, comment = "Subaufruf")
            except Exception as ex:
                if type(ex) == KeyboardInterrupt:
                    print("KeyboardInterrupt beim Verarbeiten von Zeile {:}".format(self.lineno))
                    exit(0)
                print("Fehler beim Verarbeiten von Zeile {:}".format(self.lineno))
                print("   Fehler beim Verarbeiten des Subaufrufs:")
                
                begin = m.span()[0]
                end = m.span()[1]
                print("   " + line)
                print("   " + (" "*begin) + "^" + ("-"*(end-begin-2)) + ";")
                print("   Das Makro konnte nicht erweitert werden; folgender Fehler ist aufgetreten:")
                print("      " + str(type(ex)) + ", traceback folgt:")
                print(traceback.format_exc())
                return
        # Makro-Substitution abgeschlossen

        # In Tokens aufteilen
        parts = line.strip().split(' ')

        if parts[0] == '@':
            # Eine Funktion aufgerufen
            try:
                functionname = parts[1]
                args = parts[2:]
                function = self.functions[functionname]
            except IndexError:
                print("Fehlerhafte Anweisung in Zeile " + str(self.lineno) + ":")
                print("  Unbekannte Funktion '" + functionname + "'")
                return

            function(self, args)
        elif parts[0] == '$':
            # Makro-Definition oder Aufruf
            expansion = self.macro_call(parts[1:]) or ""
            self.trace_expand(line, expansion)
            try:
                self.parse_command(expansion)
            except Exception as ex:
                if type(ex) == KeyboardInterrupt:
                    print("KeyboardInterrupt beim Verarbeiten von Zeile {:}".format(self.lineno))
                    exit(0)
                print("Fehler beim Verarbeiten von Zeile " + str(self.lineno) + ":")
                print("  Makro-Expansion zu >" + expansion + "<")
                print("  Fehler " + str(ex))
                print(traceback.format_exc())
        else:
            # Ein Inhaltsgenerator oder eine Funktion
            content_type = parts[0]
            if content_type == 'pass':
                return

            if not content_type in self.content_generators:
                # Möglicherweise ein Funktionsaufruf
                try:
                    function = self.functions[content_type]
                except IndexError:
                    print("Fehlerhafte Anweisung in Zeile " + str(self.lineno) + ":")
                    print("  Unbekannte Funktion '" + functionname + "'")
                    return
                function(self, parts[1:])
                return

            # Eventuell ist der letzte Parameter eine Optionsliste
            if parts[-1] and parts[-1].startswith('--'):
                parameters = {}
                paramparts = parts[-1][2:].split(';')
                for part in paramparts:
                    if ':' in part:
                        kvpair = part.rpartition(':')
                        parameters[kvpair[0]] = kvpair[2]
                    else:
                        parameters[part] = True

                parts = parts[:-1]
            else:
                parameters = {}

            # Zunächst müssen String-Literale gesucht und wieder verschmolzen werden
            newparts = []
            n = len(parts)-1
            start = -1
            for i in range(1, n+1):
                if start != -1:
                    if parts[i][-1] != '"':
                        continue
#                   print("   ... bis token #" + str(i) + " [" + parts[i] + "]")
                    harvested = ""
                    for j in range(start, i+1):
                        harvested += " " + parts[j]
                    harvested = harvested[2:-1] # die " entfernen
                    newparts.append(harvested)
                    start = -1

                else:
                    if parts[i] == '':
                        newparts.append(' ')
                        continue
                    elif parts[i][0] != '"':
                        newparts.append(parts[i])
                        continue
                    elif parts[i][-1] == '"' and len(parts[i]) > 1:
                        newparts.append(parts[i][1:-1])
                        continue
#                   print("   harveste ab token #" + str(i) + " [" + parts[i] + "] ...")
                    start = i

#           print("## Wurden geharvested zu:")
#           pprint.pprint(newparts, indent=4)
#           print()

            # Nun liegt ein entsprechend geharvesteter String vor.
            self.add_content(content_type, newparts, parameters)

    def add_content (self, content_type:str, options:list, parameters:dict = {}):
        if not content_type in self.content_generators:
            print("Fehlerhafte Anweisung in Zeile " + str(self.lineno) + ":")
            print("  Unbekannter Inhaltstyp '" + content_type + "'")
            return

        proc = self.content_generators[content_type]
        try:
            if 'parameters' in proc.__code__.co_varnames:
                proc(self, options, parameters)
            else:
                proc(self, options)
                if parameters != {}:
                    raise Exception("Inhaltstyp '" + content_type + "' unterstützt keine '--'-Parameter")
        except Exception as ex:
            print("Fehler (" + str(type(ex)) + ") beim Verarbeiten von Zeile " + str(self.lineno) + ":")
            print("   " + str(ex))
#           sys.last_traceback.print_stack(limit=5)
            print(traceback.format_exc())

    def macro_call (self, line_parts:list):
        if len(line_parts) == 0 or len(line_parts[0]) == 0:
            return

        macro_name = line_parts[0]

        args = line_parts[1:]
        if line_parts[0][-1] == '=':
            if macro_name in self.immutable_macros:
                print("Makro '{}' nicht verändert, da es als immutabel deklariert wurde.".format(macro_name))
                return
            else:
                macro_name = macro_name[:-1]
                self.macros[macro_name] = Macro(macro_name, args)
        else:
            if not macro_name in self.macros:
                raise Exception("Makro '" + macro_name + "' nicht definiert")

            macro = self.macros[macro_name]

            # Möglicherweise enthalten die Argumente String-Literale. Diese müssen wir gesondert harvesten.
            harvest_from = None
            new_args = []
            i = 0
#           print("## originale argumente:")
#           pprint(args)
            for arg in args:
#               print("## i = {:}, arg = »{:}«, harvest_from = {:}".format(i, arg, harvest_from))
                if harvest_from != None:
                    if arg[-1] == '"':
                        # Hier endet ein String-Literal. Harvesten wir also:
#                       print("   String-Literal endet. harveste von {:} bis {:} ...".format(harvest_from, i))
                        new_arg = harvest_options(args[harvest_from:i+1])
                        new_args.append(new_arg.strip('"'))

                        harvest_from = None
                    else:
                        pass
#                       print("   String-Literal endet noch nicht.")
                else:
                    if arg[0] == '"':
                        if len(arg) > 1 and arg[-1] != '"':
#                           print("   String-Literal beginnt.")
                            # Hier beginnt ein String-Literal
                            harvest_from = i
                        else:
#                           print("   ... Argument: »" + arg[1:-1] + "«")
                            new_args.append(arg[1:-1])
                    else:
                        # Ganz normal
#                       print("   ... Argument: »" + arg + "«")
                        new_args.append(arg)
                i += 1
            args = new_args

            return macro.expand(self, args)

    def load_template (self, headline = None, intent = "generic"):
        """ Lädt das aktuell mit layout_style gewählte Layout. Mit dem optionalen Parameter intent kann einem Custom-Layout eine Information gegeben werden. """
#       print("Lade Template für '{}'".format(self.layout_style))
        if self.layout_style in self.custom_layout_styles:
            # Dieses Layout-Template wird von einem CUSTOM_LAYOUT_STYLE bereitgestellt. Wir tun nichts weiter.
            return self.custom_layout_styles[self.layout_style](self, headline, intent)


        filename = right_or_left(self.pageno, postfix = '-') + self.layout_style + '.svg'
        template = load_svg_with_context (filename, self)

        # Wenn im gewählten Template gefärbte Bereiche Text bedecken, muss dessen Farbe
        # entsprechend angepasst werden.
        if self.layout_style == 'B':
            color_list = ['headline']
        elif self.layout_style == 'C':
            color_list = ['bottomtext', 'pageno']
        elif self.layout_style == 'E':
            color_list = ['tagline']
        else:
            color_list = []

        background_color = colorhelper.color_str_to_triplet(self.colorbox)
        text_color = colorhelper.black_or_white_contrast(*background_color)
        for element in color_list:
            try:
                node = get_child_node_by_id(template, element)[0]
                node.setProp('style', style_string_override(node.prop('style'), 'fill', '#' + colorhelper.triplet_to_hex(*text_color)))
                if node.name == 'text':
                    # Auch mit dem dazugehörigen tspan so verfahren
                    for tspan in get_child_node_by_tag(node, 'tspan'):
                        tspan.setProp('style', style_string_override(node.prop('style'), 'fill', '#' + colorhelper.triplet_to_hex(*text_color)))
            except IndexError:
                if not "Delta" in self.layout_style: # Alternative für D's Layoutentwurf
                    print("Kann Knoten '" + element + "' in Vorlagendatei " + filename + " nicht finden, um die Farbe zu ändern")

        ca = get_child_node_by_id(template, "contentarea")[0]

        if headline != None:
            headlinenode = get_child_node_by_id(template, "headline")[0]
            # Zunächst den Platzhalter-Text zurücksetzen:
            get_child_node_by_tag(headlinenode, "tspan")[0].setContent("")

            pxsize = 14.1

            if not headlinenode.prop('width'):
                headlinenode.setProp('width', ca.prop('width'))

            height = set_text_content_get_height(headlinenode, headline, ptsize = pxsize/0.353)
            if height > pxsize +0.01: # 0.01:Toleranz
                # Höhe der Contentarea anpassen
                excess = height - pxsize
#               print("## Anpassen der Contentarea, da Überschrift recht groß. Höhe: {:}, Pxsize: {:}\n.. macht Überschuss von {:} px.\n.. auf Seite {:}".format(height, pxsize, excess, self.pageno))

                ca_height = float(ca.prop('height')) - excess
                ca_y = float(ca.prop('y')) + excess
                ca.setProp('height', str(ca_height))
                ca.setProp('y', str(ca_y))

                # Womöglich ist die Überschrift mit #shape-inside codiert. In diesem Falle muss weiter angepasst werden:
                shape_inside_re = re.compile('shape-inside:url\(#([^)]+)\)')
                m = shape_inside_re.search(headlinenode.prop('style'))
                if m:
                    shape_inside_id = m.group(1)
                    shape_inside = get_child_node_by_id(template, shape_inside_id)[0]
                    shape_inside.setProp('height', str(height))

        try:
            taglinetspan = get_child_node_by_tag(get_child_node_by_id(template, "tagline")[0], "tspan")[0]
            taglinetspan.setContent(self.tagline)
        except:
            pass # womöglich exponieren nicht alle Layout-Vorlagen eine Tagline

        fca = get_child_node_by_id(template, "fullcontentarea")[0]
        fca.setProp('style', '')
        fca.setName('g')
        ca.setProp('style', '')
        ca.setName('g')

        return template

    # Die über @ exponierten Methoden:
    def function_tagline (self, options:list):
        self.tagline = ""
        for item in options:
            self.tagline += item + " "

        self.tagline = self.tagline.strip()

    def function_colorbox (self, options:list):
        if len(options) != 1:
            print("Zeile " + str(self.lineno) + ": Warnung zu '@ colorbox':")
            print("  Erwartete eine Option (Farbe:str), erhalte " + str(len(options)))

        self.colorbox = options[0]

    def function_echo_pageno (self, options:list):
        self.function_echo(options + [str(self.pageno)])

    def function_echo (self, options:list):
        for item in options:
            print(item, end=' ')

        print()

    def function_path (self, options:list):
        if len(options) == 0:
            print("Zeile " + str(self.lineno) + ": Warnung zu '@ path':")
            print("  Um den Suchpfad zurückzusetzen, bitte '@ path %' nutzen.")

        if len(options) == 1 and options[0] == '%':
            print("Suchpfad mit " + str(len(self.searchpath)) + " Elementen wird zurückgesetzt.")
            self.searchpath = ['.']
            return

        for item in options:
            self.searchpath.append(item.rstrip('/'))

    def function_toc_item_small_bold (self, options:list):
        item = ""
        for i in options:
            item += i + ' '
        self.tocfile.write(str(self.pageno+1) + ' small_bold gray:' + item + '\n')

    def function_toc_item_small (self, options:list):
        item = ""
        for i in options:
            item += i + ' '
        self.tocfile.write(str(self.pageno+1) + ' small gray:' + item + '\n')

    def function_toc_item_big (self, options:list):
        item = ""
        for i in options:
            item += i + ' '
        self.tocfile.write(str(self.pageno+1) + ' big ' + self.colorbox + ':' + item + '\n')

    def function_ifx (self, options:list):
        try:
            name1 = options[0].split('&')[0]
            name2 = options[0].split('&')[1]
            macro_then = options[1].split('/')[0]
            macro_else = options[1].split('/')[1]
        except IndexError as ex:
            raise Exception("Ungültige Verwendung der Kondition 'ifx'. Erwarte: @ ifx <makro_1>&<makro_2> <then-makro>/<else-makro>")

        if name1 in self.macros and name1 != 'pass':
            expand1 = self.macros[name1].macro_text
        else:
            expand1 = "pass"

        if name2 in self.macros and name2 != 'pass':
            expand2 = self.macros[name2].macro_text
        else:
            expand2 = "pass"

        if expand1 == expand2:
            self.trace_message("ifx " + name1 + "-> '" + expand1 + "' == '" + expand2 + "' <- " + name2)
            self.trace_message("... " + macro_then + "/" + macro_else + " => " + macro_then)
            self.parse_command("$ " + macro_then + " " + harvest_options(options[2:]))
        else:
            self.trace_message("ifx " + name1 + "-> '" + expand1 + "' != '" + expand2 + "' <- " + name2)
            self.trace_message("... " + macro_then + "/" + macro_else + " => " + macro_else)
            self.parse_command("$ " + macro_else + " " + harvest_options(options[2:]))

    def function_ifright (self, options:list):
        try:
            macro_then = options[0].split('/')[0]
            macro_else = options[0].split('/')[1]
        except IndexError:
            raise Exception("Ungültige Verwendung des Makros 'ifright'. Erwarte: @ ifright <Rechts-Makro-Name>/<Links-Makro-Name>.\nDas erste Makro wird ausgeführt, wenn die nächste Seite eine rechte wäre.")

        if (self.pageno % 2) == 0:
            self.trace_message("ifright (" + str(self.pageno+1) + ") => " + macro_then)
            self.parse_command("$ " + macro_then + " " + harvest_options(options[1:]))
        else:
            self.trace_message("ifright (" + str(self.pageno+1) + ") => " + macro_else)
            self.parse_command("$ " + macro_else + " " + harvest_options(options[1:]))

    def function_ifend (self, options:list):
        try:
            macro_then = options[0].split('/')[0]
            macro_else = options[0].split('/')[1]
        except IndexError:
            raise Exception("Ungültige Verwendung der Kondition 'ifend'. Erwarte @ ifend <Dann-Makro>/<Sonst-Makro> [<Argumente>].\n  Wenn <Argumente> angefügt werden, wird das Sonst-Makro mit diesen aufgerufen, ansonsten das Dann-Makro ohne Argumente.")

        if len(options) == 1:
            self.trace_message("ifend => " + macro_then)
            self.parse_command("$ " + macro_then)
        else:
            self.trace_message("ifend => " + macro_else)
            self.parse_command("$ " + macro_else + " " + harvest_options(options[1:]))


    def function_custom_layout_style (self, options:list):
        """ Ein Python-Modul (options[0]) wird geladen, welches einen neuen Layout-Stil bereitstellen soll, welcher ohne load_template
        auskommt.
        Das Modul muss exponieren:
        LAYOUTER_CUSTOM_LAYOUT_INDEX: dictionary von string (Layout-Name) zu function (welche load_template ersetzt)
        layouterCustomLayoutInit: Methode zur Initialisierung, erhält den Assembler und überschüssige Argumetne zum Aufruf von custom_layout_style
        
        Die load_template-Methode hat die Signatur (assembler:Assembler, headline:str, intent:str) -> libxml2.xmlDoc
        Dabei ist intent der optionale Parameter an Assembler::load_template. """
        if len(options) == 0:
            print("Zeile " + str(self.lineno) + ": Warnung zu @custom_layout_style:")
            print("   Ein Argument fehlt (Name des Python-Moduls")
            return

        module_name = options[0]
        if not module_name in self.custom_layout_styles:
            try:
                module = importlib.import_module(module_name)
                module.layouterCustomLayoutInit(self, options[1:])

                module_index = module.LAYOUTER_CUSTOM_LAYOUT_INDEX
                self.custom_layout_styles |= module_index
#               print("Liste geladener Custom Layouts:")
#               for name in self.custom_layout_styles:
#                   print("'{}'".format(name))
            except ModuleNotFoundError:
                print("Zeile " + str(self.lineno) + ": Warnung zu @custom_layout_style:")
                print("   Kein Python-Modul '" + module_name + "' gefunden")
                return
            except AttributeError:
                print("Zeile " + str(self.lineno) + ": Warnung zu @custom_layout_style:")
                print("   Das Python-Modul '" + module_name + "' muss LAYOUTER_CUSTOM_LAYOUT_INDEX und layouterCustomLayoutInit exponieren")
                return
        else:
            print("Zeile " + str(self.lineno) + ": Warnung zu @custom_layout_style:")
            print("   Modul '" + module_name + "' schon geladen")
            return

    def function_layout_style (self, options:list):
        if len(options) != 1:
            print("Zeile " + str(self.lineno) + ": Warnung zu '@ layout_style':")
            print("  Genau ein Argument (Dateinamen-Postfix) erwartet, aber " + str(len(options)) + " gefunden")

        self.layout_style = options[0]
#       print("Gewähltes Layout: '{}'".format(self.layout_style))

    def function_abort (self, options:list):
        if options:
            pprint(options)
        exit(0)

    def function_trace (self, options:list):
        if len(options) == 0:
            self.trace = True

        if options[0] == 'on':
            self.trace = True
            print("Zeile {:}: Trace aktiviert".format(self.lineno))
        else:
            self.trace = False
            print("Zeile {:}: Trace deaktiviert".format(self.lineno))

    def function_hook_end (self, options:list):
        item = ""
        for i in options:
            item += i + ' '

        self.end_hook.append(item.strip())

    def trace_expand (self, origin, result, comment = ""):
        if not self.trace:
            return
        print("[{:3d}] ".format(self.lineno) + origin)
        print("    | " + comment)
        print("   => " + result)

    def trace_command (self, command, comment = ""):
        if not self.trace:
            return
        print("[{:3d}] →".format(self.lineno) + command + "←")

    def trace_message (self, message):
        if not self.trace:
            return
        print("[{:3d}] ".format(self.lineno) + message)

    def function_add (self, options:list):
        try:
            varname = options[0]
            value = int(self.macros[varname].expand(self, []))
        except IndexError:
            raise Exception("Ungültiger Aufruf von add. Erwarte add <Variable> <Summand1> [<Weitere Summanden>]")
        except TypeError:
            raise Exception("Ungültiger Aufruf von add. Nur Base10-Ganzzahlen erlaubt.")

        for summand in options[1:]:
            try:
                value += int(summand)
            except TypeError:
                raise Exception("Ungültiger Aufruf von add. Nur Base10-Ganzzahlen erlaubt.")

        self.macros[varname].macro_text = str(value)

    def function_mul (self, options:list):
        try:
            varname = options[0]
            value = int(self.macros[varname].expand(self, []))
        except IndexError:
            raise Exception("Ungültiger Aufruf von mul. Erwarte mul <Variable> <Faktor1> [<Weitere Faktoren>]")
        except TypeError:
            raise Exception("Ungültiger Aufruf von mul. Nur Base10-Ganzzahlen erlaubt.")

        for summand in options[1:]:
            try:
                value *= int(summand)
            except TypeError:
                raise Exception("Ungültiger Aufruf von mul. Nur Base10-Ganzzahlen erlaubt.")

        self.macros[varname].macro_text = str(value)

    def function_div (self, options:list):
        try:
            varname = options[0]
            value = int(self.macros[varname].expand(self, []))

            divisor = int(options[1])
            if divisor == 0:
                raise ZeroDivisionError("div kann nicht durch 0 teilen.")

            value = value/divisor
        except IndexError:
            raise Exception("Ungültiger Aufruf von div. Erwarte div <Variable> <Divisor>")
        except TypeError:
            raise Exception("Ungültiger Aufruf von div. Nur Base10-Ganzzahlen erlaubt.")

        self.macros[varname].macro_text = str(value)

    def function_let (self, options:list):
        try:
            dest_varname = options[0]
            src_varname = options[1]
        except IndexError:
            raise Exception("Ungültiger Aufruf von let. Erwarte let <Ziel-Variable> <Quell-Variable>.")

        if not src_varname in self.macros:
            raise Exception("let: Quell-Variable '" + src_varname + "' nicht definiert.")

        src_value = self.macros[src_varname].expand(self, [])

        if dest_varname in self.macros:
            self.macros[dest_varname].macro_text = src_value
        else:
            self.macros[dest_varname] = Macro(dest_varname, ['0', src_value])

    def function_override_pageno (self, options:list):
        try:
            new_pageno = int(options[0])
        except:
            raise Exception("override_pageno: Illegale Syntax.")
        assert(new_pageno >= 0)

        print("Warnung! Überschreibe Seitenzahl {:} (bisher) mit {:} (neu) auf Anweisung aus Zeile {:}.".format(self.pageno, new_pageno, self.lineno))
        self.pageno = new_pageno

    def function_error (self, options:list):
        print("!! Scriptinterne Fehlermeldung (Zeile {:}, Seitenzahl {:})".format(self.lineno, self.pageno))
        print("   " + harvest_options(options))
        raise Exception("Scriptinterne Fehlermeldung")

    def add_page (self, pageno:int, svg:libxml2.xmlDoc):
        svg.saveFile("out/Seite{:03d}.svg".format(pageno))

    functions = { 'echo_pageno': function_echo_pageno,
            'echo': function_echo,
            'error': function_error,
            'path': function_path,
            'trace': function_trace,
            'toc_item_small': function_toc_item_small,
            'toc_item_small_bold': function_toc_item_small_bold,
            'toc_item_big': function_toc_item_big,
            'colorbox': function_colorbox,
            'abort': function_abort,
            'ifx': function_ifx,
            'ifright': function_ifright,
            'ifend': function_ifend,
            'add': function_add,
            'mul': function_mul,
            'div': function_div,
            'let': function_let,
            'override_pageno': function_override_pageno,
            'import': function_import,
            'tagline': function_tagline,
            'hook_end': function_hook_end,
            'custom_layout_style': function_custom_layout_style,
            'layout_style': function_layout_style }
    content_generators = { 'manual': new_content_manual,
            'person': new_content_person,
            'einspaltig': new_content_einspaltig,
            'artikel': new_content_artikel,
            'textargumente': new_content_textargumente,
            'empty': new_content_empty,
            'toc': new_content_toc,
            'portraits': new_content_portraits,
            'doppelseite': new_content_doppelseite,
            'seite': new_content_seite,
            'altneu': new_content_altneu,
            'bildseite': new_content_bildseite }

    def message_for_current_page (self, message):
        self.message_for_page(self.pageno, message)

    def message_for_page (self, page, message):
        print(" | {:03d}:".format(page))
        print(" | " + message)

    def get_path (self, filename):
        # Das Skirpt kann mit '@ path'-Befehlen Ordner zum Suchpfad machen.
        # Diese Funktion sucht in allen so hinzugefügten Pfaden nach einer
        # Daten namens filename.

        if filename[0] == '/':
            # Absoluter Pfad
            return filename

        if filename == '%' or filename == '/dev/null':
            return '/dev/null'

        for i in self.searchpath:
            if Path(i + '/' + filename).exists():
                return (i + '/' + filename)

        # Schleife ohne Erfolg durchlaufen.
        # Zum Visuellen Debugging geben wir bei Bilddateien eine entsprechendes Bild zurück.
        print("Warnung: '" + filename + "' nicht gefunden")
        if filename.endswith('.png') or filename.endswith('.jpg') or filename.endswith('.svg'):
            return str(Path('BildFehlt.png').absolute())

        return filename

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise Exception("Erwartete ein Argument. Go.py <Inhaltsliste>")

    infilename = sys.argv[1]
    with open(infilename, 'r') as infile:
        parser = Assembler(infile)
        parser.start()
