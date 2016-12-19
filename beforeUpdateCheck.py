#!/usr/bin/env python2.6
# -*- coding: utf-8
import getpass
import optparse
import re
import threading
from datetime import datetime

from DS_Class import DS

NAME, RESULT = 'name', 'result'
FILE_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
PRINT_TIMESTAMP_FORMAT = '%Y-%m-%d at %H:%M:%S'
NEW_SW_VERSION = 'TiMOS-B-7.0.R13'
FREE_SPACE_LIMIT = 7*1024*1024


class STATE:
    COMPLETE, \
    FATAL, \
    PERMANENT = 'complete', 'fatal', 'permanent'


class CAUSE:
    DS_TYPE_NOT_MATCH = 'DS type and primary image type does not match'
    NO_PRIMARY_IMAGE_FILE = 'primary image file absent'
    NO_CONNECTION = 'no connection'
    NO_PRIMARY_IMAGE_BOF = 'no primary image in BOF'
    SKIPPED = "Check was skipped by user"


class RE:
    FLAGS = re.IGNORECASE
    FILE_DATE_STRING = r'\b\d\d\/\d\d\/\d\d\d\d\b'
    FILE_TIME_STRING = r'\b\d\d:\d\d[am]\b'
    PRIMARY_BOF_IMAGE = re.compile(r'primary-image\s+?(\S+)\b', FLAGS)
    FILE_DATE = re.compile(FILE_DATE_STRING)
    FILE_TIME = re.compile(FILE_TIME_STRING)
    DIR_FILE_PREAMBLE = re.compile(FILE_DATE_STRING+r'\s+?'+FILE_TIME_STRING+r'\s+?(?:<DIR>|\d+?)\s+?', FLAGS)
    DS_TYPE = re.compile(r'\bSAS-[XM]\b', FLAGS)
    '''
    TiMOS-B-4.0.R2
    TiMOS-B-5.0.R2
    TiMOS-B-7.0.R9
    TiMOS-B-7.0.R13
    '''
    SW_VERSION = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', FLAGS)
    FREE_SPACE_SIZE = re.compile(r'\b(\d+?)\s+?bytes free\.', FLAGS)
    DS_NAME = re.compile(r'ds\d-[0-9a-z]+\b', FLAGS)


def print_for_ds(host, message):
    print "[{0}] : ".format(host + message)


def extract(string, regexp):
    try:
        return regexp.findall(string)[0]
    except IndexError as e:
        return ""


def contains(string, regexp):
    if regexp.search(string):
        return True
    else:
        return False

def log_to_file(host, cause, state, log_file_name=None):
    """

    :param host:
    :param cause: constant from class CAUSE or text describe event
    :param state: constant from STATE describe execution state and failure urgency
    :param log_file_name:
    :return: none
    """
    if not log_file_name:
        log_file_name = "%s_%s" % (datetime.today().strftime(FILE_TIMESTAMP_FORMAT), host)
    log_file_name += "." + state.replace(" ", "_").upper()
    try:
        with open(log_file_name, 'a') as log_file:
            log_file.write("%s: " % (host, cause))
            log_file.close()
    except IOError as e:
        print_for_ds(host, "Error write to log file.")
        print_for_ds(host, e.message)
    except OSError as e:
        print_for_ds(host, "Error open log file.")
        print_for_ds(host, e.message)


def make_check(host, user, password, log=None):
    """
    Check primary-image form BOF: is value exist, is file exist, correct DS type in file, correct SW version in file
    """

    answer = ''
    while answer not in ('Y', 'S'):
        answer = raw_input("Start check on {ds} (Y-yes/S-skip):".format(ds=host)).upper()
        if answer == 'S': return

    if not log: log = "{date}_{ds}".format(date=datetime.today().strftime(FILE_TIMESTAMP_FORMAT), ds=host)
    ds = DS(host, user, password)
    try:
        ds.conn()
    except Exception as e:
        print_for_ds(host, "Cannot connect to %s" % host)
        print_for_ds(host, e.message)
        log_to_file(host, STATE.PERMANENT, CAUSE.NO_CONNECTION, log)
        return

    primary_bof_image = extract(ds.send(b'sow bof'), RE.PRIMARY_BOF_IMAGE)
    print ds.send(b'show bof')
    print primary_bof_image
    if not primary_bof_image:
        print_for_ds(host, "Primary image not found in BOF.")
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_BOF, log)
        return

    if not contains(ds.send(b'file dir ' + primary_bof_image), RE.DIR_FILE_PREAMBLE + primary_bof_image):
        print_for_ds(host, "Primary image file [{0}] not found".format(primary_bof_image))
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_FILE, log)
        return

    ds_type = extract(ds.send(b'show version'), RE.DS_TYPE)
    file_version = ds.send(b'file version ' + primary_bof_image)
    primary_image_ds_type = extract(file_version, RE.DS_TYPE)

    if ds_type.lower() != primary_image_ds_type.lower():
        print_for_ds(host, "DS type and primary image type does not match.")
        log_to_file(host, CAUSE.DS_TYPE_NOT_MATCH, STATE.PERMANENT, log)
        return

    sw_version_main_file = extract(file_version, RE.SW_VERSION)
    answer = 'C'
    while answer == 'C' and NEW_SW_VERSION.upper() != sw_version_main_file.upper():
        while answer not in ('S', 'C'):
            answer = raw_input('Primary file has version {sw_version} skip or check one more time (S-skip/C-check):'
                               .format(sw_version=sw_version_main_file)).upper()
        if answer == 'C':
            sw_version_main_file = extract(ds.send(b'file version ' + primary_bof_image), RE.SW_VERSION)

    free_space_size = int(extract(ds.send(b'file dir'), RE.FREE_SPACE_SIZE))
    if free_space_size < FREE_SPACE_LIMIT:
        print_for_ds(host, "Has only {0} MB free space.".format(free_space_size / 1024 / 1024))

    print_for_ds(host, "All clear.")
    log_to_file(host, """{host} - all clear.
{primary_image} - primary image has type {primary_image_type}.
{host} - {ds_type}. Has {free_space} MB free space.
""".format(host=host,
           primary_image=primary_bof_image,
           primary_image_type=primary_image_ds_type,
           ds_type=ds_type,
           free_space=free_space_size), STATE.COMPLETE, log)

if __name__ == "__main__":
    parser = optparse.OptionParser(description='Check DS before upgrade', usage="usage: %prog ds_name ...")
    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("incorrect number of arguments")

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    ds_list = list(ds for ds in args if contains(ds, RE.DS_NAME))
    print ds_list
    print "Start audit: {0}".format(datetime.today().strftime(PRINT_TIMESTAMP_FORMAT))
    if len(ds_list) == 1: make_check(ds_list[0], user, secret)
    else:
        threads = list()
        for ds in ds_list:
            thread = threading.Thread(target=make_check, name=ds, args=(ds, user, secret))
            thread.start()
            threads.append(thread)

        for thread in threads: thread.join()

    print "Finished audit: {0}".format(datetime.today().strftime(PRINT_TIMESTAMP_FORMAT))
