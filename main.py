#!/usr/bin/env python2.6
# -*- coding: utf-8

import getpass
import optparse
import re
from multiprocessing import Lock
from Queue import Queue
from threading import Thread

import time

from DS_Class import DS
from copy_over_scp import scp_copy
from ds_helper import RE, extract, ds_print

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


def update_ds(ds_name, user, password, result_queue, io_lock):
    # Create object
    i = DS(ds_name, user, password)

    # Connect and get basic inform
    ds_print(ds_name, '\n' + '=' * 15 + ' Start process for \"{ds}\" '.format(ds=i.ip) + '=' * 15 + '\n', io_lock)

    try:
        i.conn()
    except Exception as e:
        ds_print(ds_name, e.message)
        result_queue.put({NAME: ds_name, RESULT: FATAL})
        return

    i.get_base_info()

    # Get all files
    # pds_print(ds_name, i.get_all_files())
    # input()

    # Check prim image
    primary_img = i.check_verion(i.prime_image)
    if primary_img:
        if primary_img[1] == i.hw_ver:
            ds_print(ds_name, '*** Primary image good and has version {0}'.format(primary_img[0]), io_lock)
            ds_print(ds_name, '*** ' + i.prime_image, io_lock)
        else:
            ds_print(ds_name, '!!!! Problem with primary image', io_lock)
            ds_print(ds_name, '*** ' + i.prime_image, io_lock)


    # Write primary image to secondary in bof
    ds_print(ds_name, '*** Write primary-image to secondary in bof file', io_lock)
    cmd = 'bof secondary-image {0}'.format(i.prime_image)
    ds_print(ds_name, '*** #{0}'.format(cmd), io_lock)
    ds_print(ds_name, i.send(cmd), io_lock)
    # ds_print(ds_name, i.send('show bof'))

    # Find old soft
    ds_print(ds_name, '*** Finding all sw in cf1:/...', io_lock)
    old_boots = i.find_files('boot.tim')
    try:
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        ds_print(ds_name, '**! cf1:/boot.tim Not exist!', io_lock)

    old_both = i.find_files('both.tim')
    old_both.remove(i.prime_image.replace('\\', '/'))


    # Remove old SW
    ds_print(ds_name, '*** Removing old SW', io_lock)
    for files in (old_boots, old_both):
        for f in files:
            # For beginning ask user for all deleting in future may be auto
            io_lock.acquire()
            answer = raw_input("*** Delete {0} (y/n)? ".format(f))
            io_lock.release()
            if answer.lower() == 'y':
                cmd = 'file delete {0} force'.format(f)
                ds_print(ds_name, '*** ' + i.send(cmd), io_lock)

    # Delete empty folders
    emt_folders = i.find_empty_folders()
    if emt_folders:
        ds_print(ds_name, '*** Deleting empty folders {0}'.format(','.join(emt_folders)), io_lock)
        for folder in emt_folders:
            cmd = 'file rd {0} force'.format(folder)
            ds_print(ds_name, i.send(cmd), io_lock)

    # Check free space
    mb = i.free_space()
    ds_print(ds_name, '*** Free {mb}MB on {ip}'.format(mb=mb, ip=i.ip), io_lock)
    if mb < 62:
        ds_print(ds_name, '!!! Not enough space for continue', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Make image folder
    ds_print(ds_name, '*** Try to create directory \"images\"', io_lock)
    ds_print(ds_name, '*** #file md cf1:\{0}'.format(folder_for_SW), io_lock)
    i.send('file md cf1:\images')
    i.send('file md cf1:\{0}'.format(folder_for_SW))


    # Copy new sw to ds
    ds_print(ds_name, '*** Start coping new sw...', io_lock)
    try:
        scp_copy(i.ip, i.user, i.password, new_SW[i.hw_ver], folder_for_SW)
    except Exception as e:
        ds_print(ds_name, e)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Check free space
    mb = i.free_space()
    ds_print(ds_name, '*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=i.ip), io_lock)

    # Check new SW and write to bof.cfg
    ds_print(ds_name, '*** Write new SW to primary-image')
    if i.check_verion(new_primary_img)[1] == i.hw_ver:
        cmd = 'bof primary-image {0}'.format(new_primary_img).replace('/', '\\')
        ds_print(ds_name, '*** #{0}'.format(cmd), io_lock)
        ds_print(ds_name, i.send(cmd), io_lock)
        # ds_print(ds_name, i.send('show bof'))
    else:
        ds_print(ds_name, '!!! New both.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # Save bof and config
    ds_print(ds_name, '*** Save new bof and config', io_lock)
    i.save_configs()


    # Change boot.tim in root directory
    ds_print(ds_name, '*** Change file cf1:/boot.tim to new ({0})'.format(new_boot_file), io_lock)

    if i.check_verion(new_boot_file)[1] == i.hw_ver:
        # remove read only attribute
        ds_print(ds_name, i.send('file attrib -r cf1:/boot.tim'), io_lock)
        cmd = 'file copy {0} cf1:/boot.tim force'.format(new_boot_file)
        ds_print(ds_name, '*** #{0}'.format(cmd), io_lock)
        # ds_print(ds_name, i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5))
        i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
    else:
        ds_print(ds_name, '!!! New boot.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return

    # after work check
    ds_type = extract(RE.DS_TYPE, i.send(b'show version'))
    primary_bof_image = extract(RE.PRIMARY_BOF_IMAGE, i.send(b'show bof'))
    primary_bof_image_print = i.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(RE.DS_TYPE, primary_bof_image_print)
    if primary_bof_image_type.lower() != ds_type.lower():
        ds_print(ds_name, 'Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return
    primary_bof_image_version = extract(RE.SW_VERSION, primary_bof_image_print)
    if primary_bof_image_version.lower() != TARGET_SW_VERSION.lower():
        ds_print(ds_name, 'Primary BOF SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, TARGET_SW_VERSION), io_lock)
    boot_tim_file_print = i.send(b'file version boot.tim')
    boot_tim_type = extract(RE.DS_TYPE, boot_tim_file_print)
    if boot_tim_type.lower() != ds_type.lower():
        ds_print(ds_name, 'boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})
        return
    boot_tim_version = extract(RE.SW_VERSION, boot_tim_file_print)
    if boot_tim_version.lower() != TARGET_SW_VERSION.lower():
        ds_print(ds_name, 'boot.tim SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, TARGET_SW_VERSION), io_lock)
        result_queue.put({NAME: ds_name, RESULT: PERMANENT})

    ds_print(ds_name, '\n' + '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=i.ip) + '=' * 15 + '\n', io_lock)
    result_queue.put({NAME: ds_name, RESULT: COMPLETE})

if __name__ == "__main__":
    parser = optparse.OptionParser(description='Get config from DS\'s and move them to 1.140',
                                   usage="usage: %prog [file with ds list]")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with list DS", metavar="FILE")
    # parser.add_option( help='Path to file with list of ds', required=True)

    (options, args) = parser.parse_args()
    if not options.ds_list_file_name or not args:
        parser.error("Use [-f <ds list file> | ds ds ds ...]")

    ds_list = args
    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines():
                    ds_list.append(extract(RE.DS_NAME, line))
        except IOError as e:
            print "Error while open file: {file}".format(file=options.ds_list_file_name)
            print e

    if len(ds_list) < 1:
        print "No ds found in arguments."
        exit()

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    print "Start running: {time}".format(time.strftime("%H:%m:%s"))

    if len(ds_list) == 1:
        update_ds(ds_list[0], user, secret, Queue, None)
    else:
        result = {COMPLETE: list(), FATAL: list(), PERMANENT: ds_list}
        io_lock = Lock()

        while result[PERMANENT]:

            result_queue, threads = Queue(), list()
            for ds_name in result[PERMANENT]:
                thread = Thread(target=update_ds, name=ds_name, args=(ds_name, user, secret, result_queue, io_lock))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            result = {COMPLETE: list(), FATAL: list(), PERMANENT: list()}

            for thread_result in result_queue:
                result[thread_result[RESULT]].append(thread_result[NAME])

            if result[COMPLETE]: print "Complete on: " + " ".join(result[COMPLETE])
            if result[PERMANENT]: print "Permanent fault on: " + " ".join(result[PERMANENT])
            if result[FATAL]: print "Fatal error on: " + " ".join(result[FATAL])

            if not result[PERMANENT]: break # finish try loading
            if raw_input("Repeat load on permanent faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

    print "Finish running: {time}".format(time.strftime("%H:%m:%s"))
