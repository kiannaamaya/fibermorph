import os
import sys
import pathlib
import shutil
import requests
import argparse
import common
from common import convert
import tqdm

def parse_args():
    """
    Parse command-line arguments
    Returns
    -------
    Parser argument namespace
    """
    parser = argparse.ArgumentParser(description="fibermorph")
    
    parser.add_argument(
        "-o", "--output_directory", metavar="", default=None,
        help="Required. Full path to and name of desired output directory. "
             "Will be created if it doesn't exist.")
    
    parser.add_argument(
        "-i", "--input_directory", metavar="", default=None,
        help="Required. Full path to and name of desired directory containing "
             "input files.")

    parser.add_argument(
        "--jobs", type=int, metavar="", default=1,
        help="Integer. Number of parallel jobs to run. Default is 1.")

    parser.add_argument(
        "-s", "--save_image", action="store_true", default=False,
        help="Default is False. Will save intermediate curvature/section processing images if --save_image flag is "
             "included.")

    gr_curv = parser.add_argument_group(
        "curvature options", "arguments used specifically for curvature module"
    )
    
    gr_curv.add_argument(
        "--resolution_mm", type=int, metavar="", default=132,
        help="Integer. Number of pixels per mm for curvature analysis. Default is 132.")

    gr_curv.add_argument(
        "--window_size_px", type=int, default=5, nargs='?', 
        help="Number of pixels to be used for window of measurement.")

    #gr_curv.add_argument(
        #"--window_size", metavar="", default=None, nargs='+',
        #help="Float or integer or None. Desired size for window of measurement for curvature analysis in pixels or mm (given "
             #"the flag --window_unit). If nothing is entered, the default is None and the entire hair will be used to for the curve fitting.")

    gr_curv.add_argument(
        "--window_unit", type=str, default="px", choices=["px", "mm"],
        help="String. Unit of measurement for window of measurement for curvature analysis. Can be 'px' (pixels) or "
             "'mm'. Default is 'px'.")

    gr_curv.add_argument(
        "-W", "--within_element", action="store_true", default=False,
        help="Boolean. Default is False. Will create an additional directory with spreadsheets of raw curvature "
             "measurements for each hair if the --within_element flag is included."
    )
    
    gr_sect = parser.add_argument_group(
        "section options", "arguments used specifically for section module"
    )
    
    gr_sect.add_argument(
        "--resolution_mu", type=float, metavar="", default=4.25,
        help="Float. Number of pixels per micron for section analysis. Default is 4.25.")

    gr_sect.add_argument(
        "--minsize", type=int, metavar="", default=20,
        help="Integer. Minimum diameter in microns for sections. Default is 20.")

    gr_sect.add_argument(
        "--maxsize", type=int, metavar="", default=150,
        help="Integer. Maximum diameter in microns for sections. Default is 150.")

    gr_raw = parser.add_argument_group(
        "raw2gray options", "arguments used specifically for raw2gray module"
    )
    
    gr_raw.add_argument(
        "--file_extension", type=str, metavar="", default=".RW2",
        help="Optional. String. Extension of input files to use in input_directory when using raw2gray function. "
             "Default is .RW2.")

    # gr_demo = parser.add_argument_group(
    #     "demo options", "arguments used specifically for section and curvature demo_dummy modules"
    # )
    #
    # gr_demo.add_argument(
    #     "--repeats", type=int, metavar="", default=1,
    #     help="Integer. Number of times to repeat validation module (i.e. number of sets of dummy data to generate)."
    # )

    # Create mutually exclusive flags for each of fibermorph's modules
    group = parser.add_argument_group(
        "fibermorph module options", "mutually exclusive modules that can be run with the fibermorph package"
    )
    module_group = group.add_mutually_exclusive_group(required=True)
    
    module_group.add_argument(
        "--raw2gray", action="store_true", default=False,
        help="Convert raw image files to grayscale TIFF files.")
    
    module_group.add_argument(
        "--curvature", action="store_true", default=False,
        help="Analyze curvature in grayscale TIFF images.")
    
    module_group.add_argument(
        "--section", action="store_true", default=False,
        help="Analyze cross-sections in grayscale TIFF images.")
    
    module_group.add_argument(
        "--demo_real_curv", action="store_true", default=False,
        help="A demo of fibermorph curvature analysis with real data.")
    
    module_group.add_argument(
        "--demo_real_section", action="store_true", default=False,
        help="A demo of fibermorph section analysis with real data.")
    
    # module_group.add_argument(
    #     "--demo_dummy_curv", action="store_true", default=False,
    #     help="A demo of fibermorph curvature with dummy data. Arcs and lines are generated, analyzed and error is "
    #          "calculated.")
    #
    # module_group.add_argument(
    #     "--demo_dummy_section", action="store_true", default=False,
    #     help="A demo of fibermorph section with dummy data. Circles and ellipses are generated, analyzed and error is "
    #          "calculated.")
    
    # module_group.add_argument(
    #     "--delete_dir", action="store_true", default=False,
    #     help="Delete any directory generated in analysis.")
    
    args = parser.parse_args()
    
    # # Validate arguments
    # demo_mods = [
    #     args.demo_real_curv,
    #     args.demo_real_section,
    #     args.demo_dummy_curv,
    #     args.demo_dummy_section,
    #     args.delete_dir]
    
    # Validate arguments (without dummy data)
    demo_mods = [
        args.demo_real_curv,
        args.demo_real_section]
    
    if any(demo_mods) is False:
        if args.input_directory is None and args.output_directory is None:
            sys.exit("ExitError: need both --input_directory and --output_directory")
        if args.input_directory is None:
            sys.exit("ExitError: need --input_directory")
        if args.output_directory is None:
            sys.exit("ExitError: need --output_directory")
    
    else:
        if args.output_directory is None:
            sys.exit("ExitError: need --output_directory")
    
    return args



def copy_if_exist(file, directory):
    """Copies files to destination directory.

    Parameters
    ----------
    file : str
        Path for file to be copied.
    directory : str
        Path for destination directory.

    Returns
    -------
    bool
        True or false depending on whether copying was successful.

    """
    
    path = pathlib.Path(file)
    destination = directory
    
    if os.path.isfile(path):
        shutil.copy(path, destination)
        # print('file has been copied'.format(path))
        return True
    else:
        # print('file does not exist'.format(path))
        return False


def create_results_cache(path):
    try:
        datadir = pathlib.Path(path)
        cache = common.make_subdirectory(datadir, "fibermorph_demo")

        # Designate where fibermorph should make the directory with all your results - this location must exist!
        os.makedirs(cache, exist_ok=True)
        output_directory = os.path.abspath(cache)
        return output_directory
    
    except TypeError:
        tqdm.write("Path is missing.")


def delete_dir(path):
    datadir = pathlib.Path(path)

    print("Deleting {}".format(str(datadir.resolve())))

    try:
        shutil.rmtree(datadir)
    except FileNotFoundError:
        print("The file doesn't exist. Nothing has been deleted")

    return True


def url_files(im_type):

    if im_type == "curv":

        demo_url = [
            "https://github.com/tinalasisi/fibermorph_DemoData/raw/master/test_input/curv/004_demo_curv.tiff",
            "https://github.com/tinalasisi/fibermorph_DemoData/raw/master/test_input/curv/027_demo_nocurv.tiff"]

        return demo_url

    elif im_type == "section":

        demo_url = [
            "https://github.com/tinalasisi/fibermorph_DemoData/raw/master/test_input/section/140918_demo_section.tiff",
            "https://github.com/tinalasisi/fibermorph_DemoData/raw/master/test_input/section/140918_demo_section2.tiff"]

        return demo_url


def download_im(tmpdir, demo_url):

    for u in demo_url:
        r = requests.get(u, allow_redirects=True)
        open(str(tmpdir.joinpath(pathlib.Path(u).name)), "wb").write(r.content)

    return True


def get_data(path, im_type):
    datadir = pathlib.Path(path)
    datadir = common.make_subdirectory(datadir, "tmpdata")

    if im_type == "curv" or im_type == "section":
        tmpdir = common.make_subdirectory(datadir, im_type)
        urllist = url_files(im_type)

        download_im(tmpdir, urllist)
        return tmpdir

    else:
        typelist = ["curv", "section"]
        for im_type in typelist:
            tmpdir = common.make_subdirectory(datadir, im_type)
            urllist = url_files(im_type)
            download_im(tmpdir, urllist)

        return True