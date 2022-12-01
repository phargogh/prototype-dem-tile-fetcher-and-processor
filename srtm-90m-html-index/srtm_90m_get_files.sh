#!/bin/bash
#
# Compile a list of all SRTM 90m tiles from the official USGS listing webpages.
#
# The resulting text file with one tile URL per line can be used as an input
# file to wget to download all files in batch.

set -x

HTML_INDEXES='srtm_all_html.txt'
rm $HTML_INDEXES || echo "Cannot remove file that isn't there."

for i in {1..6}
do
    wget "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL3.003/2000.02.11/SRTMGL3_page_${i}.html" -O - >> $HTML_INDEXES
done

SRTM_HGT_FILES="srtm-90m-urls.txt"
egrep -o 'https?://[a-zA-Z0-9./]+\.hgt\.zip"' $HTML_INDEXES | sed 's|"||' > $SRTM_HGT_FILES
