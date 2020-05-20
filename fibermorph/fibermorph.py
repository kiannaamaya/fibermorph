# %% Import libraries
import argparse
import os  # Allows python to work with the operating system.
import pathlib  # Makes defining pathways simple between mac, windows, linux.
import shutil
import sys
import warnings
from datetime import datetime
from functools import wraps
from timeit import default_timer as timer  # Timer to report how long everything is taking.

import cv2
import numpy as np  # Main math backbone of python, lots of MatLab like functions.
import pandas as pd
import rawpy  # Allows python to read raw image and convert to tiff
import scipy
import skimage
import skimage.measure
import skimage.morphology
from PIL import Image  # Allows conversion from RGB to grayscale and ImageChops for cropping
from joblib import Parallel, delayed
from matplotlib import pyplot as plt
from scipy import ndimage
from scipy.spatial import distance as dist
from skimage import filters, io
from skimage.filters import threshold_minimum, threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import disk
from skimage.segmentation import clear_border
from skimage.util import invert

# from fibermorph.test.function_unit_tests.test_unit_binarize_curv import binarize_curv
# from fibermorph.test.function_unit_tests.test_unit_filter import filter
# from fibermorph.test.function_unit_tests.test_unit_remove_particles import remove_particles
# from fibermorph.test.function_unit_tests.test_unit_skeletonize import skeletonize
# from fibermorph.test.function_unit_tests.test_unit_prune import prune
# TODO: move the functions to separate files and import them into the test units, then re-write this


# Grab version from _version.py in the fibermorph directory
dir = os.path.dirname(__file__)
version_py = os.path.join(dir, "_version.py")
exec(open(version_py).read())

# parse_args() and timing() listed first for easy updating/access

def parse_args():
    """
    Parse command-line arguments
    Returns
    -------
    Parser argument namespace
    """
    parser = argparse.ArgumentParser(description="Fibermorph")

    parser.add_argument(
        "--output_directory", required=True,
        help="Required. Full path to and name of desired output directory. "
        "Will be created if it doesn't exist.")

    parser.add_argument(
        "--input_directory", required=True,
        help="Required. Full path to and name of desired directory containing "
        "input files.")

    parser.add_argument(
        "--file_extension", required=True,
        help="Required. String. Extension of input files to use in input_directory")

    parser.add_argument(
        "--jobs", type=int, default=1,
        help="Integer. Number of parallel jobs to run. Default is 1.")

    parser.add_argument(
        "--window_size", type=float, default=1.0,
        help="Float. Add description.")

    parser.add_argument(
        "--min_size", type=float, default=1.0,
        help="Float. Add description.")

    parser.add_argument(
        "--pad", type=int, default=0,
        help="Integer. Number of pixels to pad with. Default is 0.")

    parser.add_argument(
        "--crop", type=bool, default=False,
        help="Boolean. Default is False. Add description.")

    parser.add_argument(
        "--save_image", type=bool, default=False,
        help="Boolean. Default is False. Add description.")

    parser.add_argument(
        "--save_crop", type=bool, default=False,
        help="Boolean. Default is False. Add description.")

    # Create mutually exclusive flags for each of fibermorph's modules
    module_group = parser.add_mutually_exclusive_group(required=True)

    module_group.add_argument(
        "--consolidate", action="store_true", default=False,
        help="")

    module_group.add_argument(
        "--raw2gray", action="store_true", default=False,
        help="")

    module_group.add_argument(
        "--curvature", action="store_true", default=False,
        help="")

    module_group.add_argument(
        "--section", action="store_true", default=False,
        help="")

    args = parser.parse_args()
    return args


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print(
            '\n\n The function: {} \n\n with args:[{},\n{}] \n\n and result: {} \n\ntook: {:2.4f} sec\n\n'.format(
                f.__name__, args, kw, result, te - ts))
        return result

    return wrap


# Rest of the functions--organized alphabetically

@timing

def blockPrint():
    sys.stdout = open(os.devnull, 'w')


def copy_if_exist(file, directory):
    '''

    :param file:        file to be copied
    :param directory:   location of destination directory
    :return:            None
    '''

    path = pathlib.Path(file)
    destination = directory

    if os.path.isfile(path):
        shutil.copy(path, destination)
        print('file has been copied'.format(path))
        return True
    else:
        print('file does not exist'.format(path))
        return False


def convert(seconds):
    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)
    return "%dh: %02dm: %02ds" % (hour, min, sec)


def crop_image(input_file, cropped_dir, cropped_binary_dir, pad, minpixel, resolution, crop, save_image):
    """
    :param crop:
    :param save_image:          Default is to not save cropped grayscale in order to speed up computation of results
    :param input_file:          The image file to be read in.
    :param output_path:         The output path where the subfolders resulting from this function are to be made
    :param pad:                 The number of pixels you want to pad the segmented image of the hair
    :param minpixel:            The minimum number of pixels representing a hair
    :return:                    returns cropped grayscale image and directory
    """

    filename = str(os.path.basename(input_file))

    if not crop:

        gray_img = cv2.imread(str(input_file), 0)  # read in image as numpy array, this will be in color
        type(gray_img)  # using the above function it returns <class 'numpy.ndarray'>
        print("Image size is:", gray_img.shape)  # returns (3904, 5200)

        seg_input_file = np.array(gray_img)
        seg_cropped_binary_dir = cropped_binary_dir
        seg_pad = pad
        seg_resolution = resolution

        tempdf_section = segment_section2(filename, seg_input_file, seg_cropped_binary_dir, seg_pad, seg_resolution)

        print("\n Created temporary dataframe for {}: \n {}".format(filename, tempdf_section))

        return tempdf_section
    else:

        try:
            cropped_dir = cropped_dir
            pad = pad

            gray_img = cv2.imread(str(input_file), 0)  # read in image as numpy array, this will be in color
            type(gray_img)  # using the above function it returns <class 'numpy.ndarray'>
            print("Image size is:", gray_img.shape)  # returns (3904, 5200)

            smooth = skimage.filters.rank.median(gray_img, selem=disk(int(resolution * 8)))

            thresh = threshold_otsu(smooth)

            # creates binary image by applying the above threshold and replacing all
            init_ls = (np.where(gray_img > thresh, 0, 1)).astype('uint8')

            chan = skimage.segmentation.morphological_chan_vese(smooth, 10, init_level_set=init_ls, smoothing=1, lambda1=1, lambda2=0.6)

            bw_uint8 = (np.array(chan)).astype('uint8')  # turning image into unsigned integer (0-255, grayscale)

            cleared = clear_border(bw_uint8)
            # remove artifacts connected to image border, needs to be inverted for this to work!

            radius = minpixel/2

            min_area = np.pi*(radius**2)

            # # remove small objects before labeling
            # skimage.morphology.remove_small_objects(cleared, min_area, in_place=True)

            # label image regions
            label_image, num_elements = label(cleared, connectivity=2, return_num=True)

            image_center = list(np.divide(label_image.shape, 2))  # returns array of two floats

            print("generating bounding box for image {}'\n\n".format(filename))

            minpixel = minpixel

            bbox_pad = None

            try:
                center_hair, bbox = find_hair(label_image, image_center, minpixel)

                minr = bbox[0] - pad
                minc = bbox[1] - pad
                maxr = bbox[2] + pad
                maxc = bbox[3] + pad

                bbox_pad = [minc, minr, maxc, maxr]
                print("\nFound bbox for {} \n It is: {}".format(filename, str(bbox_pad)))

            except:
                minr = int(image_center[0] / 2)
                minc = int(image_center[1] / 2)
                maxr = int(image_center[0] * 1.5)
                maxc = int(image_center[1] * 1.5)

                bbox_pad = [minc, minr, maxc, maxr]
                print("Error: \n Found no bbox for {} \n Used center 25% of image instead: {}".format(filename, str(bbox_pad)))

            finally:

                gray_crop = Image.fromarray(gray_img)
                cropped_grayscale = gray_crop.crop(bbox_pad)

                output_name_gray = pathlib.Path(cropped_dir).joinpath(filename)

                if save_image == True:

                    cropped_grayscale.save(output_name_gray)
                    print("\nSaved cropped grayscale as {}".format(output_name_gray))
                else:
                    pass

                seg_input_file = np.array(cropped_grayscale)
                seg_cropped_binary_dir = cropped_binary_dir
                seg_pad = pad
                seg_resolution = resolution

                tempdf_section = segment_section2(filename, seg_input_file, seg_cropped_binary_dir, seg_pad, seg_resolution)

                print("\n Created temporary dataframe for {}: \n {}".format(filename, tempdf_section))

            return tempdf_section
        except:
            pass


def enablePrint():
    sys.stdout = sys.__stdout__



def find_hair(label_image, image_center, minpixel):

    props = regionprops(label_image)

    center_hair = None

    try:
        hairs = [[region.label, region.centroid, dist.euclidean(image_center, region.centroid)] for region in props if region.minor_axis_length > minpixel]

        lst = pd.DataFrame(hairs, columns=['label', 'centroid', 'distance'])
        print("\n")
        print("These are the elements with minor axis length larger than minpixel:")
        print(lst)

        center_hair_idx = lst['distance'].idxmin()
        print("\n\n Row containing smallest distance:")
        print(center_hair_idx)
        print(type(center_hair_idx))

        center_hair = lst.at[center_hair_idx, 'label'].item()
    except TypeError:
        try:
            hairs = [[region.label, region.centroid, dist.euclidean(image_center, region.centroid)] for region in props if
                     region.equivalent_diameter > minpixel]

            lst = pd.DataFrame(hairs, columns=['label', 'centroid', 'distance'])
            print("\n")
            print("These are the elements with minor axis length larger than minpixel:")
            print(lst)

            center_hair_idx = lst['distance'].idxmin()
            print("\n\n Row containing smallest distance:")
            print(center_hair_idx)
            print(type(center_hair_idx))
            center_hair = lst.at[center_hair_idx, 'label'].item()
        except:
            print("\n\nCan't find hair in this image :( \n")
            pass

    print("\n\nLabel for shortest distance:")
    print(center_hair)
    print(type(center_hair))
    if center_hair < 1:
        center_hair = 0
    elif center_hair >= 1:
        center_hair = int(center_hair-1)
    else:
        center_hair = None
        print("\nThere's been a problem - no hair found!\n")

    print("\nThis is the label for the hair of interest: {}\n".format(center_hair))

    bbox_final = list(props[center_hair].bbox)

    return center_hair, bbox_final


def make_all_dirs(main_output_path):
    filtered_dir = make_subdirectory(main_output_path, append_name="filtered")

    binary_dir = make_subdirectory(main_output_path, append_name="binary")

    pruned_dir = make_subdirectory(main_output_path, append_name="pruned")

    clean_dir = make_subdirectory(main_output_path, append_name="clean")

    skeleton_dir = make_subdirectory(main_output_path, append_name="skeletonized")

    analysis_dir = make_subdirectory(main_output_path, append_name="analysis")

    return main_output_path, filtered_dir, binary_dir, pruned_dir, clean_dir, skeleton_dir, analysis_dir


def make_subdirectory(directory, append_name=""):
    """
    Function to build a directory based upon the arguments passed in append. Takes a
    directory and uses pathlib to join that to the appended string passed.
​
    :param directory:       The directory within which this function will make a subdirectory.
    :param append_name:     A string to be appended to the pathlib object.
    :return output_path:    Returns a new directory for output.

​
    """
    # Define the path of the directory within which this function will make a subdirectory.
    directory = pathlib.Path(directory)
    # The name of the subdirectory.
    append_name = str(append_name)
    # Define the output path by the initial directory and join (i.e. "+") the appropriate text.
    output_path = pathlib.Path(directory).joinpath(str(append_name))

    # Use pathlib to see if the output path exists, if it is there it returns True
    if pathlib.Path(output_path).exists() == False:

        # Prints a status method to the console using the format option, which fills in the {} with whatever
        # is in the ().
        print(
            "This output path doesn't exist:\n            {} \n Creating...".format(
                output_path))

        # Use pathlib to create the folder.
        pathlib.Path.mkdir(output_path)

        # Prints a status to let you know that the folder has been created
        print("Output path has been created")

    # Since it's a boolean return, and True is the only other option we will simply print the output.
    else:
        # This will print exactly what you tell it, including the space. The backslash n means new line.
        print(
            "Output path already exists:\n               {}".format(
                output_path))
    return output_path

def list_images(directory, file_type):
    # Change to the folder for reading images
    os.chdir(str(directory))
    glob_file_type = "*" + file_type
    file_list = []
    for filename in pathlib.Path(directory).rglob(glob_file_type):
        file_list.append(filename)
    list.sort(file_list)  # sort the files
    print(len(file_list))  # printed the sorted files
    
    return file_list

def pretty_time_delta(seconds):

    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '%dh%dm%ds' % (hours, minutes, seconds)
    elif minutes > 0:
        return '%dm%ds' % (minutes, seconds)
    else:
        return '%ds' % (seconds,)


def raw_to_gray(imgfile, output_directory):
    """

    Function to convert raw files to gray tiff files

    :param imgfile:             raw image file
    :param output_directory:    output directory where tiff folder will be created
    :return:
            - img: PIL image object
            - tiff_output_path: pathlib object with image path


    """
    imgfile = os.path.abspath(imgfile)
    output_directory = output_directory
    basename = os.path.basename(imgfile)
    name = os.path.splitext(basename)[0] + ".tiff"
    output_name = pathlib.Path(output_directory).joinpath(name)
    print("\n\n")
    print(name)

    try:
        with rawpy.imread(imgfile) as raw:
            rgb = raw.postprocess(use_auto_wb=True)
            im = Image.fromarray(rgb).convert('LA')
            im.save(str(output_name))
    except:
        print("\nSomething is wrong with {}\n".format(str(f)))
        pass

    print('{} has been successfully converted to a grayscale tiff.\n Path is {}\n'.format(name, output_name))

    return output_name



def segment_section2(filename, input_file, cropped_binary_dir, pad, resolution):
    '''

    :param filename:
    :param input_file:
    :param cropped_binary_dir:
    :param pad:
    :param resolution:
    :return:
    '''

    # filename = str(input_file)
    filename = str(os.path.basename(filename))

    gray_img = input_file  # ensure gray image

    smooth = skimage.filters.rank.median(gray_img, selem=disk(int(resolution*8)))

    # thresh = threshold_otsu(smooth)
    thresh = threshold_minimum(smooth)

    # creates binary image by applying the above threshold and replacing all
    # init_ls = (np.where(gray_img > thresh, 0, 1)).astype('uint8')
    init_ls = (np.where(gray_img > thresh, 0, 1)).astype('uint8')

    chan = skimage.segmentation.morphological_chan_vese(smooth, 30, init_level_set=init_ls, smoothing=4, lambda1=1, lambda2=1)

    bw_uint8 = (np.array(chan)).astype('uint8')  # turning image into unsigned integer (0-255, grayscale)

    label_image, num_elements = label(bw_uint8, connectivity=2, return_num=True)

    image_center = list(np.divide(label_image.shape, 2))  # returns array of two floats

    center_hair, bbox_final = find_hair(label_image, image_center, minpixel)

    print("\nHair found for {} is:".format(filename))

    print(center_hair)
    print(type(center_hair))

    index_label = int(center_hair)

    region = regionprops(label_image)[index_label]

    tempdf = tempdf_gen(region, filename, resolution)

    # save binary slice
    with pathlib.Path(cropped_binary_dir).joinpath(filename) as output_name_binary:
        im = region.filled_image
        im = np.pad(im, pad, mode='constant')
        cropped_binary = np.array(im)
        im = Image.fromarray(cropped_binary)
        im.save(str(output_name_binary))
        print("Saved binary slice as {}".format(output_name_binary))

    print("\n")

    return tempdf



def tempdf_gen(region, filename, resolution):

    section_area = round(float(region.filled_area / (resolution * resolution)), 2)
    section_max = round(float(region.major_axis_length / resolution), 2)
    section_min = round(float(region.minor_axis_length / resolution), 2)
    section_eccentricity = region.eccentricity
    section_perimeter = round(float(region.perimeter / resolution), 2)
    section_id = (str(os.path.basename(filename)).rstrip('.tiff'))

    tempdf = pd.DataFrame(
        [section_id, section_area, section_max, section_min, section_eccentricity, section_perimeter]).T

    print("\nThe data for {}, are:\n {}".format(filename, tempdf))

    return tempdf


def filter_curv(input_file, output_path):

    # create pathlib object for input Image
    input_path = pathlib.Path(input_file)

    # extract image name
    im_name = input_path.stem

    # read in Image
    gray_img = cv2.imread(str(input_path), 0)
    type(gray_img)
    print("Image size is:", gray_img.shape)

    # use frangi ridge filter to find hairs, the output will be inverted
    filter_img = skimage.filters.frangi(gray_img)
    type(filter_img)
    print("Image size is:", filter_img.shape)

    # inverting and saving the filtered image
    img_inv = skimage.util.invert(filter_img)
    with pathlib.Path(output_path).joinpath(im_name + ".tiff") as save_path:
        plt.imsave(save_path, img_inv, cmap="gray")

    return filter_img, im_name


def binarize_curv(filter_img, im_name, binary_dir, save_img=False):

    selem = skimage.morphology.disk(3)
    
    thresh_im = filter_img > threshold_minimum(filter_img)
    
    # clear the border of the image (buffer is the px width to be considered as border)
    cleared_im = skimage.segmentation.clear_border(thresh_im, buffer_size=10)
    
    # dilate the hair fibers
    binary_im = scipy.ndimage.binary_dilation(cleared_im, structure=selem, iterations=2)
    
    if save_img:
        # invert image
        save_im = skimage.util.invert(binary_im)
        
        # save image
        with pathlib.Path(binary_dir).joinpath(im_name + ".tiff") as save_name:
            im = Image.fromarray(save_im)
            im.save(save_name)
        return binary_im
    else:
        return binary_im


def remove_particles(input_file, output_path, name, minpixel=5, prune=False, save_img=False):
    img_bool = np.asarray(input_file, dtype=np.bool)
    img = check_bin(img_bool)
    
    if not prune:
        minimum = minpixel
        clean = skimage.morphology.remove_small_objects(img, connectivity=2, min_size=minimum)
    else:
        # clean = img_bool
        minimum = minpixel
        clean = skimage.morphology.remove_small_objects(img, connectivity=2, min_size=minimum)
        
        print("\n Done cleaning {}".format(name))
    
    if save_img:
        img_inv = skimage.util.invert(clean)
        with pathlib.Path(output_path).joinpath(name + ".tiff") as savename:
            plt.imsave(savename, img_inv, cmap='gray')
            # im = Image.fromarray(img_inv)
            # im.save(output_path)
        return clean
    else:
        return clean


def check_bin(img):
    img_bool = np.asarray(img, dtype=np.bool)
    
    # Gets the unique values in the image matrix. Since it is binary, there should only be 2.
    unique, counts = np.unique(img_bool, return_counts=True)
    print(unique)
    print("Found this many counts:")
    print(len(counts))
    print(counts)
    
    # If the length of unique is not 2 then print that the image isn't a binary.
    if len(unique) != 2:
        print("Image is not binarized!")
        hair_pixels = len(counts)
        print("There is/are {} value(s) present, but there should be 2!\n".format(hair_pixels))
    # If it is binarized, print out that is is and then get the amount of hair pixels to background pixels.
    if counts[0] < counts[1]:
        print("{} is not reversed".format(str(img)))
        img = skimage.util.invert(img_bool)
        print("Now {} is reversed =)".format(str(img)))
        return img
    
    else:
        print("{} is already reversed".format(str(img)))
        img = img_bool
        
        print(type(img))
        return img


def skeletonize(clean_img, name, output_path, save_img=False):
    # check if image is binary and properly inverted
    clean_img = check_bin(clean_img)
    
    # skeletonize the hair
    skeleton = skimage.morphology.thin(clean_img)
    
    if save_img:
        img_inv = skimage.util.invert(skeleton)
        with pathlib.Path(output_path).joinpath(name + ".tiff") as output_path:
            im = Image.fromarray(img_inv)
            im.save(output_path)
        return skeleton
    
    else:
        print("\n Done skeletonizing {}".format(name))
        
        return skeleton


def prune(skeleton, name, pruned_dir, save_img=False):
    """
    Starting with a morphological skeleton, creates a corresponding binary image
    with all branch-points pixels (1) and all other pixels (0).
    """
    
    print("\nPruning {}...\n".format(name))
    
    # identify 3-way branch-points through convolving the image using appropriate
    # structure elements for an 8-connected skeleton:
    # http://homepages.inf.ed.ac.uk/rbf/HIPR2/thin.htm
    hit1 = np.array([[0, 1, 0],
                     [0, 1, 0],
                     [1, 0, 1]], dtype=np.uint8)
    hit2 = np.array([[1, 0, 0],
                     [0, 1, 0],
                     [1, 0, 1]], dtype=np.uint8)
    hit3 = np.array([[1, 0, 0],
                     [0, 1, 1],
                     [0, 1, 0]], dtype=np.uint8)
    hit_list = [hit1, hit2, hit3]
    
    # use some nifty NumPy slicing to add the three remaining rotations of each
    # of the structure elements to the hit list
    for ii in range(9):
        hit_list.append(np.transpose(hit_list[-3])[::-1, ...])
    
    # add structure elements for branch-points four 4-way branchpoints, these
    hit3 = np.array([[0, 1, 0],
                     [1, 1, 1],
                     [0, 1, 0]], dtype=np.uint8)
    hit4 = np.array([[1, 0, 1],
                     [0, 1, 0],
                     [1, 0, 1]], dtype=np.uint8)
    hit_list.append(hit3)
    hit_list.append(hit4)
    print("Creating hit and miss list")
    
    # create a zero np.array() of the same shape as the skeleton and use it to collect
    # "hits" from the convolution operation
    
    skel_image = check_bin(skeleton)
    print("Converting image to binary array")
    
    branch_points = np.zeros(skel_image.shape)
    print("Creating empty array for branch points")
    
    for hit in hit_list:
        target = hit.sum()
        curr = ndimage.convolve(skel_image, hit, mode="constant")
        branch_points = np.logical_or(branch_points, np.where(curr == target, 1, 0))
    
    print("Completed collection of branch points")
    
    # pixels may "hit" multiple structure elements, ensure the output is a binary
    # image
    branch_points_image = np.where(branch_points, 1, 0)
    print("Ensuring binary")
    
    # use SciPy's ndimage module to label each contiguous foreground feature
    # uniquely, this will locating and determining coordinates of each branch-point
    labels, num_labels = ndimage.label(branch_points_image)
    print("Labelling branches")
    
    # use SciPy's ndimage module to determine the coordinates/pixel corresponding
    # to the center of mass of each branchpoint
    branch_points = ndimage.center_of_mass(skel_image, labels=labels, index=range(1, num_labels + 1))
    branch_points = np.array([value for value in branch_points if not np.isnan(value[0]) or not np.isnan(value[1])],
                             dtype=int)
    num_branch_points = len(branch_points)
    
    hit = np.array([[0, 0, 0],
                    [0, 1, 0],
                    [0, 0, 0]], dtype=np.uint8)
    
    dilated_branches = ndimage.convolve(branch_points_image, hit, mode='constant')
    dilated_branches_image = np.where(dilated_branches, 1, 0)
    print("Ensuring binary dilated branches")
    pruned_image = np.subtract(skel_image, dilated_branches_image)
    # pruned_image = np.subtract(skel_image, branch_points_image)
    
    pruned_image = remove_particles(pruned_image, pruned_dir, name, prune=True, save_img=save_img)
    
    return pruned_image


def taubin_curv(coords, resolution):
    """
    Algebraic circle fit by Taubin
      G. Taubin, "Estimation Of Planar Curves, Surfaces And Nonplanar
                  Space Curves Defined By Implicit Equations, With
                  Applications To Edge And Range Image Segmentation",
      IEEE Trans. PAMI, Vol. 13, pages 1115-1138, (1991)

    :param XYcoords:    list [[x_1, y_1], [x_2, y_2], ....]
    :return:            a, b, r.  a and b are the center of the fitting circle, and r is the curv

    Parameters
    ----------
    resolution

    """
    warnings.filterwarnings("ignore")  # suppress RuntimeWarnings from dividing by zero
    XY = np.array(coords)
    X = XY[:, 0] - np.mean(XY[:, 0])  # norming points by x avg
    Y = XY[:, 1] - np.mean(XY[:, 1])  # norming points by y avg
    centroid = [np.mean(XY[:, 0]), np.mean(XY[:, 1])]
    Z = X * X + Y * Y
    Zmean = np.mean(Z)
    Z0 = ((Z - Zmean) / (2. * np.sqrt(Zmean)))  # changed from using old_div to Python 3 native division
    ZXY = np.array([Z0, X, Y]).T
    U, S, V = np.linalg.svd(ZXY, full_matrices=False)  #
    V = V.transpose()
    A = V[:, 2]
    A[0] = (A[0]) / (2. * np.sqrt(Zmean))
    A = np.concatenate([A, [(-1. * Zmean * A[0])]], axis=0)
    # a, b = (-1 * A[1:3]) / A[0] / 2 + centroid
    r = np.sqrt(A[1] * A[1] + A[2] * A[2] - 4 * A[0] * A[3]) / abs(A[0]) / 2

    if np.isfinite(r):
        curv = 1 / (r / resolution)
        return curv
    elif np.isfinite(r):
        return 0


def subset_gen(hair_pixel_length, window_size, hair_label):
    subset_start = 0
    if window_size > 10:
        subset_end = int(window_size+subset_start)
    else:
        subset_end = int(hair_pixel_length)
    while subset_end <= hair_pixel_length:
        subset = hair_label[subset_start:subset_end]
        yield subset
        subset_start += 1
        subset_end += 1


def analyze_each_curv(hair, window_size, resolution):
    """
    Calculating curvature for hair divided into windows (as opposed to the entire hair at once)

    Moving 1 pixel at a time, the loop uses 'start' and 'end' to define the window-length with which curvature is
    calculated.

    :param hair:
    :param min_hair:
    :param window_size:     the window size (in pixel)
    :param resolution:      the resolution (number of pixels in a mm)
    :return:
                            curv_mean,
                            curv_median,
                            curvature_mean,
                            curvature_median
    """
    
    hair_label = np.array(hair.coords)
    
    length_mm = float(len(hair.coords) / resolution)
    print("\nCurv length is {} mm".format(length_mm))
    
    hair_pixel_length = len(hair.coords)  # length of hair in pixels
    print("\nCurv length is {} pixels".format(hair_pixel_length))
    
    subset_loop = (subset_gen(hair_pixel_length, window_size, hair_label=hair_label))  # generates subset loop
    
    # Safe generator expression in case of errors
    curv = [taubin_curv(hair_coords, resolution) for hair_coords in subset_loop]
    
    taubin_df = pd.Series(curv).astype('float')
    print("\nCurv dataframe is:")
    print(taubin_df)
    print(type(taubin_df))
    print("\nCurv df min is:{}".format(taubin_df.min()))
    print("\nCurv df max is:{}".format(taubin_df.max()))
    
    print("\nTrimming outliers...")
    taubin_df2 = taubin_df[taubin_df.between(taubin_df.quantile(.01), taubin_df.quantile(.99))]  # without outliers
    
    print("\nAfter trimming outliers...")
    print("\nCurv dataframe is:")
    print(taubin_df2)
    print(type(taubin_df2))
    print("\nCurv df min is:{}".format(taubin_df2.min()))
    print("\nCurv df max is:{}".format(taubin_df2.max()))
    
    curv_mean = taubin_df2.mean()
    print("\nCurv mean is:{}".format(curv_mean))
    
    curv_median = taubin_df2.median()
    print("\nCurv median is:{}".format(curv_median))
    
    within_hair_df = [curv_mean, curv_median, length_mm]
    print("\nThe curvature summary stats for this element are:")
    print(within_hair_df)
    
    if within_hair_df is not None or np.nan:
        return within_hair_df
    else:
        pass

def imread(input_file):
    input_path = pathlib.Path(str(input_file))
    img = skimage.io.imread(str(input_path), as_gray=True)
    
    im_name = input_path.stem
    return img, im_name

def analyze_all_curv(img, name, analysis_dir, resolution, window_size_mm=1):
    if type(img) != 'numpy.ndarray':
        print(type)
        img = np.array(img)
    else:
        print(type(img))
    
    print("Analyzing {}".format(name))
    
    img = check_bin(img)
    
    label_image, num_elements = skimage.measure.label(img.astype(int), connectivity=2, return_num=True)
    print("\n There are {} elements in the image".format(num_elements))
    
    props = skimage.measure.regionprops(label_image)
    
    window_size = int(round(window_size_mm * resolution))  # must be an integer
    print("\nWindow size for analysis is {} pixels".format(window_size))
    print("Analysis of curvature for each element begins...")
    tempdf = [analyze_each_curv(hair, window_size, resolution) for hair in props]
    
    print("\nData for {} is:".format(name))
    print(tempdf)
    
    within_curvdf = pd.DataFrame(tempdf, columns=['curv_mean', 'curv_median', 'length'])
    
    print("\nDataframe for {} is:".format(name))
    print(within_curvdf)
    print(within_curvdf.dtypes)
    
    # remove outliers
    q1 = within_curvdf.quantile(0.1)
    q3 = within_curvdf.quantile(0.9)
    iqr = q3 - q1
    
    within_curv_outliers = within_curvdf[
        ~((within_curvdf < (q1 - 1.5 * iqr)) | (within_curvdf > (q3 + 1.5 * iqr))).any(axis=1)]
    
    print(within_curv_outliers)
    
    within_curvdf2 = pd.DataFrame(within_curv_outliers, columns=['curv_mean', 'curv_median', 'length']).dropna()
    
    print("\nDataFrame with NaN values dropped:")
    print(within_curvdf2)
    
    with pathlib.Path(analysis_dir).joinpath(name + ".csv") as save_path:
        within_curvdf2.to_csv(save_path)
    
    curv_mean_im_mean = within_curvdf2['curv_mean'].mean()
    curv_mean_im_median = within_curvdf2['curv_mean'].median()
    curv_median_im_mean = within_curvdf2['curv_median'].mean()
    curv_median_im_median = within_curvdf2['curv_median'].median()
    length_mean = within_curvdf2['length'].mean()
    length_median = within_curvdf2['length'].median()
    hair_count = len(within_curvdf2.index)
    
    sorted_df = pd.DataFrame(
        [name, curv_mean_im_mean, curv_mean_im_median, curv_median_im_mean, curv_median_im_median, length_mean,
         length_median, hair_count]).T
    
    print("\nDataframe for {} is:".format(name))
    print(sorted_df)
    print("\n")
    
    return sorted_df

def curvature_seq(input_file, filtered_dir, binary_dir, pruned_dir, clean_dir, skeleton_dir, analysis_dir,
                  resolution, window_size_mm, save_img):

    # filter
    filter_img, im_name = filter_curv(input_file, filtered_dir)

    # binarize
    binary_img = binarize_curv(filter_img, im_name, binary_dir, save_img)

    # remove particles
    clean_im = remove_particles(binary_img, clean_dir, im_name, minpixel=5, prune=False, save_img=save_img)

    # skeletonize
    skeleton_im = skeletonize(clean_im, im_name, skeleton_dir, save_img)

    # prune
    pruned_im = prune(skeleton_im, im_name, pruned_dir, save_img)

    # analyze
    im_df = analyze_all_curv(pruned_im, im_name, analysis_dir, resolution, window_size_mm)

    return im_df

# Main modules (organized in order of operations: consolidate_files, raw2gray, curvature, section)

def consolidate_files(input_directory, output_location, file_type, jobs):
    """
    """
    total_start = timer()

    # Changing directory to where the raw images are
    os.chdir(input_directory)
    glob_file_type = "*{}".format(file_type)  # find all files with the file_type extension

    file_list = []
    for filename in pathlib.Path(input_directory).rglob(glob_file_type):
        file_list.append(filename)
    list.sort(file_list)  # sort the files
    print(len(file_list))  # printed the sorted files

    output_directory = make_subdirectory(output_location, append_name="Raw")

    Parallel(n_jobs=jobs, verbose=100)(delayed(copy_if_exist)(f, output_directory) for f in file_list)

    total_end = timer()
    total_time = str(pretty_time_delta(total_end - total_start))

    # This will print out the minutes to the console, with 2 decimal places.
    print("Entire consolidation took: {}.".format(total_time))

    return True


def raw2gray(input_directory, output_location, file_type, jobs):
    """
    """

    total_start = timer()

    # Convert raw files to tiff or copy TIFFs into new directory

    # Changing directory to where the raw images are
    os.chdir(input_directory)
    glob_file_type = "*{}".format(file_type)  # find all files with the file_type extension

    file_list = []
    for f in pathlib.Path(input_directory).rglob(glob_file_type):
        file = pathlib.Path(f)
        filename = os.path.abspath(file)
        file_list.append(filename)

    # file_list = glob.glob((str(glob_file_type)), recursive=True)  # find all the raw files in that directory
    list.sort(file_list)  # sort the files
    print(file_list)  # printed the sorted files

    print("There are {} files to convert".format(len(file_list)))
    print("\n\n")

    # %% Converting files
    # A loop for turning all raw files into grayscale tiffs

    print("Converting raw files into grayscale tiff files...\n")

    tiff_directory = make_subdirectory(output_location, append_name="tiff")

    Parallel(n_jobs=jobs, verbose=100)(delayed(raw_to_gray)(f, tiff_directory) for f in file_list)

    # # for debugging
    # file_list = file_list[:3]
    # f = file_list[0]
    # output_directory = tiff_directory
    # imgfile = f
    #
    # [raw_to_gray(f, tiff_directory) for f in file_list]

    # End the timer and then print out the how long it took
    total_end = timer()
    total_time = (total_end - total_start)

    # This will print out the minutes to the console, with 2 decimal places.
    print("\n\n")
    print("Entire analysis took: {}.".format(convert(total_time)))

    return True


def curvature(tiff_directory, output_location, file_type, jobs, resolution, window_size_mm, save_img):
    """
    """
    total_start = timer()

    # create an output directory for the analyses
    main_output_path, filtered_dir, binary_dir, pruned_dir, clean_dir, skeleton_dir, analysis_dir = make_all_dirs(
    output_location)

    file_list = list_images(tiff_directory, file_type)
    
    # List expression for curv df per image
    # im_df = [curvature_seq(input_file, filtered_dir, binary_dir, pruned_dir, clean_dir, skeleton_dir, analysis_dir, resolution, window_size_mm, save_img) for input_file in file_list]

    # This is the old parallel jobs function
    im_df = (Parallel(n_jobs=jobs, verbose=100)(delayed(curvature_seq)(input_file, filtered_dir, binary_dir, pruned_dir, clean_dir, skeleton_dir, analysis_dir, resolution, window_size_mm, save_img) for input_file in file_list))
    
    summary_df = pd.concat(im_df)
    summary_df.columns = [
        "ID", "curv_mean_mean", "curv_mean_median", "curv_median_mean", "curv_median_median",
        "length_mean", "length_median", "hair_count"]

    cols1 = [
        "curv_mean_mean", "curv_mean_median", "curv_median_mean",
        "curv_median_median", "length_mean", "length_median"]

    cols2 = ["length_mean", "length_median"]

    summary_df[cols1] = summary_df[cols1].astype(float).round(5)

    summary_df[cols2] = summary_df[cols2].astype(float).round(2)

    summary_df.set_index('ID', inplace=True)

    print("You've got data...")
    print(summary_df)

    jetzt = datetime.now()
    timestamp = jetzt.strftime("_%b%d_%H%M")

    with pathlib.Path(main_output_path).joinpath("curvature_summary_data{}.csv".format(timestamp)) as output_path:
        summary_df.to_csv(output_path)
        print(output_path)

    # End the timer and then print out the how long it took
    total_end = timer()
    total_time = (total_end - total_start)

    # This will print out the minutes to the console, with 2 decimal places.
    print("Entire analysis took: {}.".format(convert(total_time)))

    return True


def section(tiff_directory, main_output_path, file_type, jobs, resolution,
    min_size, pad, crop=True, save_crop=True):
    """
    """
    total_start = timer()

    minpixel = int(min_size * resolution)

    # Change to the folder for reading images
    cropped_list = list_images(tiff_directory, file_type)

    # Shows what is in the cropped_list. The backslash n prints a new line
    print("There are ", len(cropped_list), "files in the cropped_list:\n")
    print(cropped_list, "\n\n")

    # Creating subdirectories for cropped images

    cropped_binary_dir = make_subdirectory(main_output_path, "cropped_binary")

    if save_crop == "True":
        save_crop = True
    else:
        save_crop = False

    if save_crop:
        cropped_dir = make_subdirectory(main_output_path, "cropped")
        save_crop = True
        print("\nYou will have a folder of cropped grayscale images\n")
    else:
        cropped_dir = None
        save_crop = False

    # section_df = (crop_image(f, cropped_dir, cropped_binary_dir, pad, minpixel=minpixel, resolution=resolution) for f in cropped_list)

    section_df = (Parallel(n_jobs=jobs, verbose=100)(delayed(crop_image)(f, cropped_dir, cropped_binary_dir, pad, minpixel, resolution, crop, save_image=save_crop) for f in cropped_list))
    
    

    section_df = pd.concat(section_df)
    section_df.columns = ['ID', 'area', 'max', 'min', 'eccentricity', 'perimeter']
    section_index = section_df.set_index('ID')

    with pathlib.Path(main_output_path).joinpath("section_data.csv") as df_output_path:
        section_index.to_csv(df_output_path)

    # End the timer and then print out the how long it took
    total_end = timer()
    total_time = int(total_end - total_start)

    print("Complete analysis time: {}".format(convert(total_time)))

    return True


def main():
    """
    """

    args = parse_args()

    # Check for output directory and create it if it doesn't exist
    output_dir = make_subdirectory(args.output_directory)

    # Run fibermorph
    if args.consolidate is True:
        consolidate_files(
            args.input_directory, output_dir, args.file_extension, args.jobs)
    elif args.raw2gray is True:
        raw2gray(
            args.input_directory, output_dir, args.file_extension, args.jobs)
    elif args.curvature is True:
        curvature(
            args.input_directory, output_dir, args.file_extension, args.jobs,
            args.window_size, args.min_size, args.save_image)
    elif args.section is True:
        section(
            args.input_directory, output_dir, args.file_extension, args.jobs,
            args.resolution, args.min_size, args.pad, args.crop, args.save_crop)
    else:
        sys.exit("Error. Tim didn't exhaust all module options")

    sys.exit(0)


if __name__ == "__main__":
    main()
