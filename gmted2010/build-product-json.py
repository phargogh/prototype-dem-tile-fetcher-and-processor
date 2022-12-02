import json
import logging
import os
import sys

from osgeo import gdal

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

json_data = {}
counter = 0
with open(sys.argv[1]) as gmted_url_file:
    for line in gmted_url_file:
        gmted_url = line.strip()
        filename = os.path.basename(gmted_url)
        try:
            gdal_vsi_url = f'/vsicurl/{gmted_url}'
            LOGGER.info(f"Getting info for {gdal_vsi_url}")
            raster = gdal.Open(gdal_vsi_url)
            raster_info = gdal.Info(raster, options=['-json'])
            bbox = raster_info['wgs84Extent']['coordinates'][0]
            json_data[filename] = bbox
        finally:
            raster = None

        counter += 1
        if counter > 1:
            break


with open('gmted2010.json', 'w') as info_json:
    json.dump(json_data, info_json)
