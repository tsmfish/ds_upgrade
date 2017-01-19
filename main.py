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


def update_ds(ds_name, user, password, result_queue=Queue(), io_lock=None, force_delete=False):
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

    # Check primary image
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
                             .format('boot.tim', boot_tim_file_size), io_lock)

            result_queue.put({NAME: ds_name, RESULT: COMPLETE})
            return

    # Write primary image to secondary in bof
    print_for_ds(ds_name, '*** Write primary-image to secondary in bof file', io_lock)
    cmd = 'bof secondary-image {0}'.format(node.prime_image)
    print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
    print_for_ds(ds_name, '*** {0}'.format(node.send(cmd)), io_lock)

    # Find old soft
    print_for_ds(ds_name, '*** Finding all sw in cf1:/...', io_lock)
    old_boots = node.find_files('boot.tim')

    try:
        # remove from delete list file cf1:/boot.tim
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        print_for_ds(ds_name, '**! cf1:/boot.tim Not exist!', io_lock)

    try:
        # remove from delete list file <primary image BOF path>/boot.tim
        old_boots.remove(node.prime_image.replace('\\', '/').replace('both.tim', 'boot.tim'))
    except ValueError:
        pass

    old_both = node.find_files('both.tim')
    # remove from delete list file primary image BOF
    try:
        old_both.remove(node.prime_image.replace('\\', '/'))
    except ValueError:
        try:
            old_both.remove(node.prime_image.replace('\\', '/')+"both.tim")
        except ValueError:
            print_for_ds(ds_name, '**! '+node.prime_image.replace('\\', '/')+"both.tim+"+' Not exist!', io_lock)

    # Remove old SW
    print_for_ds(ds_name, '*** Removing old, not used SW', io_lock)
    for files in (old_boots, old_both):
        for f in files:
            if not force_delete:
                # For beginning ask user for deleting
                if io_lock: io_lock.acquire()
                answer = raw_input("[{0}] : *** Delete {1} (y/n)? ".format(ds_name, f))
                if io_lock: io_lock.release()
            if force_delete or answer.lower() == 'y':
                command_send_result = node.send('file delete {0} force'.format(f))
                print_for_ds(ds_name, '*** ' + command_send_result, io_lock)

    # Delete empty folders
    emt_folders = node.find_empty_folders()
    if emt_folders:
        print_for_ds(ds_name, '*** Deleting empty folders {0}'.format(','.join(emt_folders)), io_lock)
        for folder in emt_folders:
            command_send_result = node.send('file rd {0} force'.format(folder))
            print_for_ds(ds_name, "*** " + command_send_result, io_lock)

    # Check free space
    mb = node.free_space()
    print_for_ds(ds_name, '*** Free {mb}MB on {ip}'.format(mb=mb, ip=node.ip), io_lock)
    if mb < free_space_limit:
        print_for_ds(ds_name, '!!! Not enough space for continue', io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    # Make image folder
    print_for_ds(ds_name, '*** Try to create directory \"images\"', io_lock)
    print_for_ds(ds_name, '*** #file md cf1:\{0}'.format(folder_for_SW), io_lock)
    node.send('file md cf1:\images')
    node.send('file md cf1:\{0}'.format(folder_for_SW))

    # Copy new sw to ds
    print_for_ds(ds_name, '*** Start coping new sw...', io_lock)
    try:
        scp_copy(node.ip, node.user, node.password, new_SW[node.hw_ver], folder_for_SW)
    except Exception as e:
        print_for_ds(ds_name, str(e), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    # Check free space
    mb = node.free_space()
    print_for_ds(ds_name, '*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=node.ip), io_lock)

    # Check new SW and write to bof.cfg
    print_for_ds(ds_name, '*** Write new SW to primary-image', io_lock)
    if node.check_verion(new_primary_img)[1] == node.hw_ver:
        cmd = 'bof primary-image {0}'.format(new_primary_img).replace('/', '\\')
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
        print_for_ds(ds_name, '*** {0}'.format(node.send(cmd)), io_lock)
    else:
        print_for_ds(ds_name, '!!! New both.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    # Save bof and config
    print_for_ds(ds_name, '*** Save new bof and config', io_lock)
    node.save_configs()

    # Change boot.tim in root directory
    print_for_ds(ds_name, '*** Change file cf1:/boot.tim to new ({0})'.format(new_boot_file), io_lock)

    if node.check_verion(new_boot_file)[1] == node.hw_ver:
        # remove read only attribute
        command_send_result = node.send('file attrib -r cf1:/boot.tim')
        print_for_ds(ds_name, '*** {0}'.format(command_send_result), io_lock)
        cmd = 'file copy {0} cf1:/boot.tim force'.format(new_boot_file)
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock)
        node.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
    else:
        print_for_ds(ds_name, '!!! New boot.tim not from this platform', io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    # after work check
    ds_type = extract(ds_type_pattern, node.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
    primary_bof_image_print = node.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(ds_type_pattern, primary_bof_image_print)
    if primary_bof_image_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    primary_bof_image_version = extract(sw_version_pattern, primary_bof_image_print)
    if primary_bof_image_version.lower() != target_sw_version.lower():
        print_for_ds(ds_name, 'Primary BOF SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, target_sw_version), io_lock)

    boot_tim_file_print = node.send(b'file version boot.tim')
    boot_tim_type = extract(ds_type_pattern, boot_tim_file_print)
    if boot_tim_type.lower() != ds_type.lower():
        print_for_ds(ds_name, 'boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(boot_tim_type, ds_type), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    boot_tim_version = extract(sw_version_pattern, boot_tim_file_print)
    if boot_tim_version.lower() != target_sw_boot_version.lower():
        print_for_ds(ds_name, 'boot.tim SW version: {0}, target script SW version: {1}'
                     .format(boot_tim_version, target_sw_boot_version), io_lock)
        result_queue.put({NAME: ds_name, RESULT: TEMPORARY})
        return

    # check file sizes
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
                                   usage="usage: %prog [-y] [-f <ds list file> | ds ds ds ...]")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with list DS", metavar="FILE")
    parser.add_option("-y", "--yes", dest="force_delete",
                      help="force remove unused SW images (both/boot)",
                      action="store_true", default=False)

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
        update_ds(ds_list[0], user, secret, force_delete=options.force_delete)
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
                                                                                io_lock,
                                                                                options.force_delete))
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

        print "Finish running: {0}".format(time.strftime("%H:%m"))
