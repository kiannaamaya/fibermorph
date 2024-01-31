import pathlib
import contextlib
import joblib
from tqdm import tqdm
from functools import wraps
import os
import sys
import timeit

def convert(seconds):
    """Converts seconds into readable format (hours, mins, seconds).

    Parameters
    ----------
    seconds : float or int
        Number of seconds to convert to final format.

    Returns
    -------
    str
        A string with the input seconds converted to a readable format.

    """
    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)
    return "%dh: %02dm: %02ds" % (hour, min, sec)
    
def timing(f): # is this code used elsewhere
    @wraps(f)
    def wrap(*args, **kw):
        print("\n\nThe {} function is currently running...\n\n".format(f.__name__))
        ts = timeit.default_timer()
        result = f(*args, **kw)
        te = timeit.default_timer()
        total_time = convert(te - ts)
        print(
            '\n\nThe function: {} \n\n with args:[{},\n{}] \n\n and result: {} \n\nTotal time: {}\n\n'.format(
                f.__name__, args, kw, result, total_time))
        return result
    
    return wrap

def blockPrint(f):
    @wraps(f)
    def wrap(*args, **kw):
        # block all printing to the console
        sys.stdout = open(os.devnull, 'w')
        # call the method in question
        value = f(*args, **kw)
        # enable all printing to the console
        sys.stdout = sys.__stdout__
        # pass the return value of the method back
        return value
    return wrap


@blockPrint
def make_subdirectory(directory, append_name=""):
    """Makes subdirectories.

    Parameters
    ----------
    directory : str or pathlib object
        A string with the path of directory where subdirectories should be created.
    append_name : str
        A string to be appended to the directory path (name of the subdirectory created).

    Returns
    -------
    pathlib object
        A pathlib object for the subdirectory created.

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
        pathlib.Path.mkdir(output_path, parents=True, exist_ok=True)
        
        # Prints a status to let you know that the folder has been created
        print("Output path has been created")
    
    # Since it's a boolean return, and True is the only other option we will simply print the output.
    else:
        # This will print exactly what you tell it, including the space. The backslash n means new line.
        print("Output path already exists:\n               {}".format(
                output_path))
    return output_path
@contextlib.contextmanager
def tqdm_joblib(tqdm_object):
    """Context manager to patch joblib to report into tqdm progress bar given as argument"""
    class TqdmBatchCompletionCallback(joblib.parallel.BatchCompletionCallBack):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __call__(self, *args, **kwargs):
            tqdm_object.update(n=self.batch_size)
            return super().__call__(*args, **kwargs)

    old_batch_callback = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = TqdmBatchCompletionCallback
    try:
        yield tqdm_object
    finally:
        joblib.parallel.BatchCompletionCallBack = old_batch_callback
        tqdm_object.close()