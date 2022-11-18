#!/bin/bash
#
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="srtm-global-1s-v3"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

set -e
set -x

WORKING_DIR=srtm-global-1s-v3

if [[ -n ${SHERLOCK+x} ]]
then
    # execute on $SCRATCH if we're on sherlock
    WORKING_DIR="$SCRATCH/$WORKING_DIR"
    module load physics gdal/3.5.2
fi

mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"

CONTAINER=ghcr.io/phargogh/natcap-devstack
DIGEST=sha256:acdae8dc64e1c7f31e6d2a1f92aa16d1f49c50d58adcd841ee2d325a96de89d9

CACHE="$L_SCRATCH"
#find "$SCRATCH/srtm-global-30m" -name "*.zip" | parallel -j 8 "unzip -d $CACHE {}"
find "$SCRATCH/srtm-global-30m" -name "*.zip" | parallel -j 8 "cp -v {} $CACHE"

VRT_PATH="$CACHE/cmdline-global.vrt"
#gdalbuildvrt $VRT_PATH $(find $CACHE -name "*.hgt.zip")
gdalbuildvrt $VRT_PATH $(find $CACHE -name "*.hgt.zip")

GTIFF_PATH="$CACHE/srtm-global-1s-v3.tif"
gdal_translate \
    -of "GTiff" \
    -ot "Int16" \
    -co "COMPRESS=LZW" \
    -co "PREDICTOR=2" \
    -co "TILED=YES" \
    -co "SPARSE_OK=TRUE" \
    -co "BIGTIFF=YES" \
    -co "NUM_THREADS=8" \
    "$VRT_PATH" \
    "$GTIFF_PATH"

gdaladdo $GTIFF_PATH

rsync --progress $GTIFF_PATH $WORKING_DIR

#singularity run \
#    docker://$CONTAINER@$DIGEST \
#    python "srtm-local-1s-v3.py" \
#        --extent="global" \
#        --cache-dir="$CACHE" \
#        --vrt-path="$WORKING_DIR/global.vrt" \
#        --gtiff-path="$GTIFF_PATH"

#rsync --progress "$GTIFF_PATH" "$WORKING_DIR/cmdline-srtm-global-1s-v3.tif"
