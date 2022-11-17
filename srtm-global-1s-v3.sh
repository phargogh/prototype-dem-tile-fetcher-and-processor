#!/bin/bash
#
#SBATCH --time=2:00:00
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
fi

mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"

CONTAINER=ghcr.io/phargogh/natcap-devstack
DIGEST=sha256:acdae8dc64e1c7f31e6d2a1f92aa16d1f49c50d58adcd841ee2d325a96de89d9

singularity run \
    docker://$CONTAINER@$DIGEST \
    python "srtm-local-1s-v3.py" \
        --extent="global" \
        --cache-dir="$SCRATCH/srtm-global-30m" \
        --vrt-path="$WORKING_DIR/global.vrt" \
        --gtiff-path="$WORKING_DIR/srtm-global-1s-v3.tif"
