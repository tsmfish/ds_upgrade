#!/usr/bin/env python2.6
# -*- coding: utf-8
import getpass
import optparse
import re
import threading
from datetime import date

from DS_Class import DS

NAME, RESULT = 'name', 'result'
FILE_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
PRINT_TIMESTAMP_FORMAT = '%Y-%m-%d at %H:%M:%S'
NEW_SW_VERSION = 'TiMOS-B-7.0.R13'
FREE_SPACE_LIMIT = 65*1024*1024

class STATE:
    COMPLETE, \
    FATAL, \
    PERMANENT = 'complete', 'fatal', 'permanent'

class CAUSE:
    DS_TYPE_NOT_MATCH = 'DS type and primary image type does not match'
    NO_PRIMARY_IMAGE_FILE = 'primary image file absent'
    NO_CONNECTION = 'no connection'
    NO_PRIMARY_IMAGE_BOF = 'no primary image in BOF'

class RE:
    PRIMARY_BOF_IMAGE = re.compile(r'primary-image\s+?(\S+)\b')
    FILE_DATE = re.compile(r'\b\d\d\/\d\d\/\d\d\d\d\b')
    FILE_TIME = re.compile(r'\b\d\d:\d\d[am]\b')
    DIR_FILE_PREAMBULE = re.compile(FILE_DATE+r'\s+?'+FILE_TIME+r'\s+?(?:<DIR>|\d+?)\s+?')
    DS_TYPE = re.compile(r'\bSAS-[XM]\b')
    '''
    TiMOS-B-4.0.R2
    TiMOS-B-5.0.R2
    TiMOS-B-7.0.R9
    TiMOS-B-7.0.R13
    '''
    SW_VERSION = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b')
    FREE_SPACE_SIZE = re.compile(r'\b(\d+?)\s+?bytes free\.')
    DS_NAME = re.compile(r'ds\d+?-[0-9a-z]+\b')

def print_for_ds(host, message):
    print "[{0}] : ".format(host + message)


def extract(str, regexp, flags=re.IGNORECASE):
    try:
        return regexp.findall(str, flags)[0]
    except IndexError as e:
        return ""


def contains(str, regexp, flags=re.IGNORECASE):
    if regexp.search(str, flags):
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
        log_file_name = "%s_%s" % (date.today().strftime(FILE_TIMESTAMP_FORMAT), host)
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

    :param host:
    :param user:
    :param password:
    :param log:
    :return:
    """
    ds = DS(host, user, password)
    try:
        ds.conn()
    except Exception as e:
        print_for_ds(host, "Cannot connect to %s" % host)
        print_for_ds(host, e.message)
        log_to_file(host, STATE.PERMANENT, CAUSE.NO_CONNECTION, log)
        return

    primary_bof_image = extract(ds.send(b'sow bof'), RE.PRIMARY_BOF_IMAGE)
    if not primary_bof_image:
        print_for_ds(host, "Primary image not found in BOF.")
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_BOF, log)
        return

    if not contains(ds.send(b'file dir ' + primary_bof_image), RE.DIR_FILE_PREAMBULE + primary_bof_image):
        print_for_ds(host, "Primary image file [{0}] not found".format(primary_bof_image))
        log_to_file(host, CAUSE.NO_PRIMARY_IMAGE_FILE, log)
        return

    ds_type = extract(ds.send(b'show version'), RE.DS_TYPE)
    primary_image_ds_type = extract(ds.send(b'file version ' + primary_bof_image), RE.DS_TYPE)

    if ds_type.lower() != primary_image_ds_type.lower():
        print_for_ds(host, "DS type and primary image type does not match.")
        log_to_file(host, CAUSE.DS_TYPE_NOT_MATCH, STATE.PERMANENT, log)
        return

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

parser = optparse.OptionParser(description='Check DS before upgrade', usage="usage: %prog [ds_name]")
(options, args) = parser.parse_args()
if len(args) < 1:
    parser.error("incorrect number of arguments")

user = getpass.getuser()
secret = getpass.getpass('Password for DS:')

ds_list = (ds for ds in args if contains(ds, RE.DS_NAME))

print "Start audit: ".format(date.today().strftime(PRINT_TIMESTAMP_FORMAT))
if len(ds_list) == 1: make_check(ds_list[0], user, secret)
else:
    threads = list()
    for ds in ds_list:
        with threading.Thread(target=make_check(),
                              name=ds,
                              args=(ds, user, secret)) as thread:
            thread.start()
            threads.append(thread)

    for thread in threads: thread.join()

print "Finished audit: ".format(date.today().strftime(PRINT_TIMESTAMP_FORMAT))