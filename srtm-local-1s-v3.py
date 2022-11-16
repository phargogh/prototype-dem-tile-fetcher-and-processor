import json
import logging
import os
import zipfile

import pygeoprocessing
import requests
import shapely.geometry
import shapely.prepared
from osgeo import gdal

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

# GDAL has an STRM driver!
# https://gdal.org/drivers/raster/srtmhgt.html
# Can read the HGT format directly, even from the zipfile.
#
# Process for our first stab at this
#  preprocessing:
#     use the massive list of files to extract bounding boxes with GDAL
#        write out a large JSON file with all the data.
#     commit the large file list and json to this repo
#
#  program to run on user's computer:
#     prompt user for NASA EarthData Username and Password
#     load the tile bboxes into an RTree
#     figure out which tiles intersect the user's bbox
#     download those tiles
#     create a VRT
#     Do a raster_calculator call
#
#  program to run on Sherlock
#     use environment variables for username and password
#     use "global" as a shortcut for "grab everything"
#     download everything
#     create a VRT
#     do a raster_calculator call if needed


def main(bbox, cache_dir, target_vrt):
    LOGGER.info(f"Finding intersecting SRTM tiles for {bbox}")

    srtm_data_file = os.path.join(
        os.path.dirname(__file__), 'srtm-data', 'srtm_bboxes.json')
    LOGGER.info("Loading SRTM data")
    with open(srtm_data_file) as tiles_data:
        srtm_tiles = json.load(tiles_data)

    LOGGER.info("SRTM data loaded")

    if bbox != 'global':
        bounding_box = shapely.prepared.prep(shapely.geometry.box(*bbox))

        intersecting_tiles = []
        for srtm_zipfile, coord_list in srtm_tiles.items():
            tile = shapely.geometry.Polygon(coord_list)
            if bounding_box.intersects(tile):
                intersecting_tiles.append(srtm_zipfile)
    else:
        intersecting_tiles = list(srtm_tiles.keys())

    LOGGER.info(f"{len(intersecting_tiles)} intersecting tiles found")

    valid_intersecting_tiles = []
    for index, tile in enumerate(intersecting_tiles):
        LOGGER.info(
            f"({index}/{len(intersecting_tiles)} "
            f"Determining GDAL-readable filepath for {tile}")
        filepath = os.path.join(cache_dir, tile)
        raster = gdal.Open(filepath)
        if raster is None:
            old_filepath = filepath
            with zipfile.ZipFile(filepath) as srtm_archive:
                sub_filename = srtm_archive.infolist()[0].filename
            filepath = f'/vsizip/{old_filepath}/{sub_filename}'
            raster = gdal.Open(filepath)
            if raster is None:
                raise AssertionError(
                    f'Could not open {tile} at either {old_filepath} '
                    f'or {filepath}')

        raster = None
        valid_intersecting_tiles.append(filepath)

    gdal.BuildVRT(target_vrt, valid_intersecting_tiles)


if __name__ == '__main__':
    # bounding box for the state of california
    ca_bbox = [-124.53, 32.82, -113.71, 42]
    main(ca_bbox, '/scratch/users/jadoug06/srtm-global-30m', 'ca.vrt')
