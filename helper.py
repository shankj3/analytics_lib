import os


def direc_check(directory):
    """ check if directory called exists, if it doesn't, recursively create the whole path. """
    if not os.path.exists(directory):
        os.makedirs(directory)