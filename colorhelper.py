def triplet_to_hex (r:int, g:int, b:int) -> str:
    return "{:X}{:X}{:X}".format(r, g, b)

def triplet_string_to_triplet (rgb_triplet_string:str) -> tuple:
    pos = rgb_triplet_string.find('(')
    numbers_string = rgb_triplet_string[pos+1:-1]
    triplet = numbers_string.split(',')

    return (int(triplet[0]), int(triplet[1]), int(triplet[2]))

def colorname_to_hex (name:str) -> str:
    lookfor = name + '\t'
    with open('Farbcodes') as fd:
        for line in fd:
            if line.startswith(lookfor):
                triplet_s = line.split('\t')[1].strip()
#               print("# colorname_to_hex: »{:}« => »".format(name) + triplet_s + "«") 
                return triplet_to_hex(*triplet_string_to_triplet(triplet_s))
    
    print("Farbe '" + name + "' nicht definiert, kodieren als rot.")
    return "FF0000"

def color_str_to_triplet (color:str):
    if color.startswith('rgb'):
        return triplet_string_to_triplet(color.strip())
    elif color.startswith('#'):
        n = len(color)
        return color_str_to_triplet(color[1:n])
    elif len(color) == 6:
        return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
    else:
        return color_str_to_triplet(colorname_to_hex(color))

def _srgb_to_lin(channel_value):
    if not (channel_value <= 1):
        raise AssertionError("Ungültiger Wert " + str(channel_value))

    if channel_value <= 0.0404:
        return channel_value / 12.92
    else:
        return pow(( (channel_value +0.044)/1.055), 2.4)

def black_or_white_contrast (r, g, b) -> tuple:
    # Formel von Stack-Overflow
    r /= 255
    g /= 255
    b /= 255

    y_lin = (0.02126 * _srgb_to_lin(r) +
             0.7152  * _srgb_to_lin(g) +
             0.0722  * _srgb_to_lin(b))

    if y_lin < 0.008856:
        perc_lightness = y_lin * 9.033
    else:
        perc_lightness = pow(y_lin, 1/3) * 1.16 - 0.16

    if perc_lightness <= 0.25:
        factor = 1 - perc_lightness
    elif perc_lightness <= 0.5:
        factor = 0.5 + perc_lightness
    elif perc_lightness <= 0.75:
        factor = perc_lightness - 0.5
    else:
        factor = 1 - perc_lightness

    return (round(254 * factor),
            round(254 * factor),
            round(254 * factor))


if __name__ == '__main__':
    print("Input Schwarz 0 0 0")
    print(black_or_white_contrast(0, 0, 0))
    print("Input Weiß 254 254 254")
    print(black_or_white_contrast(254, 254, 254))
