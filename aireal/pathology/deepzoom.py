#!/usr/bin/env python3

import pdb
import argparse
import os
import sys
import re
import tempfile
import subprocess
from collections import defaultdict

import requests
import pyvips



def main(input_dir, output_dir, name=None, quality=None, callback=None):
    """ Create a deepzoom pyramid of images from slide images in input directory.
        Use current working directory to write output files temporarily before
        copying to s3 destination. Requres aws cli v2.
    """
    if input_dir.endswith("/"):
        input_dir = input_dir[:-1]
    if output_dir.endswith("/"):
        output_dir = output_dir[:-1]
    
    cleanup = []
    
    if quality is not None and (quality < 0 or quality > 100):
        sys.exit(f"Quality must be between 0 and 100")
    
    if name is None:
        name = output_dir.split("/")[-1]
    
    S3_INPUT = input_dir[:5].lower() == "s3://"
    S3_OUTPUT = output_dir[:5].lower() == "s3://"

    if S3_INPUT:
        cleanup += [tempfile.TemporaryDirectory()]
        input_temp = cleanup[-1].name
        subprocess.run(["aws", "s3", "cp", input_dir, input_temp, "--include", "*.jpg", "--recursive"])
    else:
        input_temp = input_dir
    if S3_OUTPUT:
        cleanup += [tempfile.TemporaryDirectory()]
        output_temp = cleanup[-1].name
    else:
        os.mkdir(output_dir)
        output_temp = output_dir
    
    pattern = re.compile(r"r([0-9]+)c([0-9]+)\.jpg")
    grid = defaultdict(dict)
    for fn in os.listdir(input_temp):
        match = pattern.match(fn)
        if match:
            path = os.path.join(input_temp, fn)
            if os.path.isfile(path):
                grid[int(match.group(1))][int(match.group(2))] = path

    if not grid:
        return
    
    across = None
    images = []
    for _, row in sorted(grid.items()):
        if across is None or across == len(row):
            across = len(row)
            for _, col in sorted(row.items()):
                images += [pyvips.Image.new_from_file(col)]#, access = pyvips.Access.SEQUENTIAL_UNBUFFERED)]
    
    kwargs = {"suffix": f".jpg[Q={quality}]"} if quality is not None else {}
    joined = pyvips.Image.arrayjoin(images, across=across)
    joined.write_to_file(os.path.join(output_temp, f"{name}.dz"), **kwargs)
    
    if S3_OUTPUT:
        os.chdir(output_temp)
        subprocess.run(["aws", "s3", "cp", ".", output_dir, "--recursive"])
    
    for tempdir in cleanup:
        tempdir.cleanup()
    
    
    if callback:
        requests.post(callback)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--input", help="Directory containing input images.", dest="input_dir", required=True)
    parser.add_argument('-o', "--output", help="Destination directory for output images.", dest="output_dir", required=True)
    parser.add_argument('-n', "--name", help="Name of image. If not provided defaults to input directory.")
    parser.add_argument('-q', "--quality", help="Quality (0 - 100) of output jpeg tiles.", type=int)
    parser.add_argument('-c', "--callback", help="URL to make a post request to on completion of processing.")
    args = parser.parse_args()
    
    try:
        main(**vars(args))
    except OSError as e:
        # File input/output error. This is not an unexpected error so just
        # print and exit rather than displaying a full stack trace.
        sys.exit(str(e))
