from __future__ import annotations

import argparse
import csv
import html
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode

import folium


DEFAULT_INPUT = Path("data/workplaces.csv")
DEFAULT_OUTPUT = Path("index.html")
DEFAULT_CENTER = (21.0278, 105.8342)
SITE_TITLE = "GESI Hanoi Offices"
MARKER_COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "lightred",
    "darkblue",
    "darkgreen",
    "cadetblue",
    "darkpurple",
    "pink",
    "lightblue",
    "lightgreen",
    "gray",
    "black",
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
    people = ", ".join(location.people)
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


def random_marker_colors(count: int) -> list[str]:
    if count > len(MARKER_COLORS):
        raise ValueError(
            f"The map has {count} locations, but only {len(MARKER_COLORS)} unique marker colors are available."
        )
    return random.sample(MARKER_COLORS, count)


def build_map(locations: list[WorkplaceLocation]) -> folium.Map:
    if locations:
        center = (
            mean(location.latitude for location in locations),
            mean(location.longitude for location in locations),
        )
        zoom_start = 12
    else:
        center = DEFAULT_CENTER
        zoom_start = 11

    map_ = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )

    colors = random_marker_colors(len(locations))
    for location, color in zip(locations, colors):
        folium.Marker(
            location=(location.latitude, location.longitude),
            popup=folium.Popup(popup_html(location), max_width=340),
            tooltip=location.location_name,
            icon=folium.Icon(color=color, icon="briefcase", prefix="fa"),
        ).add_to(map_)

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
