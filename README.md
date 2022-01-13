Generate books using SVG templates

# Layouter

Erstellt Bücher in einem gewissen Stil; es werden Inhalte und Layout-Vorlagen vorgegeben, anhand einer Übersichtsdatei werden diese zusammengefügt.
Die Layoutvorlagen müssen im SVG-Format vorliegen, es muss je eine Datei für rechte und linke Seiten geben.

## Die Layoutvorlagen
Werden durch Namen unterschieden. Für eine Vorlage mit Namen `example` müssen im Verzeichnis, von dem aus das Skript aufgerufen wird, die Dateien `example-Links.svg` und `example-Rechts.svg` liegen. Gewisse Knoten in den Vorlagen werden vom Layouter benutzt, wenn sie eine der folgenden `id`-s besitzen:
  - headline (für Überschriften)
  - tagline (je nach Layout für Kapitelüberschriften)
  - bottomtext
  - pageno
(dies müssen Text-Knoten sein)
  - contentarea
  - fullcontentarea
  - textarea
(hier ist der Typ egal, solange x, y, width, height gesetzt sind)

## Ausführung

Sei `Inhalt` der Name unserer Übersichtsdatei. Wir führen zum Erzeugen der Seiten im Arbeitsverzeichnis die Befehle

      mkdir out
      rm out/*
      ./Go.py Inhalt
  
aus.

Zum Erzeugen einer großen PDF-Datei aus diesen Seiten:

      cd out
      inkscape --batch-process --actions="export-type:pdf;export-do" Seite*.svg
      pdfjam --outfile Alles.pdf Seite*.pdf
  
Dauert eventuell eine Weile.

## Syntax der Übersichtsdatei

Kommentare werden mit `#` eingeleitet. Alle nicht-leeren Zeilen, die nicht nur aus Kommentaren bestehen, tun dann genau eine der folgenden Dinge:
 - einen Inhalt erzeugen
 - eine eingebaute Funktion aufrufen
 - ein Makro aufrufen

### Inhalt erzeugen
Es gibt verschiedene Inhaltstypen. Die Syntax lautet

      (Inhaltstyp) (Benötigte Argumente).


### Eingebaute Funktionen
Der Name der Funktion wird mit einem `@` präfigiert.
  
### Makros
Makros werden wie folgt definiert:

      $ (name)= (n) (s)
  
Wobei (name) der Name des zu definierenden Makros, (n) die Anzahl der Argumente und (s) der Text ist, in welchem die Substitution stattfinden soll. In (s) wird `'i'` durch das i-te Argument ersetzt.
  
Aufruf eines Makros:
      $ (name) (argumente)
  
## Benötigte Pakete (nicht erschöpfende Aufzählung)
 - inkscape
 - python3
 - python3-gi-cairo
 - python3-libxml2
