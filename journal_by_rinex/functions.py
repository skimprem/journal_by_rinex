import os
import georinex as gr
import pyproj
from pylatex import Document, Section, Table, Tabular, LongTable, NoEscape,\
    Package, Command, MultiColumn, MiniPage, MultiRow
import numpy as np
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point
import matplotlib.pyplot as plt
import cartopy.io.img_tiles as cimgt
from cartopy import crs as ccrs



def get_info(rinex_file):

    header = gr.rinexheader(rinex_file)

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
    doc.append(NoEscape(f'\\par\\noindent Наименование пункта: {data['marker name']}\\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindent Объект: {data['object']}\\hrulefill'))
    doc.append(NoEscape(f'\\par\\noindent Исполнитель (ФИО подпись): {data['operator']}\\hrulefill'))

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
        table.add_row(['GDOP', data['gdop'], data['gdop']])
        table.add_hline()
        table.add_row(['PDOP', data['pdop'], data['pdop']])
        table.add_hline()

    doc.append(
        NoEscape(
            r'''\begin{center}
                \textbf{Тип измерения высоты антенны (наклонная, вертикальная,
                вертикальная до фазового центра)}
            \end{center}'''
        ))
    
    ant_height_type = data['antenna height type']
    
    abs_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), 'images'))
 
    if ant_height_type in ['base', 'phase']:
        a_pic_path = os.path.join(abs_path, ant_height_type)
        b_pic_path = os.path.join(abs_path, 'tripod_default')
    else:
        a_pic_path = os.path.join(abs_path, 'default')
        b_pic_path = os.path.join(abs_path, ant_height_type)

    a_picture = r'\includegraphics[width=0.2\textwidth]{' + a_pic_path.replace("\\", "/") + '}'
    b_picture = r'\includegraphics[width=0.2\textwidth]{' + b_pic_path.replace("\\", "/") + '}'

    location_map = get_map(data['latitude'], data['longitude'], data['marker name'])
    location_map_path = os.path.join(os.path.dirname(filename), f'{data['marker name']}.png')
    location_map.savefig(location_map_path)
    insert_file = r'\includegraphics[width=0.3\textwidth]{'+location_map_path.replace('\\', '/')+'}'

    with doc.create(LongTable(r'|p{0.6\textwidth}|p{0.3\textwidth}|')) as table:
        table.add_hline()
        table.add_row(
            [
                'Схема расположения пункта с указанием минимум 3-х дистанций до долговечных объектов местности',
                'Зарисовка постановки антенны (штатив, веха, пилон, тур, УПЦ)'
            ]
        )
        table.add_hline()
        table.add_row([MultiRow(4, data=NoEscape(insert_file)), 'A. Без штатива'])
        table.add_row(['', NoEscape(a_picture)])
        table.add_row(['', 'B. На штативе'])
        table.add_row(['', NoEscape(b_picture)])
        table.add_hline()
    
    # Generate the PDF
    doc.generate_pdf(filename, clean_tex=False) 

def get_map(longitude, latitude, marker_name):
    ''' Get map of ties scheme '''

<<<<<<< HEAD
   
    fig = plt.figure(figsize=(5, 5))
=======
    fig = plt.figure(figsize=(15, 15))
>>>>>>> 0f5af58f6f8dacda5e8553bb60375bb86678df03
      
    # extent = [longitude - 0.01, longitude + 0.01, latitude - 0.01, latitude + 0.01]
    request = cimgt.OSM()
    ax = plt.axes(projection=request.crs)
    # ax.set_extent(extent)

    zoom = 11

    ax.add_image(request, zoom)

    ax.plot(longitude, latitude, '-ok', mfc='w', transform=ccrs.PlateCarree())
   
    ax.annotate(marker_name, xy=(longitude, latitude),
        xycoords='data', xytext=(1.5, 1.5),
        textcoords='offset points',
        fontsize=14,
        color='k', transform=ccrs.PlateCarree())

    return fig

# fig = get_map(37.6176, 55.7558, 'Moscow')

# fig.savefig('test.png')