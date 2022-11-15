#!/bin/bash
#
#SBATCH --time=4:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="Download-SRTM-tiles"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.


set -e
set -x

WORKING_DIR=srtm-global-30m

if [[ -n ${SHERLOCK+x} ]]
then
    # execute on $SCRATCH if we're on sherlock
    WORKING_DIR="$SCRATCH/$WORKING_DIR"
fi

mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"

cat srtm30m_urls.txt | parallel -j 8 --retries 3 "wget --no-clobber --no-verbose --user='$NASA_EARTHDATA_USERNAME' --password='$NASA_EARTHDATA_PASSWORD' --directory-prefix=$WORKING_DIR {}"

SRTM_JSON_FILE="srtm_bboxes.json"
echo "{" >> $SRTM_JSON_FILE
for srtm_file in $(find $WORKING_DIR -name "*.hgt.zip")
do
    echo "\"$(basename $srtm_file)\": $(gdalinfo -json $srtm_file | jq -c '.wgs84Extent.coordinates[0]')," >> $SRTM_JSON_FILE
done
echo "}" >> $SRTM_JSON_FILE

# Remove the comma from the last object to make the json valid.
# This complicated sed expression is thanks to https://unix.stackexchange.com/a/485010
sed -i.bak ':begin;$!N;s/,\n}/\n}/g;tbegin;P;D' $SRTM_JSON_FILE
