from skimage import draw
from random import randint
import matplotlib.pyplot as plt
from sympy import geometry

import os
import pathlib
import shutil
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import parse_args, create_results_cache, delete_dir, url_files, download_im
from analysis import validation_curv, sim_ellipse, validation_section, real_curv, real_section, dummy_curv, dummy_section

from joblib import Parallel, delayed

def main():
    # parse command line arguments
    args = parse_args()

    # set output directory
    path = args.output_directory

    # create results cache
    output_directory = create_results_cache(path)

    # get type of analysis
    im_type = "curv" if args.demo_real_curv else "section"

    # download data
    demo_url = url_files(im_type)
    download_im(output_directory, demo_url)

    # set parameters
    window_size_px = args.window_size_px
    repeats = 5
    resolution = 1
    jobs = 2
    im_width_px = 2
    im_height_px = 2 
    min_diam_um = 2
    max_diam_um = 2 
    px_per_um = 2
    angle_deg = 2

    # validation
    validation_curv(output_directory, repeats, window_size_px, resolution)
    sim_ellipse(output_directory, im_width_px = 5200, im_height_px = 3900, min_diam_um = 30, max_diam_um = 120, px_per_um = 4.25, angle_deg = 45)
    validation_section(output_directory, repeats, jobs)
    

    # real analysis
    if args.demo_real_curv:
        real_curv(path)
    elif args.demo_real_section:
        real_section(path)

    # dummy analysis
    dummy_curv(path, repeats = 1, window_size_px = 10)
    dummy_section(path, repeats = 1)

    # delete directory
    delete_dir(path)


if __name__ == "__main__":
    main()

# i need a way to address the repeats, window size, etc. because they differ based on function and input