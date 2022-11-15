import hashlib
import logging
import math
import os
import sys
import threading
import time
import zipfile

import pygeoprocessing
import pygeoprocessing.multiprocessing
import requests
from osgeo import gdal

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)
DOWNLOAD_PREFIX = 'https://data.hydrosheds.org/file/hydrosheds-v1-con'
FILE_TO_MD5SUM = {
    "af_con_3s.zip": "15dc5c31c8661a84c9621e3bb3764aee",
    "as_con_3s.zip": "298542936297892e9ff7a4e3c1123e98",
    "au_con_3s.zip": "3929d9d2f215582bf73a9eff7bf627cd",
    "eu_con_3s.zip": "a3cfae5748a189df621ec673193144be",
    "na_con_3s.zip": "02b0943bc1cafe714612ed193b38cbbe",
    "sa_con_3s.zip": "9d8624d79fe80f547578be6a9e932b8f",
}
DEFAULT_GTIFF_CREATION_TUPLE_OPTIONS = ('GTIFF', (
    'TILED=YES', 'BIGTIFF=YES', 'COMPRESS=LZW', 'NUM_THREADS=4',
    'BLOCKXSIZE=256', 'BLOCKYSIZE=256'))


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


def verify_checksum(filepath, checksum):
    LOGGER.info(f"Checksumming (md5) {filepath}")
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            h.update(data)

    digest = h.hexdigest()
    if digest != checksum:
        raise AssertionError(f"Checksum failed for file {filepath}")
    LOGGER.info(f"Checksum (md5) verified on {filepath}")


def download_file(source_url, target_file):
    LOGGER.info(f"Downloading {source_url} to {target_file}")
    expected_fsize = int(requests.head(source_url).headers['content-length'])
    downloaded_fsize = 0
    last_time = time.time()
    with requests.get(source_url, stream=True) as req:
        req.raise_for_status()
        with open(target_file, 'wb') as target:
            for chunk in req.iter_content(chunk_size=8192):
                if time.time() >= last_time + 5.0:
                    last_time = time.time()
                    percent = (downloaded_fsize / expected_fsize) * 100
                    LOGGER.info(
                        f"{downloaded_fsize} / {expected_fsize} ({percent}%) "
                        f"downloaded of {source_url} ")
                downloaded_fsize += len(chunk)
                target.write(chunk)
    LOGGER.info(f"Download finished: {target_file}")


def download_and_checksum(source_url, target_file):
    checksum = FILE_TO_MD5SUM[os.path.basename(source_url)]
    try:
        if os.path.exists(target_file):
            LOGGER.info(f"Verifying existing zipfile {target_file}")
            verify_checksum(target_file, checksum)
            return
    except AssertionError:
        LOGGER.info(f"Checksum failed for {target_file}")
        os.remove(target_file)

    download_file(source_url, target_file)
    verify_checksum(target_file, checksum)


def unzip_raster_from_archive(target_zipfile, target_raster):
    with zipfile.ZipFile(target_zipfile) as hydrosheds_zip:
        hydrosheds_zip.extract(os.path.basename(target_raster),
                               path=os.path.dirname(target_raster))


def thread_worker(source_url, target_zipfile, target_raster, failed):
    try:
        download_and_checksum(source_url, target_zipfile)
        unzip_raster_from_archive(target_zipfile, target_raster)
    except Exception:
        LOGGER.exception(
            f"Thread {threading.current_thread()} ({source_url}) failed.")
        failed.set()


def _identity(matrix):
    return matrix


def main(workspace):
    if not os.path.isdir(workspace):
        os.makedirs(workspace)

    LOGGER.info("Starting downloads")
    vrt_path = os.path.join(workspace, 'wrapper.vrt')
    component_rasters = []
    component_threads = []
    failed = threading.Event()
    for zip_filename, checksum in FILE_TO_MD5SUM.items():
        target_zipfile = os.path.join(workspace, zip_filename)
        target_raster = os.path.join(workspace, os.path.splitext(
            os.path.basename(target_zipfile))[0] + '.tif')
        component_rasters.append(target_raster)
        thread = threading.Thread(
                target=thread_worker,
                kwargs={
                    'source_url': f'{DOWNLOAD_PREFIX}/{zip_filename}',
                    'target_zipfile': target_zipfile,
                    'target_raster': target_raster,
                    'failed': failed,
                }
            )
        thread.start()
        component_threads.append(thread)

    for thread in component_threads:
        thread.join()

    if failed.is_set():
        raise Exception("Downloading a file failed.")

    LOGGER.info("Building a VRT of component rasters for translation")
    gdal.BuildVRT(vrt_path, component_rasters)
    vrt_raster_info = pygeoprocessing.get_raster_info(vrt_path)

    target_gtiff_path = os.path.join(
        workspace, 'hydrosheds-global-3s-v1-conditioned.tif')
    LOGGER.info(f"Translating VRT to a single file --> {target_gtiff_path}")
    raster_calculator_kwargs = {
        'base_raster_path_band_const_list': [(vrt_path, 1)],
        'local_op': _identity,
        'target_raster_path': target_gtiff_path,
        'datatype_target': vrt_raster_info['datatype'],
        'nodata_target': vrt_raster_info['nodata'][0],
        'raster_driver_creation_tuple': DEFAULT_GTIFF_CREATION_TUPLE_OPTIONS,
    }
    pygeoprocessing.raster_calculator(**raster_calculator_kwargs)
    build_overviews(target_gtiff_path, internal=True)

    LOGGER.info(f"Global HydroSHEDS raster assembled at {target_gtiff_path}")


if __name__ == '__main__':
    main(workspace=sys.argv[1])
