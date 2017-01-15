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

file_sizes = {
    'SAS-X': {
        'boot.tim': '8430496',
        'both.tim': '44336672'
    },
    'SAS-M': {
        'boot.tim': '7486880',
        'both.tim': '43364928'
    }
}


folder_for_SW = 'images/TiMOS-7.0.R13'
new_primary_img = 'cf1:/{0}/both.tim'.format(folder_for_SW)
new_boot_file = 'cf1:/{0}/boot.tim'.format(folder_for_SW)
ds_name_pattern = re.compile(r'ds\d+?-[0-9a-z]+\b', re.IGNORECASE)
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)
ds_type_pattern = re.compile(r'\bSAS-[XM]\b', re.IGNORECASE)
sw_version_pattern = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', re.IGNORECASE)
target_sw_version = 'TiMOS-B-7.0.R13'
target_sw_boot_version = 'TiMOS-L-7.0.R13'
random_wait_time = 5
free_space_limit = 56
file_size_pattern = r'\b\d{2}\/\d{2}\/\d{4}\s+?\d{2}:\d{2}[ap]\s+?(\d+?)\s+?'


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
        return re.findall(regexp, text).pop()
    except IndexError as error:
        return None


def update_ds(ds_name, user, password, result_queue, io_lock=None):
    if io_lock: time.sleep(random_wait_time * random.random())

    # Create object
    node = DS(ds_name, user, password)

    # Connect and get basic inform
    print_for_ds(ds_name, '=' * 15 + ' Start process for \"{ds}\" '.format(ds=node.ip) + '=' * 15, io_lock)

    try:
        node.conn()
    except Exception as e:
        print_for_ds(ds_name, str(e), io_lock)
        result_queue.put({NAME: ds_name, RESULT: FATAL})
        return

    node.get_base_info()


    # after work check
    ds_type = extract(ds_type_pattern, node.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
    primary_bof_image_print = node.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(ds_type_pattern, primary_bof_image_print)

    print_for_ds(ds_name, 'Primary BOF type: {0}, ds has type: {1}.'
                 .format(primary_bof_image_type, ds_type), io_lock)
    if primary_bof_image_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)

    primary_bof_image_version = extract(sw_version_pattern, primary_bof_image_print)
    print_for_ds(ds_name, 'Primary BOF SW version: {0}, target script SW version: {1}'
                 .format(primary_bof_image_version, target_sw_version), io_lock)
    if primary_bof_image_version.lower() != target_sw_version.lower():
        print_for_ds(ds_name, 'Primary BOF SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, target_sw_version), io_lock)

    boot_tim_file_print = node.send(b'file version boot.tim')
    boot_tim_type = extract(ds_type_pattern, boot_tim_file_print)
    print_for_ds(ds_name, 'boot.tim type: {0}, ds has type: {1}.'
                 .format(boot_tim_type, ds_type), io_lock)
    if boot_tim_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(boot_tim_type, ds_type), io_lock)

    boot_tim_version = extract(sw_version_pattern, boot_tim_file_print)
    print_for_ds(ds_name, 'boot.tim SW version: {0}, target script SW version: {1}'
                 .format(boot_tim_version, target_sw_boot_version), io_lock)
    if boot_tim_version.lower() != target_sw_boot_version.lower():
        print_for_ds(ds_name, 'boot.tim SW version: {0}, target script SW version: {1}'
                     .format(boot_tim_version, target_sw_boot_version), io_lock)

    # check file sizes
    primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
    print_for_ds(ds_name, '{0} file has size {1}.'
                 .format(primary_bof_image, primary_bof_image_size), io_lock)
    if primary_bof_image_size != file_sizes[ds_type.upper()]['both.tim']:
        print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                     .format(primary_bof_image, primary_bof_image_size), io_lock)

    boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
    print_for_ds(ds_name, '{0} file has size {1}.'
                 .format('boot.tim', boot_tim_file_size), io_lock)
    if boot_tim_file_size != file_sizes[ds_type.upper()]['boot.tim']:
        print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                     .format('boot.tim', boot_tim_file_size), io_lock)

    print_for_ds(ds_name, '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=node.ip) + '=' * 15, io_lock)
    result_queue.put({NAME: ds_name, RESULT: COMPLETE})


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Get config from DS\'s and move them to 1.140',
                                   usage="usage: %prog [file with ds list]")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with list DS", metavar="FILE")
    # parser.add_option( help='Path to file with list of ds', required=True)

    (options, args) = parser.parse_args()
    ds_list = list(ds for ds in args if is_contains(ds_name_pattern, ds))

    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines():
                    ds_list.append(extract(ds_name_pattern, line))
        except IOError as e:
            print "Error while open file: {file}".format(file=options.ds_list_file_name)
            print e.message

    if not ds_list:
        parser.error("Use [-f <ds list file> | ds ds ds ...]")

    if len(ds_list) < 1:
        print "No ds found in arguments."
        exit()

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    if len(ds_list) == 1:
        update_ds(ds_list[0], user, secret, Queue())
    else:
        io_lock = threading.Lock()
        result = {COMPLETE: list(), FATAL: list(), TEMPORARY: ds_list}

        while result[TEMPORARY]:
            print "Start running: {0}".format(time.strftime("%H:%m"))
            result_queue, threads = Queue(), list()
            for ds_name in result[TEMPORARY]:
                thread = threading.Thread(target=update_ds, name=ds_name, args=(ds_name,
                                                                                user,
                                                                                secret,
                                                                                result_queue,
                                                                                io_lock))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            result = {COMPLETE: list(), FATAL: list(), TEMPORARY: list()}

            while not result_queue.empty():
                thread_result = result_queue.get()
                result[thread_result[RESULT]].append(thread_result[NAME])

            if result[COMPLETE]:  print "\nComplete on         : " + " ".join(sorted(result[COMPLETE]))
            if result[TEMPORARY]: print "\n\nTemporary fault on: " + " ".join(sorted(result[TEMPORARY]))
            if result[FATAL]:     print "Fatal error on        : " + " ".join(sorted(result[FATAL]))
            print "\n"

            if not result[TEMPORARY]: break # finish try loading
            if raw_input("Repeat load on temporary faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

        print "Finish running: {0}".format(time.strftime("%H:%m"))
