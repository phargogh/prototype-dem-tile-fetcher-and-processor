import argparse
import json
import logging
import math
import os
import sys

import numpy
import pygeoprocessing
import pygeoprocessing.routing
import requests
import shapely.geometry
import shapely.prepared
from osgeo import gdal
from osgeo import osr
from tqdm.auto import tqdm

logging.basicConfig(level=logging.INFO)
# TODO: do MD5sum verification of tiles, tracked in JSON

# TODO: Add GMTED2010
KNOWN_PRODUCTS = {'SRTM', 'HydroSHEDS'}
KNOWN_ROUTING_ALGOS = {'D8', 'MFD'}
LOGGER = logging.getLogger(__name__)
DOWNLOAD_BASE_URLS = {
    'srtm': 'https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11',
}

gdal.SetCacheMax(1024)  # Megabytes


def _extract_streams_d8(flow_accum_path, tfa, target_streams_path):
    flow_accum_nodata = pygeoprocessing.get_raster_info(
        flow_accum_path)['nodata'][0]
    target_nodata = 255
    tfa = float(tfa)

    def _d8_streams(flow_accumulation):
        valid_mask = (flow_accumulation != flow_accum_nodata)
        result = numpy.full(flow_accumulation.shape, target_nodata,
                            dtype=numpy.uint8)
        result[valid_mask] = numpy.where(flow_accumulation <= tfa, 0, 1)
        return result

    pygeoprocessing.raster_calculator(
        [(flow_accum_path, 1)], _d8_streams, target_streams_path,
        gdal.GDT_Byte, target_nodata)


def download(source_url, target_file, session=None):
    # Adapted from https://stackoverflow.com/a/61575758
    if session:
        # See session example from https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
        authenticated_request = session.request('get', source_url)
        response = session.get(authenticated_request.url, stream=True)
    else:
        response = requests.get(source_url, stream=True)

    if not response.ok:
        raise AssertionError(
            f'Response failed with message "{response.text.strip()}" for '
            f'url {source_url}')

    with tqdm.wrapattr(open(target_file, "wb"), "write",
                       miniters=1, desc=source_url.split('/')[-1],
                       total=int(response.headers.get('content-length', 0))) as fout:
        for chunk in response.iter_content(chunk_size=4096):
            fout.write(chunk)

# find matching tiles.
def intersecting_tiles(bbox, product_json_data):
    bbox_geom = shapely.prepared.prep(shapely.geometry.box(*bbox))

    with open(product_json_data) as data_file:
        json_boundaries = json.load(data_file)

    for tile_filename, tile_bbox in json_boundaries.items():
        tile_geom = shapely.geometry.Polygon(tile_bbox)
        if not bbox_geom.intersects(tile_geom):
            continue

        # TODO: also yield tile file md5sum?
        yield tile_filename


# check tiles against cache and redownload if needed




# cache structure: cache/product/tile
def fetcher(workspace, product, bbox, target_projection_epsg,
            routing_method, cache_dir, min_tfa, max_tfa, tfa_step):
    if not os.path.exists(workspace):
        os.makedirs(workspace)

    product = product.lower()
    bbox_geom = shapely.prepared.prep(shapely.geometry.box(*bbox))

    tile_cache_dir = os.path.join(cache_dir, product)
    if not os.path.exists(tile_cache_dir):
        os.makedirs(tile_cache_dir)

    tile_data_file = os.path.join(
        os.path.dirname(__file__), 'data', f'{product}.json')
    with open(tile_data_file) as data_file:
        json_boundaries = json.load(data_file)

    intersecting_tiles = []
    for tile_filename, tile_bbox in json_boundaries.items():
        tile_geom = shapely.geometry.Polygon(tile_bbox)
        if not bbox_geom.intersects(tile_geom):
            continue

        tile_file = os.path.join(tile_cache_dir, tile_filename)
        if not os.path.exists(tile_filename):
            source_url = f'{DOWNLOAD_BASE_URLS[product]}/{tile_filename}'
            download(source_url, tile_filename)
            print(tile_filename)
            return

        intersecting_tiles.append(tile_file)

    vrt_path = os.path.join(workspace, f'0_{product}_mosaic.vrt')
    gdal.BuildVRT(vrt_path, intersecting_tiles)

    # TODO: square off the pixel size and use that instead?
    vrt_raster_info = pygeoprocessing.get_raster_info(vrt_path)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(target_projection_epsg)
    warped_raster = os.path.join(
        workspace, f'1_{product}_cropped_EPSG{target_projection_epsg}.tif')
    pygeoprocessing.warp_raster(
        base_raster_path=vrt_path,
        target_pixel_size=vrt_raster_info['pixel_size'],
        target_raster_path=warped_raster,
        resample_method='bilinear',
        target_bb=bbox,
        target_projection_wkt=srs.ExportToWkt()
    )

    filled_sinks_path = os.path.join(
        workspace, f'2_{product}_pitfilled.tif')
    pygeoprocessing.routing.fill_pits(
        dem_raster_path_band=(warped_raster, 1),
        target_filled_dem_raster_path=filled_sinks_path,
        working_dir=workspace
    )

    routing_method = routing_method.lower()
    flow_dir_kwargs = {
        'dem_raster_path_band': (filled_sinks_path, 1),
        'target_flow_dir_path': os.path.join(
            workspace, f'3_{product}_{routing_method}_flow_dir.tif')
    }

    # D8 and MFD flow accumulation functions have slightly different function
    # signatures, so using *args instead of **kwargs
    flow_accum_path = os.path.join(
        workspace, f'4_{product}_{routing_method}_flow_accumulation.tif')
    flow_accum_args = [
        (flow_dir_kwargs['target_flow_dir_path'], 1), flow_accum_path]

    if routing_method == 'd8':
        pygeoprocessing.routing.flow_dir_d8(**flow_dir_kwargs)
        pygeoprocessing.routing.flow_accumulation_d8(*flow_accum_args)
    else:
        pygeoprocessing.routing.flow_dir_mfd(**flow_dir_kwargs)
        pygeoprocessing.routing.flow_accumulation_mfd(*flow_accum_args)

    routing_method = routing_method.lower()
    streams_dir = os.path.join(workspace, 'streams')
    if not os.path.exists(streams_dir):
        os.makedirs(streams_dir)

    for tfa in range(min_tfa, max_tfa+1, tfa_step):
        streams_raster_path = os.path.join(
            streams_dir, f'tfa{tfa}_{routing_method}_streams.tif')
        if routing_method == 'd8':
            _extract_streams_d8(
                flow_accum_path=flow_accum_path,
                tfa=tfa,
                target_streams_path=streams_raster_path)
        else:
            pygeoprocessing.routing.extract_streams_mfd(
                flow_accum_raster_path_band=(flow_accum_path, 1),
                flow_dir_mfd_path_band=(
                    flow_dir_kwargs['target_flow_dir_path'], 1),
                flow_threshold=tfa,
                target_stream_raster_path=streams_raster_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default=os.getcwd())
    parser.add_argument('--tile-cache-dir')

    # Auto-detect target projection from closest UTM zone if no projection
    # provided.
    parser.add_argument('--target-epsg')

    parser.add_argument(
        '--tfa-range', help=(
            'The min, max and step size of threshold flow accumulation values '
            'to create in the form MIN:MAX:STEP.  Example: 500:10000:200'))

    parser.add_argument(
        '--routing-algorithm', choices=KNOWN_ROUTING_ALGOS,
        help='Routing algorithm to use.')

    parser.add_argument(
        '--username', help=('The username to log in with. Required for SRTM'))
    parser.add_argument(
        '--password', help=('The password to log in with.  Required for SRTM'))

    parser.add_argument(
        'product', metavar='product', choices=KNOWN_PRODUCTS,
        help='The DEM product to use')

    # TODO: support searching by an admin region (countries, states)
    parser.add_argument(
        'boundary', help=(
            'The boundary to use. A path to a vector AOI or a lat/lon '
            'bounding box in the order "BBOX::minx::miny::maxx::maxy"'))

    args = parser.parse_args(sys.argv[1:])

    if os.path.exists(args.boundary):
        gis_type = pygeoprocessing.get_gis_type(args.boundary)
        if (gis_type & pygeoprocessing.RASTER_TYPE):
            bbox = pygeoprocessing.get_raster_info(args.boundary)['bounding_box']
        elif (gis_type & pygeoprocessing.VECTOR_TYPE):
            bbox = pygeoprocessing.get_vector_info(args.boundary)['bounding_box']
        else:
            raise ValueError('File exists but is not a GDAL filetype: '
                             f'{args.bbox}')
    else:
        # Assume "minx,miny,maxx,maxy"
        bbox = [float(coord) for coord in
                args.boundary.replace('BBOX::', '').split('::')]

    try:
        epsg_code = int(args.target_epsg)
    except TypeError:
        raise NotImplementedError('TODO')

    try:
        min_tfa, max_tfa, tfa_step = [
            int(tfa) for tfa in args.tfa_range.split(':')]
    except AttributeError:
        # Effectively skips TFA calculations
        min_tfa, max_tfa, tfa_step = (0, 0, 1)

    cache_dir = args.tile_cache_dir
    if cache_dir is None:
        cache_dir = os.path.join(args.workspace, 'tile-cache')

    product = args.product.lower()
    if product == 'srtm' and any(
            [args.username is None, args.password is None]):
        parser.exit(
            1, ('For SRTM, your NASA EarthData Username and Password are '
                'required.  Provide them with --username and --password.\n'))

    tile_data_file = os.path.join(
        os.path.dirname(__file__), 'data', f'{product}.json')
    files_to_download = []
    tiles_needed = 0
    tile_cache_dir = os.path.join(cache_dir, product)
    if not os.path.exists(tile_cache_dir):
        os.makedirs(tile_cache_dir)

    for tilename in intersecting_tiles(bbox, tile_data_file):
        tiles_needed += 1
        cached_tile_file = os.path.join(tile_cache_dir, tilename)
        files_to_download.append(cached_tile_file)

    with requests.Session() as session:
        if product == 'srtm':
            session.auth = (args.username, args.password)

        for filename in tqdm(files_to_download):
            # TODO: md5sum checking
            if not os.path.exists(cached_tile_file):
                download(
                    f'{DOWNLOAD_BASE_URLS[product]}/{os.path.basename(filename)}',
                    filename, session=session)

    workspace = args.workspace
    if not os.path.exists(workspace):
        os.makedirs(workspace)
    target_projection_epsg = args.target_epsg
    vrt_path = os.path.join(workspace, f'0_{product}_mosaic.vrt')
    gdal.BuildVRT(vrt_path, files_to_download)

    # TODO: square off the pixel size and use that instead?
    vrt_raster_info = pygeoprocessing.get_raster_info(vrt_path)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(int(target_projection_epsg))
    warped_raster = os.path.join(
        workspace, f'1_{product}_cropped_EPSG{target_projection_epsg}.tif')
    pygeoprocessing.warp_raster(
        base_raster_path=vrt_path,
        target_pixel_size=vrt_raster_info['pixel_size'],
        target_raster_path=warped_raster,
        resample_method='bilinear',
        target_bb=bbox,
        target_projection_wkt=srs.ExportToWkt()
    )

    filled_sinks_path = os.path.join(
        workspace, f'2_{product}_pitfilled.tif')
    pygeoprocessing.routing.fill_pits(
        dem_raster_path_band=(warped_raster, 1),
        target_filled_dem_raster_path=filled_sinks_path,
        working_dir=workspace
    )

    routing_method = args.routing_algorithm.lower()
    flow_dir_kwargs = {
        'dem_raster_path_band': (filled_sinks_path, 1),
        'target_flow_dir_path': os.path.join(
            workspace, f'3_{product}_{routing_method}_flow_dir.tif')
    }

    # D8 and MFD flow accumulation functions have slightly different function
    # signatures, so using *args instead of **kwargs
    flow_accum_path = os.path.join(
        workspace, f'4_{product}_{routing_method}_flow_accumulation.tif')
    flow_accum_args = [
        (flow_dir_kwargs['target_flow_dir_path'], 1), flow_accum_path]

    if routing_method == 'd8':
        pygeoprocessing.routing.flow_dir_d8(**flow_dir_kwargs)
        pygeoprocessing.routing.flow_accumulation_d8(*flow_accum_args)
    else:
        pygeoprocessing.routing.flow_dir_mfd(**flow_dir_kwargs)
        pygeoprocessing.routing.flow_accumulation_mfd(*flow_accum_args)

    routing_method = routing_method.lower()
    streams_dir = os.path.join(workspace, 'streams')
    if not os.path.exists(streams_dir):
        os.makedirs(streams_dir)

    for tfa in range(min_tfa, max_tfa+1, tfa_step):
        streams_raster_path = os.path.join(
            streams_dir, f'tfa{tfa}_{routing_method}_streams.tif')
        if routing_method == 'd8':
            _extract_streams_d8(
                flow_accum_path=flow_accum_path,
                tfa=tfa,
                target_streams_path=streams_raster_path)
        else:
            pygeoprocessing.routing.extract_streams_mfd(
                flow_accum_raster_path_band=(flow_accum_path, 1),
                flow_dir_mfd_path_band=(
                    flow_dir_kwargs['target_flow_dir_path'], 1),
                flow_threshold=tfa,
                target_stream_raster_path=streams_raster_path)

    return

    # if tile cache directory not set, write the cache to the workspace.
    # TODO: identify the local UTM zone if no EPSG code provided.
    fetcher(
        workspace=args.workspace,
        product=args.product,
        bbox=bbox,
        target_projection_epsg=epsg_code,
        routing_method=args.routing_algorithm,
        cache_dir=cache_dir,
        min_tfa=min_tfa,
        max_tfa=max_tfa,
        tfa_step=tfa_step
    )


if __name__ == '__main__':
    main()
