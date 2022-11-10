#!/bin/bash
#
#SBATCH --time=1:00:00
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

if [[ -n ${SHERLOCK+x} ]]
then
    # Load gdal if we're on sherlock.
    module load physics gdal/3.5.2
    # execute on $SCRATCH if we're on sherlock
    cd $SCRATCH
fi

WORKING_DIR=hydrosheds-global
mkdir -f $WORKING_DIR
cd $WORKING_DIR

wget https://data.hydrosheds.org/file/hydrosheds-v1-con/af_con_3s.zip &
wget https://data.hydrosheds.org/file/hydrosheds-v1-con/as_con_3s.zip &
wget https://data.hydrosheds.org/file/hydrosheds-v1-con/au_con_3s.zip &
wget https://data.hydrosheds.org/file/hydrosheds-v1-con/eu_con_3s.zip &
wget https://data.hydrosheds.org/file/hydrosheds-v1-con/na_con_3s.zip &
wget https://data.hydrosheds.org/file/hydrosheds-v1-con/sa_con_3s.zip &

wait $(jobs -p)

for zipfile in $(find . -name *.zip)
do
    unzip $zipfile
done;

VRT_FILE=hydrosheds-global.vrt
GTIFF=hydrosheds-global-3s-v1-conditioned.tif
gdalbuildvrt $VRT_FILE $(find . -name "*.tif")
gdaltranslate -of "COG" -co "COMPRESS=LZW" -co "TILED=YES" $VRT_FILE $GTIFF
