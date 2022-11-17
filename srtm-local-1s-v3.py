import argparse
import json
import logging
import math
import os
import time
import zipfile

import pygeoprocessing
import shapely.geometry
import shapely.prepared
from osgeo import gdal

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)
DEFAULT_GTIFF_CREATION_TUPLE_OPTIONS = ('GTIFF', (
    'TILED=YES', 'BIGTIFF=YES', 'COMPRESS=LZW', 'NUM_THREADS=4',
    'BLOCKXSIZE=256', 'BLOCKYSIZE=256'))

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


def build_overviews(raster_path, internal=False,
                    resampling_method=gdal.GRA_NearestNeighbour):
    open_flags = gdal.OF_RASTER
    if internal:
        open_flags |= gdal.GA_Update
        LOGGER.info(f"Building internal overviews on {raster_path}")
    else:
        LOGGER.info("Building external overviews.")
    raster = gdal.OpenEx(raster_path, open_flags)
    n_pixels_x = raster.RasterXSize
    n_pixels_y = raster.RasterYSize

    # This loop and limiting factor borrowed from gdaladdo.cpp
    overview_scales = []
    factor = 2
    limiting_factor = 256
    while (math.ceil(n_pixels_x / factor) > limiting_factor or
           math.ceil(n_pixels_y / factor) > limiting_factor):
        overview_scales.append(factor)
        factor *= 2

    def overviews_progress(*args, **kwargs):
        pct_complete, name, other = args
        percent = round(pct_complete * 100, 2)
        if time.time() - overviews_progress.last_progress_report > 5.0:
            LOGGER.info(f"Overviews progress: {percent}%")
            overviews_progress.last_progress_report = time.time()
    overviews_progress.last_progress_report = time.time()

    LOGGER.debug(f"Using overviews {overview_scales}")
    result = raster.BuildOverviews('NEAREST', overviewlist=overview_scales,
                                   callback=overviews_progress)
    LOGGER.info(f"Overviews completed for {raster_path}")
    if result:  # Result will be nonzero on error.
        raise RuntimeError(
            f"Building overviews failed or was interrupted for {raster_path}")


def _identity(matrix):
    return matrix


def srtm(bbox, cache_dir, target_vrt, target_gtiff):
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
    last_time_logged = time.time()
    for index, tile in enumerate(intersecting_tiles):
        subdir = tile[:4]  # subdirectory prefix; for lustre performance
        if time.time() - last_time_logged > 5.0:
            LOGGER.info(
                f"({index+1}/{len(intersecting_tiles)}) "
                f"Determining GDAL-readable filepath for {tile}")
            last_time_logged = time.time()

        filepath = os.path.join(cache_dir, subdir, tile)
        raster = gdal.Open(filepath)
        if raster is None:
            LOGGER.info(f"Falling back to zipfile checking for {tile}")
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

    vrt_raster_info = pygeoprocessing.get_raster_info(target_vrt)

    pygeoprocessing.geoprocessing.raster_calculator(**{
        'base_raster_path_band_const_list': [(target_vrt, 1)],
        'local_op': _identity,
        'target_raster_path': target_gtiff,
        'datatype_target': vrt_raster_info['datatype'],
        'nodata_target': vrt_raster_info['nodata'][0],
        'raster_driver_creation_tuple': DEFAULT_GTIFF_CREATION_TUPLE_OPTIONS,
        'largest_block': 2**18,  # 4x the size of default pgp blocksize
    })
    build_overviews(target_gtiff, internal=False)


def main(args=None):
    parser = argparse.ArgumentParser(
        prog='SRTM Tile Merger',
        description='Merge SRTM tiles')
    parser.add_argument('--extent')  # "minx,miny,maxx,maxy"
    parser.add_argument('--cache-dir')
    parser.add_argument('--vrt-path')
    parser.add_argument('--gtiff-path')

    parsed_args = parser.parse_args(args)

    try:
        bbox = [float(x) for x in parsed_args.extent.split(',')],
    except ValueError:
        # user provided "global", which is a-ok
        bbox = parsed_args.extent

    srtm(
        bbox,
        parsed_args.cache_dir,
        parsed_args.vrt_path,
        parsed_args.gtiff_path
    )



if __name__ == '__main__':
    # bounding box for the state of california
    #ca_bbox = [-124.53, 32.82, -113.71, 42]
    #main(ca_bbox, '/scratch/users/jadoug06/srtm-global-30m',
    #     'ca.vrt', 'ca.tif')
    main()
