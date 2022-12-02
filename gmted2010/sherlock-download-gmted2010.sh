#!/bin/bash
#
#SBATCH --time=8:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="gmted2010-download"
#SBATCH --output=/scratch/users/jadoug06/slurm-logfiles/slurm-%j.%x.out
#
# --partition=hns,normal means that this will be submitted to both queues, whichever gets to it first will be used.

set -e
set -x

DEST_DIR="$SCRATCH/gmted2010/tiles"
mkdir -p "$DEST_DIR" || echo "Can't make a folder that already exists"

SOURCE_URLS="gmted2010-urls.txt"
wget --no-clobber --no-verbose --directory-prefix "$DEST_DIR" --input-file "$SOURCE_URLS"
