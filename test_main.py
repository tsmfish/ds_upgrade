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
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)

folder_for_SW = 'images/TiMOS-7.0.R13'
new_boot_file = 'cf1:/{0}/boot.tim'.format(folder_for_SW)
new_primary_img = 'cf1:/{0}/both.tim'.format(folder_for_SW)

target_sw_boot_version = 'TiMOS-L-7.0.R13'
target_sw_version = 'TiMOS-B-7.0.R13'

free_space_limit = 56   # in Mbytes
random_wait_time = 5    # in seconds

log_file_format = "%y%m%d_%H%M%S_{ds_name}.log"


def print_for_ds(host, message, io_lock=None, log_file_name=None):
    if io_lock: io_lock.acquire()
    print "[{0}] : {1}".format(host, message)
    if io_lock: io_lock.release()
    if log_file_name:
        try:
            with open(log_file_name, 'a') as log_file:
                log_file.write("[{0}] : {1}".format(host, message))
                log_file.file.close()
        except IOError:
            pass


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


def post_result(result, queuq=None, log_file_name=None):
    if queuq:
        queuq.put(result)
    if log_file_name:
        try:
            with open(log_file_name, 'a') as log_file:
                log_file.write("\t{0} : ***** result: {1}, saved in file {2} *****"
                               .format(result[NAME],
                                       result[RESULT],
                                       log_file_name))
                log_file.close()
        except IOError:
            pass


def update_ds(ds_name, user, password, result_queue=Queue(), io_lock=None, force_delete=False, log_to_file=False):
    if io_lock: time.sleep(random_wait_time * random.random())
    if log_to_file:
        log_file_name = time.strftime(log_file_format.format(ds_name=ds_name))
    else:
        log_file_name = None

    print_for_ds(ds_name, force_delete, io_lock, log_file_name)

    # Create object
    node = DS(ds_name, user, password)

    # Connect and get basic inform
    print_for_ds(ds_name, '=' * 15 + ' Start process for \"{ds}\" '.format(ds=node.ip) + '=' * 15,
                 io_lock,
                 log_file_name)

    try:
        node.conn()
    except Exception:
        print_for_ds(ds_name, '\033[91m'+'Cannot connect'+'\033[0m', io_lock, log_file_name)
        post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
        return

    node.get_base_info()

    print_for_ds(ds_name,
                 '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=node.ip) + '=' * 15,
                 io_lock,
                 log_file_name)
    post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Prepare DS upgrade SW to \"{0}\" version.'.format(target_sw_version),
                                   usage="usage: %prog [-y] [-n] [-l] [-f <ds list file> | ds ds ds ...]")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with DS list", metavar="FILE")
    parser.add_option("-y", "--yes", dest="force_delete",
                      help="force remove unused SW images (both/boot)",
                      action="store_true", default=False)
    parser.add_option("-n", "--no-thread", dest="no_threads",
                      help="execute nodes one by one sequentially",
                      action="store_true", default=False)
    parser.add_option("-l", "--log-to-file", dest="log_to_file",
                      help="enable logging to file yymmdd_hhmmss_ds-name.log",
                      action="store_true", default=False)

    (options, args) = parser.parse_args()
    ds_list_raw = list(extract(ds_name_pattern, ds) for ds in args if is_contains(ds_name_pattern, ds))

    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines():
                    ds_list_raw.append(extract(ds_name_pattern, line))
        except IOError as e:
            print "Error while open file: {file}".format(file=options.ds_list_file_name)
            print str(e)

    ds_list = list(set(ds_list_raw))

    if not ds_list:
        parser.print_help()
        exit()

    if len(ds_list) < 1:
        print "No ds found in arguments."
        exit()

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    print "Start running: {0}".format(time.strftime("%H:%M:%S"))

    if len(ds_list) == 1:
        update_ds(ds_list[0],
                  user,
                  secret,
                  force_delete=options.force_delete,
                  log_to_file=options.log_to_file)
    else:
        io_lock = threading.Lock()
        result = {COMPLETE: list(), FATAL: list(), TEMPORARY: ds_list}

        while result[TEMPORARY]:

            result_queue, threads = Queue(), list()

            if options.no_threads:
                for ds_name in result[TEMPORARY]:
                    try:
                        update_ds(ds_list[0],
                                  user,
                                  secret,
                                  result_queue=result_queue,
                                  force_delete=options.force_delete,
                                  log_to_file=options.log_to_file)
                    except Exception:
                        print_for_ds(ds_name, "**! Unhandled exception")
            else:
                for ds_name in result[TEMPORARY]:
                    thread = threading.Thread(target=update_ds, name=ds_name, args=(ds_name,
                                                                                    user,
                                                                                    secret,
                                                                                    result_queue,
                                                                                    io_lock,
                                                                                    options.force_delete,
                                                                                    options.log_to_file))
                    thread.start()
                    threads.append(thread)

                for thread in threads:
                    thread.join()

            result = {COMPLETE: list(), FATAL: list(), TEMPORARY: list()}

            while not result_queue.empty():
                thread_result = result_queue.get()
                result[thread_result[RESULT]].append(thread_result[NAME])

            # determinate ds with unhandled error and mark it as FATAL
            for ds_name in (ds for ds in ds_list if ds not in (result[COMPLETE]+result[TEMPORARY]+result[FATAL])):
                result[FATAL].append(ds_name)
                if options.log_to_file:
                    post_result({NAME: ds_name, RESULT: FATAL},
                                None,
                                time.strftime(log_file_format.format(ds_name=ds_name)))

            result[COMPLETE].append(COMPLETE)
            result[TEMPORARY].append(TEMPORARY)
            result[FATAL].append(FATAL)

            if result[COMPLETE]:  print '\033[92m'+"\nComplete on       : " + ", ".join(sorted(result[COMPLETE]))+'\033[0m'
            if result[TEMPORARY]: print   '\033[93m'+"Temporary fault on: " + ", ".join(sorted(result[TEMPORARY]))+'\033[0m'
            if result[FATAL]:     print   '\033[91m'+"Fatal error on    : " + ", ".join(sorted(result[FATAL]))+'\033[0m'
            print "\n"

            if not result[TEMPORARY]: break # finish try loading
            if raw_input("Repeat load on temporary faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

    print "Finish running: {0}".format(time.strftime("%H:%M:%S"))
