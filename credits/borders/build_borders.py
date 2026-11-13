"""Builds TravelTo/Borders.txt, the outlines the map draws from afar, in text.

They come from the same geoBoundaries shapes as the precise outlines (prepare_precise_borders.py, pack_borders.py), so
a place looks the same at every zoom: Natural Earth, used before, drew Morocco with most of Western Sahara, which
geoBoundaries keeps apart, and the map changed its border while zooming. mapshaper simplifies each border shared by
two places once, so neighbours keep exactly the same line.

    mapshaper-xl 12gb precise.geojson -simplify interval=5000 keep-shapes -o precision=0.00001 far.geojson
    build_borders.py write far.geojson 0.02 1000 TravelTo/Borders.txt

`build_borders.py tag` makes the same kind of input from Natural Earth (ne_<scale>_admin_0_countries and
ne_<scale>_admin_1_states_provinces), no longer used by the app:
    build_borders.py tag <folder> <scale> TravelTo/Models/PlaceCatalog.swift <tagged.geojson>

Output: one line per place, CODE|polygon;polygon — a polygon is ring/ring (the outer ring, then its holes), a ring is
"lon,lat lon,lat …" in degrees times <divisor>. The pieces of a place are listed from the largest down. A piece whose
bounding box is under <islet> square degrees is dropped, except a place's largest one.
"""
import json, re, sys


def tag(folder, scale, catalog, out):
    source = open(catalog, encoding="utf-8").read()
    def block(name):
        text = re.search(name + r' = """\n(.*?)"""', source, re.S).group(1)
        return [row.split(",")[0].strip() for row in text.replace("\\\n", "").split(";") if row.strip()]
    countries, states = set(block("countryData")), {"US-" + code for code in block("stateData")}
    aliases = {"KOS": "XK", "CYN": "CY", "SOL": "SO", "TWN": "TW", "PSX": "PS", "FRA": "FR", "NOR": "NO"}
    features = []
    for feature in json.load(open(f"{folder}/ne_{scale}_admin_0_countries.geojson"))["features"]:
        p = feature["properties"]
        code = aliases.get(p["ADM0_A3"]) or (p["ISO_A2_EH"] if p["ISO_A2_EH"] != "-99" else p["ISO_A2"])
        if code in countries:
            features.append({"type": "Feature", "properties": {"code": code}, "geometry": feature["geometry"]})
    for feature in json.load(open(f"{folder}/ne_{scale}_admin_1_states_provinces.geojson"))["features"]:
        code = feature["properties"].get("iso_3166_2")
        if code in states:
            features.append({"type": "Feature", "properties": {"code": code}, "geometry": feature["geometry"]})
    json.dump({"type": "FeatureCollection", "features": features}, open(out, "w"), separators=(",", ":"))
    found = {f["properties"]["code"] for f in features}
    print(len(features), "shapes; without one:", sorted((countries | states) - found))


def write(simplified, islet, divisor, out):
    def box(ring):
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    def ring_text(ring):
        points = []
        for x, y in ring[:-1]:  # GeoJSON repeats the first point at the end
            p = (round(x * divisor), round(y * divisor))
            if not points or points[-1] != p:
                points.append(p)
        return " ".join(f"{x},{y}" for x, y in points) if len(points) >= 3 else None

    shapes = {}
    for feature in json.load(open(simplified))["features"]:
        geometry = feature["geometry"]
        if not geometry:
            continue
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        shapes.setdefault(feature["properties"]["code"], []).extend(polygons)

    lines, points = [], 0
    for code in sorted(shapes):
        pieces = sorted(shapes[code], key=lambda polygon: -box(polygon[0]))
        texts = []
        for index, polygon in enumerate(pieces):
            if index > 0 and box(polygon[0]) < islet:
                continue
            outer = ring_text(polygon[0])
            if not outer:
                continue
            holes = [ring_text(hole) for hole in polygon[1:] if box(hole) >= islet * 2]
            texts.append("/".join([outer] + [hole for hole in holes if hole]))
        if texts:
            lines.append(f"{code}|{';'.join(texts)}")
            points += sum(text.count(",") for text in texts)
    open(out, "w", encoding="utf-8").write(
        f"# code|polygons — degrees times {divisor}; sources and steps in docs/build_borders.py\n"
        + "\n".join(lines) + "\n")
    print(len(lines), "places,", points, "points")


if __name__ == "__main__":
    if sys.argv[1] == "tag":
        tag(*sys.argv[2:6])
    else:
        write(sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
