import os
import re
import pikepdf
import georinex as gr
import pyproj
from datetime import datetime as dt
from pylatex import Document, Section, Table, Tabularx, LongTable, NoEscape,\
    Package, Command, MultiColumn, MiniPage, MultiRow, Section, Subsection
from pylatex.utils import escape_latex
import numpy as np
import geopandas as gpd
import contextily as ctx
from shapely.geometry import Point
import matplotlib.pyplot as plt
import cartopy.io.img_tiles as cimgt
from cartopy import crs as ccrs

# RINEX 2 epoch lines don't have a unique leading marker character like
# RINEX 3's '>', so they're matched by their fixed date/time/flag shape:
# " yy mm dd hh mm ss.sssssss  flag ..." at the start of the line
RINEX2_EPOCH_RE = re.compile(
    r'^\s*(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2}(?:\.\d+)?)\s+(\d)'
)

# hyperref strips underscores from PDF form field names, so this is
# written without any to begin with, avoiding any ambiguity about what
# the compiled PDF's actual field name ends up being
ANTENNA_HEIGHT_RADIO_FIELD = 'antennaheighttype'

# Must match the concatenated order of the two _radio_choice_lines() calls
# that build the "A" (no tripod) and "B" (tripod) choice widgets below
ANTENNA_HEIGHT_RADIO_VALUES = ['base', 'phase', 'tripod_slant', 'tripod_base', 'tripod_phase']


def _rinex2_year(two_digit_year):
    year = int(two_digit_year)
    return 2000 + year if year < 80 else 1900 + year

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

    rinex_version = float(header.get('version', 3))

    times = []
    count = 0
    with open(rinex_file, 'r', encoding='utf-8') as f:
        for line in f:
            count += 1
            if rinex_version >= 3:
                if not line or line[0] != '>':
                    continue
                tokens = line.split()[1:]
                if len(tokens) < 6:
                    # Auxiliary header-info epoch record (event flag 2-5),
                    # e.g. "> ... 4  1" with no timestamp - not a real
                    # observation epoch, skip quietly
                    continue
                year, month, day, hour, minute, second = tokens[:6]
            else:
                match = RINEX2_EPOCH_RE.match(line)
                if not match:
                    continue
                year, month, day, hour, minute, second = match.groups()[:6]
                year = str(_rinex2_year(year))

            try:
                times.append(
                    dt.strptime(f'{year}-{month}-{day} {hour}:{minute}:{second.split('.')[0]}', '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                print(f'Warning! Invalid time format in RINEX file, line {count}')
                continue

    if not times:
        raise ValueError(f'No valid observation epochs found in RINEX file: {rinex_file}')

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

def _form_field(name, value, as_form, width='5cm'):
    """Render a value as plain text (default path, used for the .tex that
    gets converted to .docx), or as a fillable hyperref PDF form field
    pre-filled with that value (used for the .tex that becomes the .pdf).
    """
    if not as_form:
        return value
    escaped = escape_latex(str(value))
    return NoEscape(
        r'\TextField[name=' + name + r',width=' + width +
        r',height=0.4cm,default={' + escaped + r'}]{}'
    )


def _paired_field_row(label_a, name_a, value_a, label_b, name_b, value_b, as_form, width='3cm'):
    """Combine two label/value pairs onto a single table row, to keep the
    journal compact enough to fit on one page."""
    label = f'{label_a} / {label_b}'
    if not as_form:
        return [label, f'{value_a} / {value_b}']
    field_a = _form_field(name_a, value_a, as_form, width=width)
    field_b = _form_field(name_b, value_b, as_form, width=width)
    return [label, NoEscape(str(field_a) + r'\hspace{0.8cm}' + str(field_b))]


def _radio_choice_lines(name, choices, selected_value, as_form):
    """A single-choice (mutually exclusive) selector for one of several
    named options, e.g. which specific antenna measurement point was used.

    choices is a list of (label, value) pairs. selected_value is the value
    to preselect, or None if nothing should be preselected. Returns one
    rendered line per choice (mark/widget before the label), meant to be
    placed one per row, stacked vertically under a diagram.

    In the plain (.docx) path each line is a '[x]'/'[ ]' checklist entry,
    since .docx has no equivalent of a real selectable control. In the PDF
    path each line is its own radio widget (with an empty built-in label,
    so our own label text can be placed after it instead), all sharing
    `name`. Every call for the same group must pass the same
    `selected_value` - passing it inconsistently (or omitting it on some
    calls) leaves an unresolved macro name literally visible as the value
    of the widgets that didn't set it.

    hyperref only links widgets from a single \\ChoiceMenu call into one
    true radio group; splitting a group across several calls like this
    produces several *independent* fields that merely share a name, which
    several PDF viewers do not enforce as mutually exclusive. Call
    _merge_radio_widgets() on the compiled PDF to fix that up.
    """
    if not as_form:
        return [
            f'{"[x]" if value == selected_value else "[ ]"} {label}'
            for label, value in choices
        ]
    # 'Off' is the reserved PDF value meaning "no button in this group is
    # selected" - used instead of omitting default=, which leaves the
    # field's own value as an unresolved, literally-visible macro name
    default = selected_value if selected_value is not None else 'Off'
    lines = []
    for label, value in choices:
        widget = (
            r'\ChoiceMenu[radio,name=' + name + r',default=' + default +
            r',width=0.3cm,height=0.3cm]{}{ =' + value + '}'
        )
        lines.append(NoEscape(widget + ' ' + label))
    return lines


def _merge_radio_widgets(pdf_path, field_name, values_in_order, selected_value):
    """Fix up a compiled PDF so that every /Btn field named `field_name`
    becomes one true radio group (a single field with the widgets as its
    /Kids), instead of several independent fields that only coincidentally
    share a name - see _radio_choice_lines() for why that happens.

    `values_in_order` must be the choice values in the exact order their
    widgets were written to the document (i.e. the concatenation of the
    `choices` lists passed to every _radio_choice_lines() call for this
    field name), so each compiled widget can be matched back to the value
    it represents. hyperref does not set /AS (which of a button's
    appearance states is currently shown) on these widgets at all, so it
    has to be set explicitly here too, not just /V - otherwise nothing
    appears checked even for a correctly-selected value.
    """
    pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
    acroform = pdf.Root.AcroForm
    fields = acroform.Fields

    widgets = [
        f for f in fields
        if f.get('/FT') == pikepdf.Name('/Btn') and str(f.get('/T', '')) == field_name
    ]
    if not widgets:
        pdf.close()
        return
    if len(widgets) != len(values_in_order):
        pdf.close()
        raise ValueError(
            f'Expected {len(values_in_order)} "{field_name}" radio widgets, found {len(widgets)}'
        )

    parent = pdf.make_indirect(pikepdf.Dictionary({
        '/FT': pikepdf.Name('/Btn'),
        '/T': pikepdf.String(field_name),
        '/Ff': 49152,  # Radio + NoToggleToOff, matching hyperref's own radio fields
        '/Kids': pikepdf.Array(),
    }))

    selected_state = pikepdf.Name('/Off')
    for widget, value in zip(widgets, values_in_order):
        on_key = next((k for k in widget.AP.N.keys() if k != '/Off'), None)
        if value == selected_value and on_key is not None:
            state = pikepdf.Name(on_key)
            widget['/AS'] = state
            selected_state = state
        else:
            widget['/AS'] = pikepdf.Name('/Off')
        if '/T' in widget:
            del widget['/T']
        if '/V' in widget:
            del widget['/V']
        widget['/Parent'] = parent
        parent['/Kids'].append(widget)
    parent['/V'] = selected_state

    widget_ids = {widget.objgen for widget in widgets}
    remaining_fields = pikepdf.Array(f for f in fields if f.objgen not in widget_ids)
    remaining_fields.append(parent)
    acroform.Fields = remaining_fields

    pdf.save(pdf_path)
    pdf.close()


def _build_journal_document(data, as_form, a_picture, b_picture, insert_file):
    doc = Document(
        document_options=['10pt', 'a4paper', 'final'],
        documentclass='article',
        geometry_options=['left=2cm', 'right=2cm', 'top=2cm', 'bottom=2cm'],
        inputenc='utf8',
        fontenc='OT1',
        lmodern=False,
        textcomp=True,
    )
    doc.preamble.append(Package('babel', 'russian'))
    doc.preamble.append(Package('makecell'))
    doc.preamble.append(Package('longtable'))
    doc.preamble.append(Package('graphicx'))
    if as_form:
        doc.preamble.append(Package('hyperref'))

    # babel's Russian shorthands make '"' an active character (e.g. for
    # hyphenation hints), which silently swallows following punctuation in
    # user-supplied text (e.g. 'ООО "Ромашка", ...'). babel re-enables its
    # shorthands at \begin{document}, so this must be turned off here
    # rather than in the preamble for it to actually take effect.
    doc.append(NoEscape(r'\shorthandoff{"}'))
    doc.append(Command('thispagestyle', 'empty'))

    if as_form:
        # TextField widgets only become real AcroForm fields when wrapped
        # in hyperref's Form environment
        doc.append(NoEscape(r'\begin{Form}'))

    with doc.create(Section(title='ЖУРНАЛ СПУТНИКОВЫХ НАБЛЮДЕНИЙ', numbering=False)):

        with doc.create(Subsection(title='Информация о пункте и оборудовании', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r'|l|X|'),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row([MultiColumn(size=2, data=NoEscape(r'\textbf{Общая информация}'), align='|c|')])
                table.add_hline()
                table.add_row(['Организация', _form_field('organization', data['organization'], as_form, width='10cm')])
                table.add_hline()
                table.add_row(['Наименование пункта', _form_field('marker_name', data['marker name'], as_form, width='10cm')])
                table.add_hline()
                table.add_row(['Объект', _form_field('object', data['object'], as_form, width='10cm')])
                table.add_hline()
                table.add_row(['Исполнитель (ФИО)', _form_field('operator', data['operator'], as_form, width='10cm')])
                table.add_hline()
                table.add_row([MultiColumn(size=2, data=NoEscape(r'\textbf{Местоположение}'), align='|c|')])
                table.add_hline()
                table.add_row(_paired_field_row(
                    'Широта', 'latitude', f'{data["latitude"]:.6f}',
                    'Долгота', 'longitude', f'{data["longitude"]:.6f}',
                    as_form))
                table.add_hline()
                table.add_row(_paired_field_row(
                    'Высота', 'height', f'{data["height"]:.6f}',
                    'Трапеция 1:100000', 'trapezoid', crd2cell_100(data['longitude'], data['latitude']),
                    as_form))
                table.add_hline()
                table.add_row([MultiColumn(size=2, data=NoEscape(r'\textbf{Оборудование}'), align='|c|')])
                table.add_hline()
                table.add_row(['Тип и № приемника', _form_field(
                    'receiver', f'{data["receiver type"]} {data["receiver number"]}', as_form, width='10cm')])
                table.add_hline()
                table.add_row(['Тип и № антенны', _form_field(
                    'antenna', f'{data["antenna type"]} {data["antenna number"]}', as_form, width='10cm')])
                table.add_hline()
                table.add_row([MultiColumn(size=2, data=NoEscape(r'\textbf{Характеристика пункта}'), align='|c|')])
                table.add_hline()
                table.add_row(_paired_field_row(
                    'Тип знака', 'centre_type', data['centre type'],
                    'Тип центра', 'benchmark_type', data['benchmark type'],
                    as_form, width='5cm'))
                table.add_hline()

        # Create a table to display the metadata
        with doc.create(Subsection(title='Информация о сеансе измерений', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r"|X|X|X|"),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row([MultiColumn(size=3, data='Параметры сеанса', align='|c|')])
                table.add_hline()
                table.add_row(['', 'Начало', 'Конец'])
                table.add_hline()
                table.add_row([
                    'Дата',
                    _form_field('start_date', str(data['start date']), as_form, width='2.5cm'),
                    _form_field('end_date', str(data['end date']), as_form, width='2.5cm'),
                ])
                table.add_hline()
                table.add_row([
                    'Время',
                    _form_field('start_time', str(data['start time'])+'+0 UTC', as_form, width='5cm'),
                    _form_field('end_time', str(data['end time'])+'+0 UTC', as_form, width='5cm'),
                ])
                table.add_hline()
                antenna_height_field = _form_field('antenna_height', data['antenna height'], as_form, width='2cm')
                table.add_row(['Высота антенны', antenna_height_field, antenna_height_field])
                table.add_hline()
                gdop_field = _form_field('gdop', data['gdop'], as_form, width='2cm')
                table.add_row(['GDOP', gdop_field, gdop_field])
                table.add_hline()
                pdop_field = _form_field('pdop', data['pdop'], as_form, width='2cm')
                table.add_row(['PDOP', pdop_field, pdop_field])
                table.add_hline()

        with doc.create(Subsection(title=r'Измерение высоты и схема расположение пункта', numbering=False)):
            with doc.create(
                Tabularx(
                    table_spec=NoEscape(r'|p{0.6\textwidth}|X|'),
                    width_argument=NoEscape(r'\textwidth'))) as table:
                table.add_hline()
                table.add_row(
                    [
                        'Схема расположения пункта',
                        'Зарисовка постановки антенны'
                    ]
                )
                table.add_hline()

                # Both groups share one field name and the same resolved
                # selection, so all 5 options are mutually exclusive across
                # both diagrams - picking one anywhere clears any other.
                ant_height_type = data['antenna height type']
                radio_a_lines = _radio_choice_lines(
                    ANTENNA_HEIGHT_RADIO_FIELD,
                    [('2 -- до основания', 'base'), ('3 -- до фаз. центра', 'phase')],
                    ant_height_type,
                    as_form,
                )
                radio_b_lines = _radio_choice_lines(
                    ANTENNA_HEIGHT_RADIO_FIELD,
                    [('1 -- наклонная', 'tripod_slant'), ('2 -- верт. до основания', 'tripod_base'), ('3 -- верт. до фаз. центра', 'tripod_phase')],
                    ant_height_type,
                    as_form,
                )

                table.add_row([
                    # rows: caption + picture + choices, for both A and B
                    MultiRow(2 + len(radio_a_lines) + 2 + len(radio_b_lines), data=NoEscape(insert_file)),
                    'A. Без штатива'
                ])
                table.add_row(['', NoEscape(a_picture)])
                for line in radio_a_lines:
                    table.add_row(['', line])
                table.add_row(['', 'B. На штативе'])
                table.add_row(['', NoEscape(b_picture)])
                for line in radio_b_lines:
                    table.add_row(['', line])
                table.add_hline()

    doc.append(NoEscape(r'\vfill'))
    doc.append(NoEscape(r'\hfill Подпись'))

    if as_form:
        doc.append(NoEscape(r'\end{Form}'))

    return doc


def journal_generator(data, filename):

    ant_height_type = data['antenna height type']

    abs_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), 'images'))

    if ant_height_type is None:
        a_pic_path = os.path.join(abs_path, 'default')
        b_pic_path = os.path.join(abs_path, 'tripod_default')
    elif ant_height_type in ['base', 'phase']:
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
    plt.close(location_map)
    insert_file = r'\includegraphics[width=0.6\textwidth]{'+location_map_path.replace('\\', '/')+'}'

    # PDF: fillable form fields for the values the user typed in via the
    # GUI/config, so they can be corrected by hand later without
    # regenerating. Compiled first, then its intermediate .tex/.aux/.log
    # are cleaned up so they don't clash with the plain .tex below.
    form_doc = _build_journal_document(data, True, a_picture, b_picture, insert_file)
    form_doc.generate_pdf(filename, clean_tex=True)
    _merge_radio_widgets(
        filename + '.pdf', ANTENNA_HEIGHT_RADIO_FIELD,
        ANTENNA_HEIGHT_RADIO_VALUES, data['antenna height type'],
    )

    # .tex: plain text, byte-for-byte what this function produced before
    # form fields existed - this is what gets converted to .docx, and
    # hyperref form fields would silently lose their values in that
    # conversion, so this version must never contain any.
    plain_doc = _build_journal_document(data, False, a_picture, b_picture, insert_file)
    plain_doc.generate_tex(filename)

def get_map(longitude, latitude, marker_name):
    ''' Get map of ties scheme '''

    fig = plt.figure(figsize=(15, 15))
      
    extent = [longitude - 0.01, longitude + 0.01, latitude - 0.005, latitude + 0.005]
    # request = cimgt.OSM()
    # request = cimgt.Stamen('terrain-background')
    request = cimgt.QuadtreeTiles()
    ax = plt.axes(projection=request.crs)
    ax.set_extent(extent)

    zoom = 15

    ax.add_image(request, zoom)

    ax.plot(longitude, latitude, '-^w', markersize=20, mfc='r', transform=ccrs.PlateCarree())
   
    ax.annotate(marker_name, xy=(longitude, latitude),
        xycoords='data', xytext=(20, 20),
        textcoords='offset points',
        fontsize=14,
        bbox=dict(boxstyle="round,pad=0.3", edgecolor="none", facecolor="white"),
        color='k', transform=ccrs.PlateCarree())

    return fig
