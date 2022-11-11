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

if [[ -n ${SHERLOCK+x} ]]
then
    # Load gdal if we're on sherlock.
    module load physics gdal/3.5.2
    # execute on $SCRATCH if we're on sherlock
    cd "$SCRATCH"
fi

WORKING_DIR=hydrosheds-global
mkdir $WORKING_DIR || echo "$WORKING_DIR already exists"
cd $WORKING_DIR

CONTAINER=ghcr.io/phargogh/natcap-devstack
DIGEST=sha256:0a397b17b328d3ee85966ff22e21e7597446fad3a6764e19ba0f1da68bf5b46a

singularity run docker://$CONTAINER@$DIGEST hydrosheds-global-3s-v1-con.py
