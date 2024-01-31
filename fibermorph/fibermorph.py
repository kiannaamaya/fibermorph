# %% Import libraries
import argparse
import datetime
import os
import pathlib
import shutil
import sys
import timeit
import warnings
from datetime import datetime
from functools import wraps

# import cv2
import numpy as np
import pandas as pd
import rawpy
import scipy
import skimage
import contextlib
import joblib
import skimage.exposure
import skimage.measure
import skimage.morphology
from PIL import Image
from joblib import Parallel, delayed
from matplotlib import pyplot as plt
from scipy import ndimage
from scipy.spatial import distance as dist
from skimage import filters, io
from skimage.filters import threshold_minimum
from skimage.segmentation import clear_border
from skimage.util import invert
from tqdm import tqdm

#%%
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import demo
from common import make_subdirectory
from utils import parse_args
from image import raw2gray, curvature, section

# Grab version from _version.py in the fibermorph directory
dir = os.path.dirname(__file__)
version_py = os.path.join(dir, "_version.py")
exec(open(version_py).read())

def main():
    args = parse_args()
    
    # Run fibermorph
    
    if args.demo_real_curv is True:
        demo.real_curv(args.output_directory)
        sys.exit(0)
    elif args.demo_real_section is True:
        demo.real_section(args.output_directory)
        sys.exit(0)
    # elif args.demo_dummy_curv is True:
    #     demo.dummy_curv(args.output_directory, args.repeats, args.window_size)
    #     sys.exit(0)
    # elif args.demo_dummy_section is True:
    #     demo.dummy_section(args.output_directory, args.repeats)
    #     sys.exit(0)
    
    # Check for output directory and create it if it doesn't exist
    output_dir = make_subdirectory(args.output_directory)
    
    if args.raw2gray is True:
        raw2gray(
            args.input_directory, output_dir, args.file_extension, args.jobs)
    elif args.curvature is True:
        curvature(
            args.input_directory, output_dir, args.jobs,
            args.resolution_mm, args.window_size, args.window_unit, args.save_image, args.within_element)
    elif args.section is True:
        section(
            args.input_directory, output_dir, args.jobs,
            args.resolution_mu, args.minsize, args.maxsize, args.save_image)
    else:
        sys.exit("Error. Tim didn't exhaust all module options")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
