import georinex as gr
import pyproj
from pylatex import Document, Section, Table, Tabular, LongTable, NoEscape,\
    Package, Command, MultiColumn, MiniPage, MultiRow
import numpy as np

def get_info(rinex_file):

    header = gr.rinexheader(rinex_file)

    print('header ...', end='')
    info = {}
    info['marker name'] = header['MARKER NAME'].strip()
    x, y, z = map(float, header['APPROX POSITION XYZ'].split())
    info['longitude'], info['latitude'], info['height'] = pyproj.Transformer.from_crs(
        pyproj.CRS.from_proj4('+proj=cart'),
        pyproj.CRS.from_proj4('+proj=longlat +ellps=WGS84'),
    ).transform(x, y, z)
    rec_type_vers = header['REC # / TYPE / VERS'].strip()
    info['receiver number'] = rec_type_vers[:20].strip()
    info['receiver type'] = rec_type_vers[20:40].strip()
    ant_type = header['ANT # / TYPE'].strip()
    info['antenna number'] = ant_type[:20].strip()
    info['antenna type'] = ant_type[20:40].strip()
    info['antenna height'], _, _ = map(float, header['ANTENNA: DELTA H/E/N'].split())
    print('done!')

    # print('loading ... ', end='')
    # data = gr.load(rinex_file)
    # print('done!')
    # start_time = data.time[0].values  # Start of seance
    # end_time = data.time[-1].values   # End of seance
    # info['start'] = start_time
    # info['end'] = end_time

    return info

def crd2cell_100(lon, lat):
    rows = 'A B C D E F G H I J K L M N O P Q R S T U V Z'.split()
    col = int(lon//6+31)
    row = int(lat//4)
    subcell = 133 - 12 * int((lat - row * 4)//(4/12)) + int((lon - col * 6 + 186)//(6/12))
    return '-'.join([str(rows[row]), str(col), str(subcell)])

def journal_generator(data, filename):

    doc = Document(
        document_options=['10pt', 'a4paper', 'final'],
        documentclass='article',
        geometry_options=['left=2cm', 'right=2cm', 'top=2cm', 'bottom=2cm'],
        inputenc='utf8',
        fontenc='OT1',
        lmodern=False,
        textcomp=True,
    )
    # doc.preamble.append(Command("author", "Anonymous author"))
    doc.preamble.append(Package('babel', 'russian'))
    doc.preamble.append(Package('makecell'))
    doc.preamble.append(Package('longtable'))
    doc.preamble.append(Package('graphicx'))

    # doc.preamble.append(Command("title", "ЖУРНАЛ СПУТНИКОВЫХ НАБЛЮДЕНИЙ"))
    # doc.preamble.append(Command("date", ""))
    # Add title and section
    # doc.append(NoEscape(r'\maketitle'))

    doc.append(Command('thispagestyle', 'empty'))

    doc.append(NoEscape(r'\section*{ЖУРНАЛ СПУТНИКОВЫХ НАБЛЮДЕНИЙ}'))

    doc.append(NoEscape(f'Организация: {data['organization']} \\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindentНаименование пункта: {data['marker name']}\\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindentОбъект: {data['object']}\\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindentИсполнитель (ФИО подпись): {data['operator']}\\hrulefill'))

    with doc.create(LongTable('l')) as table:
        table.add_row(["Приближенные координаты"])
        table.add_row([f'B = {data["latitude"]:.6f}'])
        table.add_hline()
        table.add_row([f'L = {data["longitude"]:.6f}'])
        table.add_hline()
        table.add_row([f'H = {data["height"]:.6f}'])
        table.add_hline()
        table.add_row([f"Трапеция масштаба карты 1:100000 {crd2cell_100(data['longitude'], data['latitude'])}"])
        table.add_hline()
        table.add_row([f'Тип и № приемника {data["receiver type"]} {data["receiver number"]}'])
        table.add_hline()
        table.add_row([f'Тип и № антенны {data["antenna type"]} {data["antenna number"]}'])
        table.add_hline()

    doc.append(NoEscape(f'\\noindentТип и характеристика геодезического знака {data['centre type']}\\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindentТип и характеристика центра (марки) {data['benchmark type']}\\hrulefill'))

    doc.append(NoEscape(r'\begin{center}\textbf{Время выполнения сеансов}\end{center}'))

    # Create a table to display the metadata
    with doc.create(LongTable(NoEscape(r"|p{0.3\textwidth}|p{0.3\textwidth}|p{0.3\textwidth}|"))) as table:
        table.add_hline()
        table.add_row(["Номер сеанса", MultiColumn(size=2, align='c|', data=NoEscape(r'Сеанс \textnumero{}'))])
        table.add_hline(2,3)
        table.add_row(['', 'Начало', 'Конец'])
        table.add_hline()
        table.add_row(['Дата', '', ''])
        table.add_hline()
        table.add_row(['Время', '', ''])
        table.add_hline()
        table.add_row(['Высота антенны', data['antenna height'], data['antenna height']])
        table.add_hline()
        table.add_row(['GDOP', '', ''])
        table.add_hline()
        table.add_row(['PDOP', '', ''])
        table.add_hline()

    doc.append(NoEscape(r'\begin{center}\textbf{Тип измерения высоты антенны (наклонная, вертикальная, вертикальная до фазового центра)}\end{center}'))
    
    ant_height_type = data['antenna height type']
    if ant_height_type in ['base', 'phase']:
        a_picture = r'\includegraphics[width=0.2\textwidth]{'+ant_height_type+'}'
        b_picture = r'\includegraphics[width=0.2\textwidth]{tripod_default}'
    else:
        a_picture = r'\includegraphics[width=0.2\textwidth]{default}'
        b_picture = r'\includegraphics[width=0.2\textwidth]{'+ant_height_type+'}'
    
    with doc.create(LongTable(r'|p{0.6\textwidth}|p{0.3\textwidth}|')) as table:
        table.add_hline()
        table.add_row(
            [
                'Схема расположения пункта с указанием минимум 3-х дистанций до долговечных объектов местности',
                'Зарисовка постановки антенны (штатив, веха, пилон, тур, УПЦ)'
            ]
        )
        table.add_hline()
        table.add_row([MultiRow(4, data=''), 'A. Без штатива'])
        table.add_row(['', NoEscape(a_picture)])
        table.add_row(['', 'B. На штативе'])
        table.add_row(['', NoEscape(b_picture)])
        table.add_hline()
    
    # Generate the PDF
    doc.generate_pdf(filename, clean_tex=True) 

# info = get_info('nogN2771.24O')

# info['antenna height type'] = 'base'

# journal_generator(info, info['marker name'].strip())