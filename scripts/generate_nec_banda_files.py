
import xml.etree.ElementTree as ET
from datetime import date, timedelta, datetime

def generate_nec_banda_file(base_date, output_file_path, template_file):
    # Determine the number of intervals for the given day
    is_dst_spring_forward = base_date.month == 3 and base_date.weekday() == 6 and 25 <= base_date.day <= 31
    is_dst_fall_back = base_date.month == 10 and base_date.weekday() == 6 and 25 <= base_date.day <= 31

    if is_dst_spring_forward:
        num_intervals = 92
    elif is_dst_fall_back:
        num_intervals = 100
    else:
        num_intervals = 96

    # Parse the template file
    tree = ET.parse(template_file)
    root = tree.getroot()

    # Update fields
    identificador = root.find("Identificador")
    if identificador is not None:
        identificador.set("v", f"necBandaFRR_{base_date.strftime('%Y%m%d')}.2")

    dia_mercado = root.find("DiaMercado")
    if dia_mercado is not None:
        dia_mercado.set("v", base_date.strftime('%Y-%m-%d'))
    
    hora_envio = root.find("HoraEnvio")
    if hora_envio is not None:
        hora_envio.set("v", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Update Horizonte
    horizonte = root.find("Horizonte")
    if horizonte is not None:
        start_date = base_date - timedelta(days=1)
        end_date = base_date
        horizonte.set("v", f"{start_date.strftime('%Y-%m-%d')}T23:00Z/{end_date.strftime('%Y-%m-%d')}T23:00Z")

    periodo = root.find("Periodo")
    if periodo is not None:
        # Update IntervaloTempo
        intervalo_tempo = periodo.find("IntervaloTempo")
        if intervalo_tempo is not None:
            start_date = base_date - timedelta(days=1)
            end_date = base_date
            intervalo_tempo.set("v", f"{start_date.strftime('%Y-%m-%d')}T23:00Z/{end_date.strftime('%Y-%m-%d')}T23:00Z")
        
        # Remove existing intervals
        for intervalo in periodo.findall("Intervalo"):
            periodo.remove(intervalo)

        # Add new intervals
        for i in range(1, num_intervals + 1):
            intervalo = ET.SubElement(periodo, "Intervalo")
            ET.SubElement(intervalo, "NumeroPeriodo").set("v", str(i))
            ET.SubElement(intervalo, "BandaSubir").set("v", "300")
            ET.SubElement(intervalo, "BandaDescer").set("v", "300")
            ET.SubElement(intervalo, "BandaMinima").set("v", "1")

    # Write the new XML file
    tree.write(output_file_path, encoding="UTF-8", xml_declaration=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Date in YYYY-MM-DD format")
    parser.add_argument("output", help="Output file path")
    parser.add_argument("--template", help="Template file path", default="/data/tiago/Documents/Projects/mock-watt/data/payloads/ren/bafrr/necBanda.xml")
    args = parser.parse_args()

    base_date = date.fromisoformat(args.date)
    generate_nec_banda_file(base_date, args.output, args.template)
