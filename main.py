#!/usr/bin/env python2.6
# -*- coding: utf-8

import getpass
import optparse
import re
import threading
import time
from Queue import Queue

from DS_Class import DS
from copy_over_scp import scp_copy

COMPLETE, FATAL, PERMANENT = 'complete', 'fatal', 'permanent'
NAME, RESULT = 'name', 'result'
TARGET_SW_VERSION = 'TiMOS-B-7.0.R13'

new_SW = {
    'SAS-X': '/home/mpls/soft/7210-SAS-X-TiMOS-7.0.R13/',
    'SAS-M': '/home/mpls/soft/7210-SAS-M-TiMOS-7.0.R13/'}
folder_for_SW = 'images/TiMOS-7.0.R13'
new_primary_img = 'cf1:/{0}/both.tim'.format(folder_for_SW)
new_boot_file = 'cf1:/{0}/boot.tim'.format(folder_for_SW)
ds_name_pattern = re.compile(r'ds\d+?-[0-9a-z]+\b', re.IGNORECASE)
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)
ds_type_pattern = re.compile(r'\bSAS-[XM]\b', re.IGNORECASE)
sw_version_pattern = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', re.IGNORECASE)


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
    # Create object
    i = DS(ds_name, user, password)

    # Connect and get basic inform
    print_for_ds(ds_name, '=' * 15 + ' Start process for \"{ds}\" '.format(ds=i.ip) + '=' * 15, io_lock)

    try:
        i.conn()
    except Exception as e:
        print_for_ds(ds_name, str(e), io_lock)
        result_queue.put({NAME: ds_name, RESULT: FATAL})
        return

    i.get_base_info()

    # Get all files
    # pprint_for_ds(ds_name, i.get_all_files())
    # input()

    # Check prim image
    primary_img = i.check_verion(i.prime_image)
    if primary_img:
        if primary_img[1] == i.hw_ver:
            print_for_ds(ds_name, '*** Primary image good and has version {0}'.format(primary_img[0]), io_lock)
            print_for_ds(ds_name, '*** ' + i.prime_image, io_lock)
        else:
            print_for_ds(ds_name, '!!!! Problem with primary image', io_lock)
            print_for_ds(ds_name, '*** ' + i.prime_image, io_lock)


    # Write primary image to secondary in bof
    print_for_ds(ds_name, '*** Write primary-image to secondary in bof file', io_lock)
    cmd = 'bof secondary-image {0}'.format(i.prime_image)
    print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
    print_for_ds(ds_name, '*** {0}'.format(i.send(cmd)), io_lock)
    # print_for_ds(ds_name, i.send('show bof'))

    # Find old soft
    print_for_ds(ds_name, '*** Finding all sw in cf1:/...', io_lock)
    old_boots = i.find_files('boot.tim')
    try:
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        print_for_ds(ds_name, '**! cf1:/boot.tim Not exist!', io_lock)

    old_both = i.find_files('both.tim')
    old_both.remove(i.prime_image.replace('\\', '/'))


    # Remove old SW
    print_for_ds(ds_name, '*** Removing old SW')
    for files in (old_boots, old_both):
        for f in files:
            # For beginning ask user for all deleting in future may be auto
            if io_lock: io_lock.acquire()
            answer = raw_input("[{0}] : *** Delete {1} (y/n)? ".format(ds_name, f))
            if io_lock: io_lock.release()
            if answer.lower() == 'y':
                cmd = 'file delete {0} force'.format(f)
                print_for_ds(ds_name, '*** ' + i.send(cmd), io_lock)

    # Delete empty folders
    emt_folders = i.find_empty_folders()
    if emt_folders:
        print_for_ds(ds_name, '*** Deleting empty folders {0}'.format(','.join(emt_folders)), io_lock)
        for folder in emt_folders:
            cmd = 'file rd {0} force'.format(folder)
            print_for_ds(ds_name, i.send(cmd), io_lock)

    # Check free space
    mb = i.free_space()
    print_for_ds(ds_name, '*** Free {mb}MB on {ip}'.format(mb=mb, ip=i.ip), io_lock)
    if mb < 62:
        print_for_ds(ds_name, '!!! Not enough space for continue', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Make image folder
    print_for_ds(ds_name, '*** Try to create directory \"images\"', io_lock)
    print_for_ds(ds_name, '*** #file md cf1:\{0}'.format(folder_for_SW), io_lock)
    i.send('file md cf1:\images')
    i.send('file md cf1:\{0}'.format(folder_for_SW))


    # Copy new sw to ds
    print_for_ds(ds_name, '*** Start coping new sw...', io_lock)
    try:
        scp_copy(i.ip, i.user, i.password, new_SW[i.hw_ver], folder_for_SW)
    except Exception as e:
        print_for_ds(ds_name, str(e))
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Check free space
    mb = i.free_space()
    print_for_ds(ds_name, '*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=i.ip), io_lock)

    # Check new SW and write to bof.cfg
    print_for_ds(ds_name, '*** Write new SW to primary-image', io_lock)
    if i.check_verion(new_primary_img)[1] == i.hw_ver:
        cmd = 'bof primary-image {0}'.format(new_primary_img).replace('/', '\\')
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
        print_for_ds(ds_name, i.send(cmd), io_lock)
        # print_for_ds(ds_name, i.send('show bof'))
    else:
        print_for_ds(ds_name, '!!! New both.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Save bof and config
    print_for_ds(ds_name, '*** Save new bof and config', io_lock)
    i.save_configs()


    # Change boot.tim in root directory
    print_for_ds(ds_name, '*** Change file cf1:/boot.tim to new ({0})'.format(new_boot_file), io_lock)

    if i.check_verion(new_boot_file)[1] == i.hw_ver:
        # remove read only attribute
        print_for_ds(ds_name, '*** {0}'.format(i.send('file attrib -r cf1:/boot.tim')), io_lock)
        cmd = 'file copy {0} cf1:/boot.tim force'.format(new_boot_file)
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
        # print_for_ds(ds_name, i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5))
        i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
    else:
        print_for_ds(ds_name, '!!! New boot.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # after work check
    ds_type = extract(ds_type_pattern, i.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, i.send(b'show bof'))
    primary_bof_image_print = i.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(ds_type_pattern, primary_bof_image_print)
    if primary_bof_image_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return
    primary_bof_image_version = extract(sw_version_pattern, primary_bof_image_print)
    if primary_bof_image_version.lower() != TARGET_SW_VERSION.lower():
        print_for_ds(ds_name, 'Primary BOF SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, TARGET_SW_VERSION), io_lock)
    boot_tim_file_print = i.send(b'file version boot.tim')
    boot_tim_type = extract(ds_type_pattern, boot_tim_file_print)
    if boot_tim_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return
    boot_tim_version = extract(sw_version_pattern, boot_tim_file_print)
    if boot_tim_version.lower() != TARGET_SW_VERSION.lower():
        print_for_ds(ds_name, 'boot.tim SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, TARGET_SW_VERSION), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})

    print_for_ds(ds_name, '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=i.ip) + '=' * 15, io_lock)
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
        result = {COMPLETE: list(), FATAL: list(), PERMANENT: ds_list}

        while result[PERMANENT]:
            print "Start running: {0}".format(time.strftime("%H:%m:%s"))
            result_queue, threads = Queue(), list()
            for ds_name in result[PERMANENT]:
                thread = threading.Thread(target=update_ds, name=ds_name, args=(ds_name,
                                                                                user,
                                                                                secret,
                                                                                result_queue,
                                                                                io_lock))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            result = {COMPLETE: list(), FATAL: list(), PERMANENT: list()}

            while not result_queue.empty():
                thread_result = result_queue.get()
                result[thread_result[RESULT]].append(thread_result[NAME])

            if result[COMPLETE]: print "Complete on: " + " ".join(sorted(result[COMPLETE]))
            if result[PERMANENT]: print "Permanent fault on: " + " ".join(sorted(result[PERMANENT]))
            if result[FATAL]: print "Fatal error on: " + " ".join(sorted(result[FATAL]))

            if not result[PERMANENT]: break # finish try loading
            if raw_input("Repeat load on permanent faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

        print "Finish running: {0}".format(time.strftime("%H:%m:%s"))
