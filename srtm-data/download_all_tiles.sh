#!/bin/bash
#
#SBATCH --time=6:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="Download-SRTM-tiles"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

# fail the script on first nonzero exit code.
set -e

# echo the commands as they're executed
set -x

WORKING_DIR=srtm-global-30m
SRTM_URLS_FILE=srtm30m_urls.txt

if [[ -n ${SHERLOCK+x} ]]
then
    # execute on $SCRATCH if we're on sherlock
    WORKING_DIR="$SCRATCH/$WORKING_DIR"
    module load physics gdal/3.5.2
    module load system jq
fi

mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"

# Runtime: This took about 2 hours to run on 4 CPUs
#cat srtm30m_urls.txt | parallel -j 8 --retries 3 "wget --no-clobber --no-verbose --user='$NASA_EARTHDATA_USERNAME' --password='$NASA_EARTHDATA_PASSWORD' --directory-prefix=$WORKING_DIR {}"

# Try this alternate approach and see if it's faster
wget --no-clobber --no-verbose --user="$NASA_EARTHDATA_USERNAME" --password="$NASA_EARTHDATA_PASSWORD" --directory-prefix=$WORKING_DIR --input-file $SRTM_URLS_FILE

# Runtime: with all of the SRTM files downloaded, this took just under 3 hours to run.
# It was on SCRATCH, so I'm guessing that the disk I/O is the bottleneck.
SRTM_JSON_FILE="srtm_bboxes.json"
rm $SRTM_JSON_FILE || echo "Can't delete $SRTM_JSON_FILE if it doesn't exist!"
echo "{" >> $SRTM_JSON_FILE

# This loop has so many iterations that we don't really need everything logged.
# We're still exiting on the first nonzero exit code.
set +x

n_total=$(wc -l $SRTM_URLS_FILE | awk '{ print $1 }')
n_files_so_far=1

# $srtm_file is an absolute path in this case.
for srtm_file in $(find $WORKING_DIR -name "*.hgt.zip")
do
    echo -e "$srtm_file $n_files_so_far \t\t of $n_total"

    # gdalinfo is supposed to be able to extract the SRTM files (and it usually
    # does).  But there are about 17 tiles that aren't accessible with the standard
    # gdalinfo, so we need to specifically and correctly name those files.
    # The /vsigzip/ approach is more reliable, but slower, so we only use that as a fallback when needed.
    RASTER_METADATA=$(gdalinfo -json $srtm_file || gdalinfo -json /vsizip/$srtm_file/$(unzip -l $srtm_file | head -n4 | tail -n1 | awk '{ print $4 }'))
    echo "\"$(basename $srtm_file)\": $(echo $RASTER_METADATA | jq -c '.wgs84Extent.coordinates[0]')," >> $SRTM_JSON_FILE
    n_files_so_far=$(($n_files_so_far+1))
done
echo "}" >> $SRTM_JSON_FILE

# Remove the comma from the last object to make the json valid.
# This complicated sed expression is thanks to https://unix.stackexchange.com/a/485010
sed -i.bak ':begin;$!N;s/,\n}/\n}/g;tbegin;P;D' $SRTM_JSON_FILE

# Checksum the files while we're at it.
CHECKSUM_FILE="$WORKING_DIR/checksums.md5"
find "$WORKING_DIR" -name "*.hgt.zip" | xargs md5sum > "$CHECKSUM_FILE"
