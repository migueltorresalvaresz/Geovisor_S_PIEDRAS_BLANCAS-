import json
import os
import shutil
import tempfile

import arcpy


ROOT = os.path.dirname(os.path.abspath(__file__))
BUILDINGS = os.path.join(ROOT, "construcciones_piedras_blancas.geojson")
ZONING = os.path.join(ROOT, "pot_piedras_blancas.geojson")
OUT_DIR = os.path.join(ROOT, "construcciones_pot_2014")
OUT_NAME = "construcciones_pot_2014.shp"
SR = arcpy.SpatialReference(4326)


def load_geojson(path):
    with open(path, encoding="utf-8") as source:
        return json.load(source)["features"]


def polygon_from_geojson(geometry):
    kind = geometry["type"]
    coords = geometry["coordinates"]
    groups = [coords] if kind == "Polygon" else coords
    parts = arcpy.Array()
    for polygon in groups:
        rings = arcpy.Array()
        for ring in polygon:
            points = arcpy.Array([arcpy.Point(x, y) for x, y, *_ in ring])
            rings.add(points)
        parts.add(rings)
    return arcpy.Polygon(parts, SR)


def create_input(path, name, features, fields):
    fc = os.path.join(path, name)
    arcpy.management.CreateFeatureclass(path, name, "POLYGON", spatial_reference=SR)
    for field_name, field_type, length in fields:
        kwargs = {"field_length": length} if length else {}
        arcpy.management.AddField(fc, field_name, field_type, **kwargs)
    names = [field[0] for field in fields]
    with arcpy.da.InsertCursor(fc, ["SHAPE@"] + names) as cursor:
        for feature in features:
            props = feature.get("properties") or {}
            cursor.insertRow([polygon_from_geojson(feature["geometry"])] + [props.get(key) for key in names])
    return fc


def main():
    buildings = load_geojson(BUILDINGS)
    zoning = load_geojson(ZONING)
    os.makedirs(OUT_DIR, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="pot2014_")
    try:
        gdb = os.path.join(scratch, "work.gdb")
        arcpy.management.CreateFileGDB(scratch, "work.gdb")
        b_fields = [
            ("FID_ORIG", "LONG", None), ("COBAMA", "LONG", None),
            ("CBML", "TEXT", 30), ("ID_CONSTR", "TEXT", 40),
            ("AREA_CONST", "DOUBLE", None), ("TIPO_CONST", "TEXT", 20),
        ]
        z_fields = [
            ("COD_POT", "LONG", None), ("SUBCOD_POT", "LONG", None),
            ("USO_POT", "TEXT", 100), ("SUBCAT_POT", "TEXT", 150),
        ]
        b_fc = create_input(gdb, "construcciones", buildings, b_fields)
        z_fc = create_input(gdb, "zonificacion", zoning, z_fields)
        joined = os.path.join(gdb, "construcciones_pot")
        arcpy.analysis.SpatialJoin(
            b_fc, z_fc, joined, "JOIN_ONE_TO_ONE", "KEEP_COMMON", match_option="INTERSECT"
        )

        out_fc = os.path.join(OUT_DIR, OUT_NAME)
        if arcpy.Exists(out_fc):
            arcpy.management.Delete(out_fc)
        arcpy.conversion.FeatureClassToFeatureClass(joined, OUT_DIR, OUT_NAME)
        count = int(arcpy.management.GetCount(out_fc)[0])
        print("Construcciones intersectadas con POT:", count)
        print("Shapefile:", out_fc)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
