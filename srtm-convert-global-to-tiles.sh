#!/bin/bash
#
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="srtm-convert-global-to-tiles"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

set -e
set -x

WORKING_DIR=srtm-global-1s-v3-tiles

CONTAINER=ghcr.io/natcap/devstack
DIGEST=sha256:54066e72aa135deb8e2f60fda2f42f1856912e36967446659ad754b4b64d7efa

GEOTIFF_SOURCE="$SCRATCH/srtm-global-1s-v3-BACKUP/srtm-global-1s-v3.tif"
WORKING_VRT="$SCRATCH/srtm-global-1s-v3-BACKUP/srtm-scaled-byte.vrt"

# gdal2tiles will fail if the raster is not a byte raster, so here's the
# workaround gdal2tiles.py recommends.
singularity run \
    --env GDAL_CACHEMAX=1024 \
    docker://$CONTAINER@$DIGEST \
    gdal_translate \
        -of VRT \
        -ot Byte \
        -scale \
        "$GEOTIFF_SOURCE" \
        "$WORKING_VRT"

# gdal2tiles is not available in the standard Sherlock gdal package, so here
# we'll run it in the devstack container.
singularity run \
    --env GDAL_CACHEMAX=1024 \
    docker://$CONTAINER@$DIGEST \
    gdal2tiles.py \
        --webviewer=leaflet \
        --title="SRTMv3 1 Arc-Second" \
        --zoom="2-14" \
        --processes=8 \
        "$WORKING_VRT" \
        "$SCRATCH/$WORKING_DIR"
