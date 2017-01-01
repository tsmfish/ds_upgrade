#!/usr/bin/env python2.6
# -*- coding: utf-8
import Queue
import getpass
import optparse
import re
import threading
from datetime import datetime

from DS_Class import DS
from ds_helper import RE, is_contains, extract, ds_print

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


def log_to_file(host, cause, state, log_file_name=None, io_lock=None):
    """

    :param host:
    :param cause: constant from class CAUSE or text describe event
    :param state: constant from STATE describe execution state and failure urgency
    :param log_file_name:
    :return: none
    """
    if not log_file_name:
        log_file_name = "{date}_{host}".format(date=datetime.today().strftime(FILE_TIMESTAMP_FORMAT), host=host)
    log_file_name += "." + state.replace(" ", "_").upper()

    try:
        with open(log_file_name, 'a') as log_file:
            log_file.write("%s: " % (host, cause))
            log_file.close()
    except IOError as e:
        ds_print(host, "Error write to log file.", io_lock)
        ds_print(host, str(e), io_lock)
    except OSError as e:
        ds_print(host, "Error open log file.", io_lock)
        ds_print(host, str(e), io_lock)


def make_check(host, user, password, log=None, io_lock=None):
    """
    Check primary-image form BOF: is value exist, is file exist, correct DS type in file, correct SW version in file
    """

    answer = ''
    while answer not in ('Y', 'S'):
        if io_lock: io_lock.acquire()
        answer = raw_input("Start check on {ds} (Y-yes/S-skip):".format(ds=host)).upper()
        if io_lock: io_lock.release()
        if answer == 'S': return

    ds = DS(host, user, password)
    try:
        ds.conn()
    except Exception as e:
        ds_print(host, "Cannot connect to %s" % host, io_lock)
        ds_print(host, str(e), io_lock)
        log_to_file(host, STATE.PERMANENT, CAUSE.NO_CONNECTION, log, io_lock)
        return

    primary_bof_image = extract(ds.send(b'sow bof'), RE.PRIMARY_BOF_IMAGE)
    ds_print(ds, ds.send(b'show bof'), io_lock)

    if not primary_bof_image:
        ds_print(host, "Primary image not found in BOF.", io_lock)
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_BOF, log, io_lock)
        return

    if not is_contains(ds.send(b'file dir ' + primary_bof_image), RE.DIR_FILE_PREAMBLE + primary_bof_image):
        ds_print(host, "Primary image file [{0}] not found".format(primary_bof_image), io_lock)
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_FILE, log, io_lock)
        return

    ds_type = extract(ds.send(b'show version'), RE.DS_TYPE)
    file_version = ds.send(b'file version ' + primary_bof_image)
    primary_image_ds_type = extract(file_version, RE.DS_TYPE)

    if ds_type.lower() != primary_image_ds_type.lower():
        ds_print(host, "DS type and primary image type does not match.", io_lock)
        log_to_file(host, CAUSE.DS_TYPE_NOT_MATCH, STATE.PERMANENT, log, io_lock)
        return

    sw_version_main_file = extract(file_version, RE.SW_VERSION)
    answer = 'C'
    while answer == 'C' and NEW_SW_VERSION.upper() != sw_version_main_file.upper():
        while answer not in ('S', 'C'):
            if io_lock: io_lock.acquire()
            answer = raw_input('Primary file has version {sw_version} skip or check one more time (S-skip/C-check):'
                               .format(sw_version=sw_version_main_file)).upper()
            if io_lock: io_lock.release()
        if answer == 'C':
            sw_version_main_file = extract(ds.send(b'file version ' + primary_bof_image), RE.SW_VERSION)

    free_space_size = int(extract(ds.send(b'file dir'), RE.FREE_SPACE_SIZE))
    if free_space_size < FREE_SPACE_LIMIT:
        ds_print(host, "Has only {0} MB free space.".format(free_space_size / 1024 / 1024), io_lock)

    ds_print(host, "All clear.", io_lock)
    log_to_file(host, """{host} - all clear.
{primary_image} - primary image has type {primary_image_type}.
{host} - {ds_type}. Has {free_space} MB free space.
""".format(host=host,
           primary_image=primary_bof_image,
           primary_image_type=primary_image_ds_type,
           ds_type=ds_type,
           free_space=free_space_size), STATE.COMPLETE, log, io_lock)

if __name__ == "__main__":
    parser = optparse.OptionParser(description='Check DS before upgrade', usage="usage: %prog ds_name ...")
    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("incorrect number of arguments")

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    ds_list = list(ds for ds in args if is_contains(ds, RE.DS_NAME))
    print ds_list
    print "Start audit: {0}".format(datetime.today().strftime(PRINT_TIMESTAMP_FORMAT))
    if len(ds_list) == 1: make_check(ds_list[0], user, secret, io_lock=None)
    else:
        threads = list()
        io_lock = threading.Lock()
        for ds in ds_list:
            try:
                thread = threading.Thread(target=make_check, name=ds, args=(ds, user, secret, None, io_lock))
                thread.start()
                threads.append(thread)
            except Exception as e:
                ds_print(ds, str(e), io_lock)

        for thread in threads: thread.join()

    print "Finished audit: {0}".format(datetime.today().strftime(PRINT_TIMESTAMP_FORMAT))
