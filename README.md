# prototype-dem-tile-fetcher-and-processor

This script, `fetcher.py`, allows someone to easily define an area of interest
and then have the program automate the following steps:

1. Download the appropriate DEM tiles
2. Verify checksums on the downloaded tiles
3. Mosaic the tiles into a single DEM
4. Fill hydrological sinks
5. Calculate flow direction (D8 or MFD)
6. Calculate flow accumulation (D8 or MFD)
7. Given a range of flow accumulation thresholds, create a series of stream
   layers based on the generated flow accumulation layer.


## Supported DEM Products

The following DEM products are supported:

1. SRTM
   * Resolutions: 3s
   * Subproducts: v3
   * Notes: NASA EarthData login credentials required.
2. HydroSHEDS
   * Resolutions: ?
   * Subproducts: v1
3. GMTED2010
   * Resolutions: 7.5s, 15s, 30s
   * Subproducts:
      * "mea" - Mean
      * "std" - Standard Deviation
      * "med" - Median
      * "min" - Minimum
      * "dsc" - Systematic Subsample
      * "bln" - Breakline Emphasis

## Cache

Tile downloads can be unpredictable and slow, depending on the underlying
webserver.  To avoid this, a cache is available for internal use.  If
the cache is provided to `fetcher.py`, tiles available in the cache will not
be re-downloaded and used directly.

The cache has the following directory structure:

```
<cache location>/
    <product>-<resolution>-<subproduct>/
        tiles/
        tiles-checksum-<algorithm>.txt
        tiles-bboxes.json
        download-urls.txt
        <product>-<resolution>-<subproduct>-global.tif
        README.md

```

For example, for SRTM-3s-v3, this might look like:
```
$OAK/
    SRTM-3s-v3/
        tiles/
        tiles-checksum-sha256.txt
        tiles-bboxes.json
        SRTM-3s-v3-global.tif
        download-urls.txt
        README.md
```

`tiles/` is a directory of tiles in this product. Each tile is a GeoTiff and
is in WGS84.

`tiles-checksum-sha256.tif` is a checksum file that can be run with `sha256sum`
or similar in order to verify the integrity of downloaded tiles in the `tiles/`
directory.

`tiles-bboxes.json` is a JSON file mapping a filename in `tiles/` to a list of
coordinate pairs representing the bounding box of the tile. This is used by
`fetcher.py` to determine which tiles are needed for the area of interest.

`SRTM-3s-v3-global.tif` is a cloud-optimized geotiff for the target product,
resolution and subproduct, including overviews.

`download-urls.txt` is a list of URLs that can be fed to a program such as
`wget` in order to re-download all tiles.

`README.md` is a markdown file describing where to find more information about
the dataset.
