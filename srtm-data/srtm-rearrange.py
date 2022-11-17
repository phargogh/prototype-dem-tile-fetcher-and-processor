# Move a big flat directory of 14k files into some smaller directories for
# maybe better performance on Lustre filesystem.
import json
import os
import shutil
import time

with open('srtm_bboxes.json') as data_file:
    srtm_tiles = json.load(data_file)

last_report_time = time.time()
n_files_moved = 0
base_prefix = os.path.join(os.environ['SCRATCH'], 'srtm-global-30m')
for srtm_zipfile in srtm_tiles.keys():
    if time.time() - last_report_time >= 5.0:
        print(f"Moved {n_files_moved}/{len(srtm_tiles)} so far")
        last_report_time = time.time()

    srtm_prefix = srtm_zipfile[:4]
    subdir = os.path.join(base_prefix, srtm_prefix)
    if not os.path.exists(subdir):
        os.makedirs(subdir)

    source_file = os.path.join(base_prefix, srtm_zipfile)
    dest_file = os.path.join(subdir, srtm_zipfile)
    shutil.move(source_file, dest_file)
    n_files_moved += 1
