#!/bin/bash
#
#SBATCH --time=24:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="isric-soilgrids-sand"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

set -e
set -x

module load physics gdal/3.5.2

GDAL_CACHEMAX=1024 gdal_translate \
    -of "GTiff" \
    -co "COMPRESS=LZW" \
    -co "PREDICTOR=2" \
    -co "TILED=YES" \
    -co "SPARSE_OK=TRUE" \
    -co "BIGTIFF=YES" \
    -co "NUM_THREADS=4" \
    "/vsicurl/https://files.isric.org/soilgrids/latest/data/sand/sand_0-5cm_mean.vrt" \
    $SCRATCH/isric-soilgrids-wcs-layers/isric-soilgrids-sand_0-5cm_mean.tif
