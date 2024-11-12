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
