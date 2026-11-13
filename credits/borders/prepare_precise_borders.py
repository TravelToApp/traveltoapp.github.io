"""First step of the outlines: picks from geoBoundaries' CGAZ files (CC BY 4.0) the shapes of the countries and US
states in the app's catalog, tagged with the catalog's code, as one GeoJSON for mapshaper.

Greenland and Antarctica are places of their own in the catalog. The areas CGAZ keeps apart as disputed (Western Sahara, Aksai Chin, the Falklands…) are kept too, tagged "~" + their
CGAZ group ("~ESH", "~112"): the app outlines them, dashed, without giving them to any country. Simplifying them with
the countries keeps their edges on the very same lines.

Then mapshaper and pack_borders.py (see its docstring) make TravelTo/BordersMid.bin and TravelTo/BordersFine.bin.
Sources and licences of each country's borders: geoBoundariesOpen-meta.csv in the geoBoundaries repository.

usage: prepare_precise_borders.py <geoBoundariesCGAZ_ADM0.geojson> <geoBoundariesCGAZ_ADM1.geojson>
                                  <ne_10m_admin_0_countries.geojson> <PlaceCatalog.swift> <output.geojson>
"""
import json, re, sys

adm0, adm1, natural_earth, catalog, out = sys.argv[1:6]
source = open(catalog, encoding="utf-8").read()
def rows(name):
    text = re.search(name + r' = """\n(.*?)"""', source, re.S).group(1)
    return [[field.strip() for field in row.split(",")] for row in text.replace("\\\n", "").split(";") if row.strip()]
countries = {row[0] for row in rows("countryData")}
states = {row[1]: "US-" + row[0] for row in rows("stateData")}
states["District of Columbia"] = "US-DC"  # the catalog calls it Washington D.C.

# ISO 3166 alpha-3 (CGAZ's shapeGroup) to alpha-2 (the catalog's codes), from Natural Earth.
alpha2 = {"XKX": "XK", "118": "PS", "129": "PS"}  # Kosovo; the Gaza Strip and the West Bank
for feature in json.load(open(natural_earth))["features"]:
    p = feature["properties"]
    code = p["ISO_A2_EH"] if p["ISO_A2_EH"] != "-99" else p["ISO_A2"]
    for key in ("ISO_A3", "ADM0_A3", "ISO_A3_EH"):
        if p.get(key) not in (None, "-99") and code != "-99":
            alpha2.setdefault(p[key], code)

def split_at_greenwich(geometry):
    """Antarctica's outline runs all around the South Pole, which the map fills wrongly when seen from afar (from
    its northernmost point down, ocean included). Each such ring becomes a western and an eastern half, cut along
    the Greenwich meridian; the map draws Antarctica without an outline, so the cut doesn't show."""
    def half(ring, keep):
        out = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if keep(a[0]):
                out.append(a)
            if keep(a[0]) != keep(b[0]) and a[0] != b[0]:
                t = (0 - a[0]) / (b[0] - a[0])
                out.append([0.0, a[1] + (b[1] - a[1]) * t])
        return out + out[:1] if len(out) >= 3 else None
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    result = []
    for polygon in polygons:
        outer = polygon[0]
        if max(x for x, _ in outer) - min(x for x, _ in outer) < 300:
            result.append(polygon)
            continue
        ring = outer[:-1]
        for keep in (lambda x: x <= 0, lambda x: x >= 0):
            cut = half(ring, keep)
            if cut:
                result.append([cut])
    return {"type": "MultiPolygon", "coordinates": result}


features = []
for feature in json.load(open(adm0))["features"]:
    group = feature["properties"]["shapeGroup"]
    code = alpha2.get(group)
    if code not in countries and (group.isdigit() or group == "ESH"):
        code = "~" + group  # a disputed area
    if code in countries or code.startswith("~"):
        geometry = split_at_greenwich(feature["geometry"]) if code == "AQ" else feature["geometry"]
        features.append({"type": "Feature", "properties": {"code": code}, "geometry": geometry})
for feature in json.load(open(adm1))["features"]:
    p = feature["properties"]
    if p["shapeGroup"] == "USA" and p["shapeName"] in states:
        features.append({"type": "Feature", "properties": {"code": states[p["shapeName"]]}, "geometry": feature["geometry"]})

found = {f["properties"]["code"] for f in features}
json.dump({"type": "FeatureCollection", "features": features}, open(out, "w"), separators=(",", ":"))
print(len(features), "shapes; without one:", sorted((countries | set(states.values())) - found))
