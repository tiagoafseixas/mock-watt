#!/usr/bin/env python3
"""Script to randomize BandaSubir and BandaDescer values in the necBanda_normal.xml file."""

import random
import xml.etree.ElementTree as ET

# Define the ranges for random values
BANDA_SUBIR_MIN = 0
BANDA_SUBIR_MAX = 90
BANDA_DESCER_MIN = 0
BANDA_DESCER_MAX = 5

def randomize_banda_values(input_file, output_file):
    """Randomize BandaSubir and BandaDescer values in the XML file."""
    # Parse the XML file
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Iterate through all Intervalo elements
    for intervalo in root.findall('.//Intervalo'):
        # Randomize BandaSubir (0 to 90)
        banda_subir = intervalo.find('BandaSubir')
        if banda_subir is not None:
            banda_subir.set('v', str(random.randint(BANDA_SUBIR_MIN, BANDA_SUBIR_MAX)))

        # Randomize BandaDescer (0 to 5)
        banda_descer = intervalo.find('BandaDescer')
        if banda_descer is not None:
            banda_descer.set('v', str(random.randint(BANDA_DESCER_MIN, BANDA_DESCER_MAX)))

    # Write the modified XML to the output file
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)
    print(f"Randomized values written to {output_file}")

if __name__ == '__main__':
    input_file = 'data/payloads/ren/ws504/necBanda_normal.xml'
    output_file = 'data/payloads/ren/ws504/necBanda_normal.xml'
    randomize_banda_values(input_file, output_file)