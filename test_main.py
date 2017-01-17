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

    # Get all files
    # pprint_for_ds(ds_name, i.get_all_files())
    # input()

    # Check prim image
    primary_img = node.check_verion(node.prime_image)
    if primary_img:
        if primary_img[1] == node.hw_ver:
            print_for_ds(ds_name, '*** Primary image good and has version {0}'.format(primary_img[0]), io_lock)
            print_for_ds(ds_name, '*** ' + node.prime_image, io_lock)
        else:
            print_for_ds(ds_name, '!!!! Problem with primary image', io_lock)
            print_for_ds(ds_name, '*** ' + node.prime_image, io_lock)
            result_queue.put({NAME: ds_name, RESULT: FATAL})
            return

        if primary_img[0] != node.sw_ver:
            print_for_ds(ds_name, '!!! Version of the bof primary-image is {0} current running {1}.'
                         .format(primary_img[0], node.sw_ver))
            print_for_ds(ds_name, '!!! May be this switch already prepare for update!')

            # check file sizes
            ds_type = extract(ds_type_pattern, node.send(b'show version'))
            primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
            primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
            if primary_bof_image_size != file_sizes[ds_type.upper()]['both.tim']:
                print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                             .format(primary_bof_image, primary_bof_image_size), io_lock)
            else:
                print_for_ds(ds_name, '{0} file has correct size.'
                             .format(primary_bof_image, primary_bof_image_size), io_lock)

            boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
            if boot_tim_file_size != file_sizes[ds_type.upper()]['boot.tim']:
                print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                             .format('boot.tim', boot_tim_file_size), io_lock)
            else:
                print_for_ds(ds_name, '{0} file has correct size.'
                             .format(primary_bof_image, primary_bof_image_size), io_lock)

            result_queue.put({NAME: ds_name, RESULT: COMPLETE})
            return

    # Find old soft
    print_for_ds(ds_name, '*** Finding all sw in cf1:/...', io_lock)
    old_boots = node.find_files('boot.tim')
    try:
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        print_for_ds(ds_name, '**! cf1:/boot.tim Not exist!', io_lock)

    print_for_ds(ds_name, '!!! ' + node.prime_image, io_lock)
    print_for_ds(ds_name, '!!! ' + node.prime_image.replace('\\', '/'), io_lock)
    print_for_ds(ds_name, '!!! ' + node.prime_image.replace('\\', '/').replace('both.tim', 'boot.tim'), io_lock)

    try:
        old_boots.remove(node.prime_image.replace('\\', '/').replace('both.tim', 'boot.tim'))
    except ValueError:
        pass

    old_both = node.find_files('both.tim')
    old_both.remove(node.prime_image.replace('\\', '/'))

    # Remove old SW
    print_for_ds(ds_name, '*** Removing old, not used SW', io_lock)
    for files in (old_boots, old_both):
        for f in files:
                print_for_ds(ds_name, f, io_lock)

    # check file sizes
    ds_type = extract(ds_type_pattern, node.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
    primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
    if primary_bof_image_size != file_sizes[ds_type.upper()]['both.tim']:
        print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                     .format(primary_bof_image, primary_bof_image_size), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
    if boot_tim_file_size != file_sizes[ds_type.upper()]['boot.tim']:
        print_for_ds(ds_name, '{0} file has size {1} and this is - WRONG!'
                     .format('boot.tim', boot_tim_file_size), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    print_for_ds(ds_name, '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=node.ip) + '=' * 15, io_lock)
    result_queue.put({NAME: ds_name, RESULT: COMPLETE})


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Get config from DS\'s and move them to 1.140',
                                   usage="usage: %prog [-f <ds list file> | ds ds ds ...]")
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
            print str(e)

    if not ds_list:
        parser.error("Use %prog [-f <ds list file> | ds ds ds ...]")

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
            print "Start running: {0}".format(time.strftime("%H:%M"))
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

            if result[COMPLETE]:  print   "\nComplete on       :" + " ".join(sorted(result[COMPLETE]))
            if result[TEMPORARY]: print "\n\nTemporary fault on:" + " ".join(sorted(result[TEMPORARY]))
            if result[FATAL]:     print     "Fatal error on    :" + " ".join(sorted(result[FATAL]))
            print "\n"

            if not result[TEMPORARY]: break # finish try loading
            if raw_input("Repeat load on temporary faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

        print "Finish running: {0}".format(time.strftime("%H:%M"))

