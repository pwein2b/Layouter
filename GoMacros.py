import re
import pwsvgxml

def find_textarea (document):
    try:
        ta = pwsvgxml.get_child_node_by_id(document, 'textarea')[0]
        return ta
    except IndexError:
        pass

    return pwsvgxml.get_child_node_by_id(document, 'contentarea')[0]

class Macro:
    def __init__ (self, macro_name, macro_text:list):
        self.macro_name = macro_name
        if len(macro_text) == 0:
            raise Exception("Ungültige Makro-Definition. Erwarte: $ <name>= <anzahl argumente> <ersetzungstext>")

        self.n_args = int(macro_text[0])
        
        self.macro_text = ""
        for item in macro_text[1:]:
            self.macro_text += item + " "

        # Jeweils einen Backslash aus dem Makro-Text entfernen
        self.macro_text = re.sub("(?<!\\\\)\\\\", "", self.macro_text).strip()

    def copy (self, new_name):
        new_macro = Macro(new_name, ['0'])
        new_macro.macro_text = self.macro_text
        new_macro.n_args = self.n_args
        return new_macro

    def expand (self, assembler, arguments:list):
#       print("## Versuche " + self.macro_name + " mit folgenden Argumenten zu expandieren:")
#       pprint(arguments)

        if len(arguments) < self.n_args:
            raise Exception("Ungültiger Makro-Aufruf. '" + self.macro_name + "' erwartet " + str(self.n_args) + " Argumente, habe " + str(len(arguments)) + " vorgefunden:\n" + pformat(arguments))
        # Wenn zu viele Argumente vorliegen, so werden diese am Ende wieder mit zurückgegeben

        result = self.macro_text
#       print("   >" + self.macro_text + "<")
#       print("   ↓")

        for arg in range(self.n_args):
            # In der Makro-Definition können Argumente mit `0`, `1` etc. aufgerufen werden. Dann werden die Argumente unverändert übernommen.
            # Ferner können sie mit `"0"`, `"1"` etc. aufgerufen werden; dann werden sie genau dann mit Doppelten Anführungszeichen umgeben, wenn sie ein Leerzeichen enthalten.

            search1 = '`{:}`'.format(int(arg))
            replace1 = arguments[arg]
            
            search2 = '`"{:}"`'.format(int(arg))
            if ' ' in arguments[arg]:
                replace2 = '"' + arguments[arg] + '"'
            else:
                replace2 = replace1

            result = result.replace(search1, replace1).replace(search2, replace2)

#           print("   >" + result + "<")

        if len(arguments) > self.n_args:
            for arg in arguments[self.n_args:]:
                result += " \"" + arg + "\""

#       print("   → >" + result + "<")
        return result or ""

class LambdaMacro(Macro):
    """ Normale Makros werden anhand von Textbasierten Vorschriften expandiert.
    Makros wie $ pageno hingegen verlangen nach einer Expansion durch
    Python-Makros; diese Subklasse ermöglicht das.

    Das Expand-Lambda muss die Argumente (Macro, Assembler, Argumente:list) annehmen. """
    def __init__ (self, macro_name, macro_expand):
        super().__init__(macro_name, ['0', 'pass'])
        self.expand = macro_expand

