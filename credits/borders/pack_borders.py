"""Packs simplified outlines (GeoJSON features with a "code" property, from mapshaper) into the app's binary format,
read lazily one place at a time by `BorderPack` in the app.

Pipeline for the precise outlines (geoBoundaries CGAZ: CC BY 4.0, ODbL © OpenStreetMap contributors and others, see
the credits page):
    prepare_precise_borders.py … precise.geojson
    mapshaper-xl 12gb precise.geojson -simplify interval=<metres> keep-shapes -o precision=0.00001 <level>.geojson
    pack_borders.py <level>.geojson <islet> TravelTo/<file>.bin
for each level: BordersRegion (1500 m, islet 0.01), BordersNear (400 m, islet 0.0005), BordersFine (100 m, islet
0.00002). Each serves the zoom where its error stays about one point on screen (see `Borders.Detail`).
mapshaper simplifies each shared border once, so neighbours keep the very same line.

Format, little-endian:
    "TTB1", u32 place count, then per place: u8 code length, code (ASCII), u32 offset, u32 length (from the file start)
    a place: varint piece count, then per piece (largest first): varint ring count, then per ring (outer first):
        varint point count, points as zigzag varint deltas of (longitude, latitude) in units of 1e-4 degree (11 m),
        the first one from (0, 0).
A piece whose bounding box is under <islet> square degrees is dropped, except a place's largest one.

usage: pack_borders.py <simplified.geojson> <islet> <output.bin>
"""
import json, struct, sys

source, islet, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
UNIT = 10_000


def varint(value):
    data = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            data.append(byte | 0x80)
        else:
            data.append(byte)
            return bytes(data)


def zigzag(value):
    return (value << 1) ^ (value >> 63)


def box(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def ring_points(ring):
    points = []
    for x, y in ring[:-1]:  # GeoJSON repeats the first point at the end
        p = (round(x * UNIT), round(y * UNIT))
        if not points or points[-1] != p:
            points.append(p)
    return points if len(points) >= 3 else None


shapes = {}
for feature in json.load(open(source))["features"]:
    geometry = feature["geometry"]
    if geometry:
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        shapes.setdefault(feature["properties"]["code"], []).extend(polygons)

blobs, total = {}, 0
for code in sorted(shapes):
    pieces = []
    for index, polygon in enumerate(sorted(shapes[code], key=lambda polygon: -box(polygon[0]))):
        if index > 0 and box(polygon[0]) < islet:
            continue
        outer = ring_points(polygon[0])
        if not outer:
            continue
        holes = [ring_points(hole) for hole in polygon[1:] if box(hole) >= islet * 2]
        pieces.append([outer] + [hole for hole in holes if hole])
    blob = bytearray(varint(len(pieces)))
    last = (0, 0)
    for rings in pieces:
        blob += varint(len(rings))
        for ring in rings:
            blob += varint(len(ring))
            for x, y in ring:
                blob += varint(zigzag(x - last[0])) + varint(zigzag(y - last[1]))
                last = (x, y)
            total += len(ring)
    blobs[code] = bytes(blob)

header = bytearray(b"TTB1" + struct.pack("<I", len(blobs)))
index_size = sum(1 + len(code) + 8 for code in blobs)
offset = len(header) + index_size
body = bytearray()
for code, blob in blobs.items():
    header += bytes([len(code)]) + code.encode("ascii") + struct.pack("<II", offset + len(body), len(blob))
    body += blob
open(out, "wb").write(header + body)
print(len(blobs), "places,", total, "points,", len(header) + len(body), "bytes")
