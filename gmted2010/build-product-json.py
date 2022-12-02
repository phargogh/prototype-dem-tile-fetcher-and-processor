import json
import logging
import os
import sys

from osgeo import gdal

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

json_data = {}
for gmted_url in open(sys.argv[1]):
    filename = os.path.basename(gmted_url)
    try:
        LOGGER.info(f"Getting info for {gmted_url}")
        raster = gdal.Open(f'/vsicurl/{gmted_url}')
        raster_info = gdal.Info(raster, options=['-json'])
        bbox = raster_info['wgs84Extent']['coordinates'][0]
        json_data[filename] = bbox
    finally:
        raster = None


with open('gmted2010.json', 'w') as info_json:
    json.dump(json_data, info_json, indent=4)
