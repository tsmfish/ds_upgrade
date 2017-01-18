#!/usr/bin/env python2.6
# -*- coding: utf-8

import getpass
import optparse
import random
import re
import threading
import time
from Queue import Queue

from DS_Class import DS
from copy_over_scp import scp_copy

COMPLETE, FATAL, TEMPORARY = 'complete', 'fatal', 'temporary'
NAME, RESULT = 'name', 'result'


new_SW = {
    'SAS-X': '/home/mpls/soft/7210-SAS-X-TiMOS-7.0.R13/',
    'SAS-M': '/home/mpls/soft/7210-SAS-M-TiMOS-7.0.R13/'}

file_sizes = {  # should be STRING, for comparision with re.pastern catches filed
    'SAS-X': {
        'boot.tim': '8430496',
        'both.tim': '44336672'
    },
    'SAS-M': {
        'boot.tim': '7486880',
        'both.tim': '43364928'
    }
}


ds_name_pattern = re.compile(r'ds\d+?-[0-9a-z]+\b', re.IGNORECASE)
ds_type_pattern = re.compile(r'\bSAS-[XM]\b', re.IGNORECASE)
file_size_pattern = re.compile(r'\b\d{2}\/\d{2}\/\d{4}\s+?\d{2}:\d{2}[ap]\s+?(\d+?)\s+?')
sw_version_pattern = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', re.IGNORECASE)

folder_for_SW = 'images/TiMOS-7.0.R13'

new_boot_file = 'cf1:/{0}/boot.tim'.format(folder_for_SW)
new_primary_img = 'cf1:/{0}/both.tim'.format(folder_for_SW)
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)

target_sw_boot_version = 'TiMOS-L-7.0.R13'
target_sw_version = 'TiMOS-B-7.0.R13'

free_space_limit = 56   # in Mbytes
random_wait_time = 5    # in seconds


def print_for_ds(host, message, io_lock=None):
    if io_lock: io_lock.acquire()
    print "[%s] : " % host + message
    if io_lock: io_lock.release()


def is_contains(regexp, text):
    """

    :param regexp:
    :param text:
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: True if string contains regular expression
    """
    if re.search(regexp, text):
        return True
    else:
        return False


def extract(regexp, text):
    """

    :param regexp: regular expression
    :param text: source for extracting
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: first occur regular expression
    """
    try:
        return re.findall(regexp, text)[0]
    except IndexError:
        return ""


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Get config from DS\'s and move them to 1.140',
                                   usage="usage: %prog [-y] [-f <ds list file> | ds ds ds ...]")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with list DS", metavar="FILE")
    parser.add_option("-y", "--yes", dest="force_delete",
                      help="force remove unused SW images (both/boot)",
                      action="store_true", default=False)

    (options, args) = parser.parse_args()
    print args
    print options
    print options.ds_list_file_name
    print options.force_delete

    print "Finish running: {0}".format(time.strftime("%H:%m:%S"))
