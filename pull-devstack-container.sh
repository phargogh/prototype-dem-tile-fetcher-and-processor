#!/usr/bin/env sh

#!/bin/bash
#SBATCH --time=0:30:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --mail-type=ALL
#SBATCH --mail-user=jdouglass@stanford.edu
#SBATCH --partition=hns,normal
#SBATCH --job-name="Build devstack singularity container"

singularity pull docker://ghcr.io/phargogh/natcap-devstack:latest
