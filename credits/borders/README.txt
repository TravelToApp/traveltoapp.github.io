TravelTo country borders: how they are made

Sources
- geoBoundaries CGAZ ADM0 and ADM1 (https://www.geoboundaries.org), CC BY 4.0; many countries in it come from
  OpenStreetMap (© OpenStreetMap contributors, ODbL 1.0), others from sources under their own licences, listed in
  https://github.com/wmgeolab/geoBoundaries/blob/main/releaseData/geoBoundariesOpen-meta.csv

Steps (the scripts are in this folder; mapshaper is the npm package of the same name)
1. prepare_precise_borders.py keeps from CGAZ the shapes of the places in TravelTo's catalog (countries, Greenland,
   Antarctica, US states), tagged with their ISO code (the Gaza Strip and the West Bank together as Palestine), and
   the areas CGAZ marks as disputed, kept apart and given to no country. Antarctica is cut in two along the Greenwich
   meridian so that no outline runs around the pole.
2. mapshaper simplifies them, each shared border once, at 5000, 1500, 400 and 100 m:
     mapshaper-xl 12gb precise.geojson -simplify interval=<metres> keep-shapes -o precision=0.00001 <level>.geojson
3. build_borders.py (5000 m, the map from afar) and pack_borders.py (the other three) round the points, drop islands
   under a size given in each script except each place's largest piece, and write the app's files.

Nothing else is changed. The resulting files are available on request: traveltoapp1@gmail.com
