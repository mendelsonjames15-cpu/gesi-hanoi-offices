from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode

import folium


DEFAULT_INPUT = Path("data/workplaces.csv")
DEFAULT_OUTPUT = Path("index.html")
DEFAULT_CENTER = (21.0278, 105.8342)
SITE_TITLE = "GESI Hanoi Offices"
INITIAL_BOUNDS_PADDING = (56, 56)
MAX_INITIAL_ZOOM = 12
MARKER_COLORS = [
    ("red", "#d94841"),
    ("blue", "#2f80ed"),
    ("green", "#219653"),
    ("orange", "#f2994a"),
    ("purple", "#7b61ff"),
    ("yellow", "#f2c94c"),
]


@dataclass(frozen=True)
class WorkplaceLocation:
    location_name: str
    people: tuple[str, ...]
    address: str
    latitude: float
    longitude: float


def clean(value: str | None) -> str:
    return (value or "").strip()


def split_people(value: str) -> tuple[str, ...]:
    return tuple(
        person.strip()
        for person in value.replace(";", ",").split(",")
        if person.strip()
    )


def format_people(people: tuple[str, ...]) -> str:
    if len(people) <= 1:
        return people[0] if people else ""
    if len(people) == 2:
        return " & ".join(people)
    return f"{', '.join(people[:-1])}, & {people[-1]}"


def merge_locations(locations: list[WorkplaceLocation]) -> list[WorkplaceLocation]:
    merged: dict[tuple[str, str, float, float], WorkplaceLocation] = {}

    for location in locations:
        key = (
            location.location_name,
            location.address,
            location.latitude,
            location.longitude,
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = location
            continue

        people = list(existing.people)
        for person in location.people:
            if person not in people:
                people.append(person)

        merged[key] = WorkplaceLocation(
            location_name=existing.location_name,
            people=tuple(people),
            address=existing.address,
            latitude=existing.latitude,
            longitude=existing.longitude,
        )

    return list(merged.values())


def read_locations(csv_path: Path) -> list[WorkplaceLocation]:
    locations: list[WorkplaceLocation] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = {"address", "latitude", "longitude"} - fieldnames
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"{csv_path} is missing required column(s): {missing}")

        if (
            "location_name" not in fieldnames
            and "workplace" not in fieldnames
            and "name" not in fieldnames
        ):
            raise ValueError(
                f"{csv_path} must include location_name, workplace, or name for marker titles"
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                latitude = float(clean(row.get("latitude")))
                longitude = float(clean(row.get("longitude")))
            except ValueError as exc:
                raise ValueError(
                    f"{csv_path}:{row_number} has invalid latitude/longitude"
                ) from exc

            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError(f"{csv_path}:{row_number} has coordinates out of range")

            location_name = (
                clean(row.get("location_name"))
                or clean(row.get("workplace"))
                or clean(row.get("name"))
                or "Workplace"
            )
            people_value = clean(row.get("people")) or clean(row.get("name"))

            locations.append(
                WorkplaceLocation(
                    location_name=location_name,
                    people=split_people(people_value),
                    address=clean(row.get("address")),
                    latitude=latitude,
                    longitude=longitude,
                )
            )

    return merge_locations(locations)


def google_maps_url(location: WorkplaceLocation) -> str:
    query = f"{location.latitude},{location.longitude}"
    return f"https://www.google.com/maps/search/?{urlencode({'api': '1', 'query': query})}"


def popup_html(location: WorkplaceLocation) -> str:
    people = format_people(location.people)
    maps_url = google_maps_url(location)
    rows: list[tuple[str, str, bool]] = [
        ("People", people, False),
        ("Address", location.address, False),
        ("Google Maps", maps_url, True),
    ]
    details = "\n".join(
        popup_row(label, value, is_link)
        for label, value, is_link in rows
        if value
    )
    title = html.escape(location.location_name)

    return f"""
    <section class="popup">
      <h3>{title}</h3>
      <dl>{details}</dl>
    </section>
    """


def popup_row(label: str, value: str, is_link: bool = False) -> str:
    escaped_label = html.escape(label)
    escaped_value = html.escape(value)
    if is_link:
        content = (
            f'<a href="{escaped_value}" target="_blank" rel="noopener noreferrer">'
            "Open in Google Maps"
            "</a>"
        )
    else:
        content = escaped_value
    return f"<dt>{escaped_label}</dt><dd>{content}</dd>"


def marker_colors(count: int) -> list[tuple[str, str]]:
    if count > len(MARKER_COLORS):
        raise ValueError(
            f"The map has {count} locations, but only {len(MARKER_COLORS)} unique marker colors are available."
        )
    return MARKER_COLORS[:count]


def legend_html(
    locations: list[WorkplaceLocation],
    colors: list[tuple[str, str]],
) -> str:
    rows = "\n".join(
        f"""
        <li>
          <span class="legend-marker" style="background: {html.escape(hex_color)}"></span>
          <span>{html.escape(format_people(location.people) or location.location_name)}</span>
        </li>
        """
        for location, (_color_name, hex_color) in zip(locations, colors)
    )
    return f"""
    <section class="map-legend">
      <h2>Offices</h2>
      <ul>{rows}</ul>
    </section>
    """


def build_map(locations: list[WorkplaceLocation]) -> folium.Map:
    map_ = folium.Map(
        location=DEFAULT_CENTER,
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )

    colors = marker_colors(len(locations))
    for location, (_color_name, hex_color) in zip(locations, colors):
        folium.CircleMarker(
            location=(location.latitude, location.longitude),
            radius=8,
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color=hex_color,
            fill_opacity=0.95,
            popup=folium.Popup(popup_html(location), max_width=340),
        ).add_to(map_)

    if locations:
        map_.fit_bounds(
            [(location.latitude, location.longitude) for location in locations],
            padding=INITIAL_BOUNDS_PADDING,
            max_zoom=MAX_INITIAL_ZOOM,
        )

    legend = folium.Element(legend_html(locations, colors))
    map_.get_root().html.add_child(legend)

    return map_


def inject_styles(html_text: str) -> str:
    styles = """
    <style>
      html, body, .folium-map {
        height: 100%;
      }

      body {
        margin: 0;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .leaflet-popup-content {
        margin: 14px 16px;
      }

      .popup h3 {
        margin: 0 0 10px;
        color: #1f2937;
        font-size: 16px;
        line-height: 1.25;
      }

      .popup dl {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 6px 10px;
        margin: 0;
        color: #374151;
        font-size: 13px;
        line-height: 1.35;
      }

      .popup dt {
        color: #6b7280;
        font-weight: 700;
      }

      .popup dd {
        margin: 0;
      }

      .popup a {
        color: #2563eb;
        font-weight: 700;
        text-decoration: none;
      }

      .popup a:hover {
        text-decoration: underline;
      }

      .map-legend {
        position: fixed;
        top: 12px;
        right: 12px;
        z-index: 9999;
        min-width: 126px;
        max-width: min(180px, calc(100vw - 86px));
        max-height: calc(100vh - 92px);
        overflow-y: auto;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid rgba(31, 41, 55, 0.16);
        border-radius: 6px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.18);
        color: #111827;
        padding: 10px 12px;
      }

      .map-legend h2 {
        margin: 0 0 8px;
        color: #111827;
        font-size: 13px;
        line-height: 1.2;
      }

      .map-legend ul {
        display: grid;
        gap: 7px;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .map-legend li {
        display: flex;
        align-items: center;
        gap: 7px;
        color: #374151;
        font-size: 12px;
        font-weight: 700;
        line-height: 1.2;
      }

      .legend-marker {
        display: inline-block;
        flex: 0 0 auto;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 1px solid rgba(17, 24, 39, 0.28);
      }

      @media (max-width: 520px) {
        .map-legend {
          top: 8px;
          right: 8px;
          max-width: min(150px, calc(100vw - 78px));
          max-height: 42vh;
          padding: 8px 10px;
        }

        .map-legend li {
          font-size: 11px;
        }
      }
    </style>
    """
    if "<title>" not in html_text:
        html_text = html_text.replace(
            "<head>",
            f"<head>\n    <title>{SITE_TITLE}</title>",
            1,
        )
    return html_text.replace("</head>", f"{styles}\n</head>")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a static Hanoi workplace map from a CSV file."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    locations = read_locations(args.input)
    map_ = build_map(locations)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    map_.save(str(args.output))
    generated_html = args.output.read_text(encoding="utf-8")
    args.output.write_text(inject_styles(generated_html), encoding="utf-8")
    print(f"Wrote {args.output} with {len(locations)} location(s).")


if __name__ == "__main__":
    main()
