# The journal creator by information from a RINEX file

## Description

This project is designed to create a GNSS journal based on information from
RINEX files. It includes tools for processing RINEX data, geodetic
transformations, and generating reports in PDF and DOCX formats.

## Installation

To install the dependencies, use `pip`:

```sh
pip install .
```

## Usage

To run the main script, use the following command:

```sh
journal_by_rinex
```

### Fillable PDF output

The generated `.pdf` is a fillable form: Organization, Object, Operator,
geodetic mark type, benchmark type, GDOP and PDOP are real PDF form fields
(pre-filled with the values used at generation time), so they can be
corrected directly in a PDF viewer later without regenerating the journal.
Fields derived from the RINEX file itself (position, receiver/antenna,
session dates) are not form fields, since they're facts read from the data
rather than typed-in metadata.

The `.docx` is generated separately from a plain-text version of the same
journal (not from the PDF), since the conversion tool used for `.docx`
(pandoc) cannot represent PDF form fields and would otherwise silently
drop their values — so the `.docx` always has the values as plain,
non-fillable text.

### Batch processing

The GUI supports processing multiple RINEX files in one run:

* **Add files** — pick one or more RINEX files manually via a multi-select
  file dialog.
* **Add folder (recursive)** — pick a folder and recursively scan it
  (including all subfolders) for observation RINEX files matching the
  `*.??o` / `*.??O` naming pattern (e.g. `station1530.23o`); all matches are
  added to the file list.

The same metadata (organization, object, operator, benchmark/centre type,
GDOP/PDOP) and measurement type apply to every file processed in a batch.
Each generated report's filename is taken from the `MARKER NAME` field of
its RINEX header, not the source filename.

### Output location

Before clicking **Process files**, choose where the generated
`.tex`/`.pdf`/`.docx` files should go:

* **Custom folder** — all output files are written to a single folder
  chosen via **Select save path**.
* **Next to source RINEX file** — each file's output is written next to
  its own source RINEX file, which is useful when batch-processing files
  collected from multiple subfolders and avoids output files overwriting
  each other when several RINEX files share the same marker name.

### Configuration files (YAML)

Instead of retyping the organization, operator, and other metadata every
time, they can be stored in a YAML config file and loaded into the form.
See [`config.example.yaml`](config.example.yaml) for the full list of
supported fields.

* **Load config (YAML)** — pick one or more `.yaml`/`.yml` files. If several
  are selected, they are merged in order, so later files override values
  from earlier ones — handy for keeping shared defaults (organization,
  operator) in one file and per-object overrides (object name, save path)
  in another.
* **Save config (YAML)** — write the current form values to a YAML file for
  reuse next time.
* If a file named `config.yaml` or `config.yml` exists in the directory the
  app is started from, it is loaded automatically on startup.

### Random GDOP/PDOP

Instead of typing a fixed GDOP/PDOP value, check **Random, range:** next to
either field to have each file draw its own value from a range (default
1.5–2.0). The fixed value field is disabled while random mode is active.
This is also configurable via YAML with `gdop_random`/`gdop_min`/`gdop_max`
and the `pdop_*` equivalents — see
[`config.example.yaml`](config.example.yaml).

By default, all values in a config file apply to every file in the batch.
To use different metadata for different files in the same batch, add a
`file_rules` list: each rule has a `pattern` (matched against the file's
basename, or its full path if the pattern contains a `/`) and any fields
to override for files matching that pattern — see the `file_rules` example
in [`config.example.yaml`](config.example.yaml). Matching rules are applied
on top of the global values, in order, for that file only.

### Reviewing and correcting a batch (Save YAML)

Check **Save YAML** before clicking **Process files** to have the app write
out a YAML config right after processing, containing one `file_rules` entry
per processed file — matched by its exact path — with the exact parameters
that were applied to it (including any randomly drawn GDOP/PDOP values and
any earlier `file_rules` overrides). You'll be prompted for where to save
it.

This is meant as a round-trip workflow: open the saved file, correct
whatever needs fixing for individual files (e.g. a wrong object name), then
load it back via **Load config (YAML)** before the next run — the corrected
values are applied to those exact files again, individually.

## Dependencies

The project uses the following libraries:

* `tk` - for GUI
* `georinex` - for processing RINEX files
* `pyproj` - for geodetic transformations
* `pylatex` - for generating PDFs
* `pypandoc` - for generating DOCX files
* `geopandas` - for processing geospatial data
* `centextily` - for basemaps
* `cartopy` - for visualizing geospatial data
* `pyyaml` - for YAML configuration file support

## Project Structure

* `examples/` - usage examples
* `journal_by_rinex/` - main directory with source code
* `setup.py` - installation script

## Author

Roman Sermiagin
[roman.sermiagin@gmail.com](mailto:roman.sermiagin@gmail.com)

## License

This project is licensed under the MIT License. See the LICENSE file for
details.
