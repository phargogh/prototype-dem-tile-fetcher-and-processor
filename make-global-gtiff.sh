#!/bin/bash
#
#SBATCH --time=2:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="Hydrosheds-global-3s-v1-conditioned"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

set -e
set -x

download_and_verify() {
    download_url=$1
    md5sum=$2
}

if [[ -n ${SHERLOCK+x} ]]
then
    # Load gdal if we're on sherlock.
    module load physics gdal/3.5.2
    # execute on $SCRATCH if we're on sherlock
    cd $SCRATCH
fi

WORKING_DIR=hydrosheds-global
mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"
cd $WORKING_DIR

cat hydrosheds-3s-v1-con.txt | parallel -j3 wget {}

for zipfile in $(find . -name *.zip)
do
    # Unzip, overwriting existing files without prompting, excluding PDFs
    unzip -o $zipfile -x *.pdf
done;

VRT_FILE=hydrosheds-global.vrt
GTIFF=hydrosheds-global-3s-v1-conditioned.tif
gdalbuildvrt $VRT_FILE $(find . -name "*.tif")
gdal_translate -of "COG" -co "COMPRESS=LZW" -co "TILED=YES" $VRT_FILE $GTIFF
