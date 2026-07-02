# GESI Hanoi Offices

A small CSV-driven Folium project that generates a static `index.html` map for GitHub Pages.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Update Locations

Edit `data/workplaces.csv`.

Required columns:

- `location_name`
- `people`
- `address`
- `latitude`
- `longitude`

`people` can contain one person or a comma/semicolon-separated list. If you keep
multiple rows for the same location, the generator combines them into one marker
and merges the people names.

Latitude and longitude are required because static map generation should use verified coordinates. Addresses are displayed in popups, and a geocoding step can be added later if you want to turn addresses into coordinates automatically.

The generated map keeps the default Leaflet and basemap attribution visible
because hosted map tile providers require it.

## Generate The Map

```bash
python generate_map.py
```

This writes `index.html` at the project root. Commit `index.html`, `generate_map.py`, `requirements.txt`, and `data/workplaces.csv`, then enable GitHub Pages for the repository root.

You can also use a different CSV or output path:

```bash
python generate_map.py --input data/workplaces.csv --output index.html
```
