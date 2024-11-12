import os
import georinex as gr
import pyproj
from datetime import datetime as dt
from pylatex import Document, Section, Table, Tabularx, LongTable, NoEscape,\
    Package, Command, MultiColumn, MiniPage, MultiRow, Section, Subsection
import numpy as np
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point
import matplotlib.pyplot as plt
import cartopy.io.img_tiles as cimgt
from cartopy import crs as ccrs

HEIGHT_TYPES = {
    'base': 'вертикальная (УПЦ)',
    'phase': 'вертикальная до фазового центра (УПЦ)',
    'tripod_slant': 'наклонная (штатив)',
    'tripod_base': 'вертикальная (штатив)',
    'tripod_phase': 'вертикальная до фазового центра (штатив)',
}

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

    times = []
    with open(rinex_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line[0] == '>':
                year, month, day, hour, minute, second = line.split()[1:7]
                times.append(
                    dt.strptime(f'{year}-{month}-{day} {hour}:{minute}:{second.split('.')[0]}', '%Y-%m-%d %H:%M:%S'))
    
    start_time = times[0]
    end_time = times[-1]
    # print('loading ... ', end='')
    # data = gr.load(rinex_file)
    # print('done!')
    # start_time = data.time[0].values  # Start of seance
    # end_time = data.time[-1].values   # End of seance
    info['start date'] = start_time.date()
    info['start time'] = start_time.time()
    info['end date'] = end_time.date()
    info['end time'] = end_time.time()

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

    with doc.create(Section(title=r'ЖУРНАЛ СПУТНИКОВЫХ НАБЛЮДЕНИЙ', numbering=False)):

        with doc.create(Subsection(title=r'Общая информация', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r'|l|X|'),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row(['Организация:', data['organization']])
                table.add_hline()
                table.add_row(['Наименование пункта:', data['marker name']])
                table.add_hline()
                table.add_row(['Объект:', data['object']])
                table.add_hline()
                table.add_row(['Исполнитель (ФИО):', data['operator']])
                table.add_hline()
                table.add_row([MultiColumn(size=2, data='Приближенные координаты:', align='c')])
                table.add_hline()
                table.add_row(['Широта', f'{data["latitude"]:.6f}'])
                table.add_hline()
                table.add_row(['Долгота', f'{data["longitude"]:.6f}'])
                table.add_hline()
                table.add_row(['Высота', f'{data["height"]:.6f}'])
                table.add_hline()
                table.add_row(['Трапеция 1:100000:', f'{crd2cell_100(data['longitude'], data['latitude'])}'])
                table.add_hline()
                table.add_row(['Тип и № приемника:', f'{data["receiver type"]} {data["receiver number"]}'])
                table.add_hline()
                table.add_row(['Тип и № антенны:', f'{data["antenna type"]} {data["antenna number"]}'])
                table.add_hline()
                table.add_row(['Тип и хар-ка геод. знака:', f'{data['centre type']}'])
                table.add_hline()
                table.add_row(['Тип и хар-ка центра (марки):', f'{data['benchmark type']}'])
                table.add_hline()

        ant_height_type = data['antenna height type']

        # Create a table to display the metadata
        with doc.create(Subsection(title=r'Информация о сеансе измерений', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r"|X|X|X|"),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row([MultiColumn(size=3, data='Время выполнения сеансов', align='|c|')])
                table.add_hline()
                table.add_row(["Номер сеанса", MultiColumn(size=2, align='c|', data=NoEscape(r'Сеанс \textnumero{}'))])
                table.add_hline(2,3)
                table.add_row(['', 'Начало', 'Конец'])
                table.add_hline()
                table.add_row(['Дата', str(data['start date']), str(data['end date'])])
                table.add_hline()
                table.add_row(['Время', str(data['start time'])+'+0 UTC', str(data['end time'])+'+0 UTC'])
                table.add_hline()
                table.add_row(['Высота антенны', data['antenna height'], data['antenna height']])
                table.add_hline()
                table.add_row(['GDOP', data['gdop'], data['gdop']])
                table.add_hline()
                table.add_row(['PDOP', data['pdop'], data['pdop']])
                table.add_hline()
    
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

        location_map = get_map(data['longitude'], data['latitude'], data['marker name'])
        location_map_path = os.path.join(os.path.dirname(filename), f'{data['marker name']}.png')
        location_map.savefig(location_map_path, bbox_inches='tight')
        insert_file = r'\includegraphics[width=0.6\textwidth]{'+location_map_path.replace('\\', '/')+'}'

        with doc.create(Subsection(title=r'Измерение высоты и схема расположение пункта', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r'|p{0.6\textwidth}|X|'),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row([
                    NoEscape(r'''Тип измерения высоты антенны:
                            (наклонная, вертикальная, вертикальная до фазового центра)'''), HEIGHT_TYPES[ant_height_type]])
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
    
    doc.append(NoEscape(r'\vfill'))
    doc.append(NoEscape(r'\hfill Подпись'))
    
    # Generate the PDF
    doc.generate_pdf(filename, clean_tex=False) 

def get_map(longitude, latitude, marker_name):
    ''' Get map of ties scheme '''

    fig = plt.figure(figsize=(15, 15))
      
    extent = [longitude - 0.01, longitude + 0.01, latitude - 0.005, latitude + 0.005]
    request = cimgt.OSM()
    ax = plt.axes(projection=request.crs)
    ax.set_extent(extent)

    zoom = 15

    ax.add_image(request, zoom)

    ax.plot(longitude, latitude, '-ok', mfc='w', transform=ccrs.PlateCarree())
   
    ax.annotate(marker_name, xy=(longitude, latitude),
        xycoords='data', xytext=(1.5, 1.5),
        textcoords='offset points',
        fontsize=14,
        color='k', transform=ccrs.PlateCarree())

    return fig
