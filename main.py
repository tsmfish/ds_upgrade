#!/usr/bin/env python2.6
# -*- coding: utf-8
import base64
import getpass
import optparse
import random
import re
import threading
import time
from Queue import Queue

from DS_Class import DS, ExceptionWrongPassword, ExceptionHostUnreachable
from copy_over_scp import scp_copy
from ds_helper import COLORS, ds_print, print_message_format, extract, is_contains, ds_compare, utilise_progress


log_file_format = "%y%m%d_%H%M%S_{ds_name}.log"

SW_R9 = 'TiMOS-B-7.0.R9'
SW_R13 = 'TiMOS-B-7.0.R13'

target_sw = SW_R9  # it is default value, it can be overwrite by using script options --R9 or --R13

BOF, BOOT, folder_on_ds, boot_file, bof_file, source_folder = 'bof', 'boot', 'folder on ds', 'boot.tim', 'both.tim', 'source folder'
dsType, sasX, sasM = 'type', 'SAS-X', 'SAS-M'

sw = {
    SW_R9: {
        BOF: 'TiMOS-B-7.0.R9',
        BOOT: 'TiMOS-L-7.0.R9',
        folder_on_ds: 'images/TiMOS-7.0.R9',
        boot_file: 'cf1:/images/TiMOS-7.0.R9/boot.tim',
        bof_file: 'cf1:/images/TiMOS-7.0.R9/both.tim',
        sasX: {
            source_folder: '/home/mpls/soft/7210-SAS-X-TiMOS-7.0.R9/',
            boot_file: '8426112',
            bof_file: '44325568'
        },
        sasM: {
            source_folder: '/home/mpls/soft/7210-SAS-M-TiMOS-7.0.R9/',
            boot_file: '7490464',
            bof_file: '43352608'
        }
    },

    SW_R13: {
        BOF: 'TiMOS-B-7.0.R13',
        BOOT: 'TiMOS-L-7.0.R13',
        folder_on_ds: 'images/TiMOS-7.0.R13',
        boot_file: 'cf1:/images/TiMOS-7.0.R13/boot.tim',
        bof_file: 'cf1:/images/TiMOS-7.0.R13/both.tim',
        sasX: {
            source_folder: '/home/mpls/soft/7210-SAS-X-TiMOS-7.0.R13/',
            boot_file: '8430496',
            bof_file: '44336672'
        },
        sasM: {
            source_folder: '/home/mpls/soft/7210-SAS-M-TiMOS-7.0.R13/',
            boot_file: '7486880',
            bof_file: '43364928'
        },
    }
}

free_space_limit = 56   # in Mbytes
random_wait_time = 5    # in seconds

COMPLETE, FATAL, TEMPORARY = 'complete', 'fatal', 'temporary'
NAME, RESULT = 'name', 'result'

ds_name_pattern = re.compile(r'ds\d+?-[0-9a-z]+\b', re.IGNORECASE)
ds_type_pattern = re.compile(r'\bSAS-[XM]\b', re.IGNORECASE)
file_size_pattern = re.compile(r'\b\d{2}\/\d{2}\/\d{4}\s+?\d{2}:\d{2}[ap]\s+?(\d+?)\s+?')
sw_version_pattern = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', re.IGNORECASE)
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)
comment_line_pattern = re.compile(r'^[#/]\S', re.DOTALL|re.MULTILINE)

RETRY_CONNECTION_LIMIT = 7
FAIL_CONNECTION_WAIT_INTERVALS = [3,5,9,17,29,37,47,51]


def post_result(result, queu=None, log_file_name=None):
    if queu:
        queu.put(result)
    if log_file_name:
        try:
            with open(log_file_name, 'a') as log_file:
                log_file.write("[{0}] : ***** result: {1} *****\n"
                               .format(result[NAME],
                                       result[RESULT].upper()))
                log_file.close()
        except IOError:
            pass


def update_ds(ds_name,
              user,
              password,
              result_queue=Queue(),
              io_lock=None,
              force_delete=False,
              log_to_file=False,
              color=None,
              no_progress=False):

    if io_lock: time.sleep(random_wait_time * random.random())
    if log_to_file:
        log_file_name = time.strftime(log_file_format.format(ds_name=ds_name))
    else:
        log_file_name = None

    # Create object
    node = DS(ds_name, user, password)

    # Connect and get basic inform
    ds_print(ds_name,
             '=' * 8 + ' Start process for {ds} '.format(ds=node.ip) + '=' * 8,
             io_lock,
             log_file_name,
             color)
    for tray in range(RETRY_CONNECTION_LIMIT):
        try:
            node.conn()
            break
        #except ExceptionWrongPassword:
        #    ds_print(ds_name, 'Wrong password', io_lock, log_file_name, color, COLORS.error)
        #    post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
        #    return
        except ExceptionHostUnreachable:
            ds_print(ds_name, 'Cannot connect!', io_lock, log_file_name, color, COLORS.error)
            post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
            return
        except :
            if tray != RETRY_CONNECTION_LIMIT - 1:
                ds_print(ds_name, 'Cannot connect! Try reconnect...', io_lock, log_file_name, color)
            else:
                ds_print(ds_name, 'Cannot connect!', io_lock, log_file_name, color, COLORS.error)
                post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
                return
        time.sleep(FAIL_CONNECTION_WAIT_INTERVALS[tray])

    node.get_base_info()

    # Check node SW version
    if node.sw_ver.lower() == sw[target_sw][BOF].lower():
        ds_print(ds_name,
                 "*** Running SW version already \"{0}\"".format(node.sw_ver),
                 io_lock,
                 log_file_name,
                 color,
                 COLORS.info)
        post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)
        return

    # Check primary image
    primary_img = node.check_version(node.prime_image)
    if primary_img:
        if primary_img[1] == node.hw_ver:
            ds_print(ds_name,
                     '*** Primary image good and has version {0}'.format(primary_img[0]),
                     io_lock,
                     log_file_name,
                     color)
            ds_print(ds_name, '*** ' + node.prime_image, io_lock, log_file_name, color)
        else:
            ds_print(ds_name, '!!! Problem with primary image', io_lock, log_file_name, color, COLORS.error)
            ds_print(ds_name, '**! ' + node.prime_image, io_lock, log_file_name, color)
            post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
            return

        if primary_img[0] != node.sw_ver:
            ds_print(ds_name,
                     '!!! Version of the bof primary-image is {0} current running {1}.'
                     .format(primary_img[0], node.sw_ver),
                     io_lock,
                     log_file_name,
                     color,
                     COLORS.error)
            ds_print(ds_name,
                     '!!! May be this switch already prepare for update!',
                     io_lock,
                     log_file_name,
                     color)

            # check file sizes
            ds_type = extract(ds_type_pattern, node.send(b'show version'))
            primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
            primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
            if primary_bof_image_size != sw[target_sw][ds_type.upper()][bof_file]:
                ds_print(ds_name,
                         '**! {0} file has size {1} and this is - WRONG!'
                         .format(primary_bof_image, primary_bof_image_size),
                         io_lock,
                         log_file_name,
                         color,
                         COLORS.error)
            else:
                ds_print(ds_name,
                         '*** {0} file has correct size.'
                         .format(primary_bof_image, primary_bof_image_size),
                         io_lock,
                         log_file_name,
                         color)

            boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
            if boot_tim_file_size != sw[target_sw][ds_type.upper()][boot_file]:
                ds_print(ds_name,
                         '**! {0} file has size {1} and this is - WRONG!'
                         .format('boot.tim', boot_tim_file_size),
                         io_lock,
                         log_file_name,
                         color,
                         COLORS.error)
            else:
                ds_print(ds_name,
                         '*** {0} file has correct size.'
                         .format('boot.tim', boot_tim_file_size),
                         io_lock,
                         log_file_name,
                         color)

            post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)
            return

    # Write primary image to secondary in bof
    ds_print(ds_name, '*** Write primary-image to secondary in bof file', io_lock, log_file_name, color)
    cmd = 'bof secondary-image {0}'.format(node.prime_image)
    ds_print(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
    node.send(cmd)

    # Find old soft
    ds_print(ds_name, '*** Finding all sw in cf1:/...', io_lock, log_file_name, color)
    old_boots = node.find_files('boot.tim')

    try:
        # remove from delete list file cf1:/boot.tim
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        ds_print(ds_name, '**! cf1:/boot.tim Not exist!', io_lock, log_file_name, color)

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
            ds_print(ds_name,
                     '**! ' + node.prime_image.replace('\\', '/') +"both.tim+" +' Not exist!',
                     io_lock,
                     log_file_name,
                     color)

    # Remove old SW
    ds_print(ds_name, '*** Removing old, not used SW', io_lock, log_file_name, color)
    for files in (old_boots, old_both):
        for f in files:
            if not force_delete:
                # For beginning ask user for deleting
                if io_lock: io_lock.acquire()
                try:
                    if color:
                        answer = raw_input(color+print_message_format.format(ds_name, "*** Delete {0} (y/n)? ".format(f))+COLORS.end)
                    else:
                        answer = raw_input(print_message_format.format(ds_name, "*** Delete {0} (y/n)? ".format(f)))
                except :
                    answer = 'n'
                if io_lock: io_lock.release()
            if force_delete or answer.lower() == 'y':
                command_send_result = node.send('file delete {0} force'.format(f)).replace('\n', '')
                ds_print(ds_name, '*** ' + command_send_result, io_lock, log_file_name, color)

    # Delete empty folders
    emt_folders = node.find_empty_folders()
    if emt_folders:
        ds_print(ds_name,
                 '*** Deleting empty folders {0}'.format(','.join(emt_folders)),
                 io_lock,
                 log_file_name,
                 color)
        for folder in emt_folders:
            command_send_result = node.send('file rd {0} force'.format(folder))
            if command_send_result:
                ds_print(ds_name, "*** " + command_send_result, io_lock, log_file_name, color)

    # Check free space
    mb = node.free_space()
    ds_print(ds_name, '*** Free {mb}MB on {ip}'.format(mb=mb, ip=node.ip), io_lock, log_file_name, color)
    if mb < free_space_limit:
        ds_print(ds_name, '!!! Not enough space for continue', io_lock, log_file_name, color, COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Make image folder
    ds_print(ds_name, '*** Try to create directory \"images\"', io_lock, log_file_name, color)
    ds_print(ds_name, '*** #file md cf1:\{0}'.format(sw[target_sw][folder_on_ds]), io_lock, log_file_name, color)
    node.send('file md cf1:\images')
    node.send('file md cf1:\{0}'.format(sw[target_sw][folder_on_ds]))

    # Copy new sw to ds
    ds_print(ds_name, '*** Start coping new sw at {0}...'.format(time.strftime("%H:%M:%S")), io_lock, log_file_name, color)
    try:
        node.net_connect.clear_buffer()
        time.sleep(1)
        if no_progress:
            scp_copy(node.ip,
                     node.user,
                     node.password,
                     sw[target_sw][node.hw_ver.upper()][source_folder],
                     sw[target_sw][folder_on_ds],
                     io_lock,
                     None)
        else:
            scp_copy(node.ip,
                     node.user,
                     node.password,
                     sw[target_sw][node.hw_ver.upper()][source_folder],
                     sw[target_sw][folder_on_ds],
                     io_lock,
                     lambda string,copied,total: ds_print("ds in",
                                                          "transfer file",
                                                          io_lock,
                                                          None,
                                                          color,
                                                          None,
                                                          True))
    except Exception as e:
        ds_print(ds_name, str(e), io_lock, log_file_name, color, COLORS.error)
        ds_print(ds_name,
                 "!*! Try copy manual: scp {0}* {1}:cf1:/{2}/".format(sw[target_sw][node.hw_ver.upper()][source_folder], ds_name, sw[target_sw][folder_on_ds]),
                 io_lock,
                 log_file_name,
                 color, COLORS.info)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Check free space
    mb = node.free_space()
    ds_print(ds_name,
             '*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=node.ip),
             io_lock,
             log_file_name,
             color)

    # Check new SW and write to bof.cfg
    ds_print(ds_name, '*** Write new SW to primary-image', io_lock, log_file_name, color)
    if node.check_version(sw[target_sw][bof_file])[1].lower() == node.hw_ver.lower():
        cmd = 'bof primary-image {0}'.format(sw[target_sw][bof_file]).replace('/', '\\')
        ds_print(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
        node.send(cmd)
    else:
        ds_print(ds_name, '!!! New both.tim not from this platform', io_lock, log_file_name, color, COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Save bof and config
    ds_print(ds_name, '*** Save new bof and config', io_lock, log_file_name, color)
    node.save_configs()

    # Change boot.tim in root directory
    ds_print(ds_name,
             '*** Change file cf1:/boot.tim to new ({0})'.format(sw[target_sw][boot_file]),
             io_lock,
             log_file_name,
             color)

    if node.check_version(sw[target_sw][boot_file])[1].lower() == node.hw_ver.lower():
        # remove read only attribute
        node.send('file attrib -r cf1:/boot.tim')
        cmd = 'file copy {0} cf1:/boot.tim force'.format(sw[target_sw][boot_file])
        ds_print(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
        node.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
    else:
        ds_print(ds_name, '!!! New boot.tim not from this platform', io_lock, log_file_name, color, COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # after work check
    ds_type = extract(ds_type_pattern, node.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
    primary_bof_image_print = node.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(ds_type_pattern, primary_bof_image_print)
    if primary_bof_image_type.lower() != ds_type.lower():
        ds_print(ds_name,
                 '!!! Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                 .format(primary_bof_image_type, ds_type),
                 io_lock,
                 log_file_name,
                 color,
                 COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    primary_bof_image_version = extract(sw_version_pattern, primary_bof_image_print)
    if primary_bof_image_version.lower() != sw[target_sw][BOF].lower():
        ds_print(ds_name,
                     '**! Primary BOF SW version: {0}, target script SW version: {1}'
                 .format(primary_bof_image_version, sw[target_sw][BOF]),
                 io_lock,
                 log_file_name,
                 color)

    boot_tim_file_print = node.send(b'file version boot.tim')
    boot_tim_type = extract(ds_type_pattern, boot_tim_file_print)
    if boot_tim_type.lower() != ds_type.lower():
        ds_print(ds_name,
                     '!!! boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                 .format(boot_tim_type, ds_type),
                 io_lock,
                 log_file_name,
                 color,
                 COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    boot_tim_version = extract(sw_version_pattern, boot_tim_file_print)
    if boot_tim_version.lower() != sw[target_sw][BOOT].lower():
        ds_print(ds_name,
                 '**! boot.tim SW version: {0}, target script SW version: {1}'
                 .format(boot_tim_version, sw[target_sw][BOOT]),
                 io_lock,
                 log_file_name,
                 color)

    # check file sizes
    primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
    if primary_bof_image_size != sw[target_sw][ds_type.upper()][bof_file]:
        ds_print(ds_name,
                 '**! {0} file has size {1} and this is - WRONG!'
                 .format(primary_bof_image, primary_bof_image_size),
                 io_lock,
                 log_file_name,
                 color,
                 COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
    if boot_tim_file_size != sw[target_sw][ds_type.upper()][boot_file]:
        ds_print(ds_name,
                 '**! {0} file has size {1} and this is - WRONG!'
                 .format('boot.tim', boot_tim_file_size),
                 io_lock,
                 log_file_name,
                 color,
                 COLORS.error)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    ds_print(ds_name,
             '=' * 8 + ' Finish process for {ds} '.format(ds=node.ip) + '=' * 8,
             io_lock,
             log_file_name,
             color,
             COLORS.ok)
    post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Prepare DS upgrade SW to \"{0}\" version.'.format(target_sw),
                                   usage="usage: %prog [options] [-f <DS list file> | ds ds ds ...]",
                                   version="1.1.196")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with DS list, line started with # or / will be dropped", metavar="FILE")
    parser.add_option("-y", "--yes", dest="force_delete",
                      help="force remove unused SW images (both/boot)",
                      action="store_true", default=False)
    parser.add_option("-n", "--no-thread", dest="no_threads",
                      help="execute nodes one by one sequentially",
                      action="store_true", default=False)
    parser.add_option("-l", "--log-to-file", dest="log_to_file",
                      help="enable logging to file {0}".format(log_file_format),
                      action="store_true", default=False)
    parser.add_option("-c", "--color", dest="colorize",
                      help="Colorize output",
                      action="store_true", default=False)
    parser.add_option("--pw", "--password", dest="secret",
                      help="encoded password",
                      type="string", default="")
    parser.add_option("--r9", "--R9", dest="r9",
                      help="load SW {0}".format(SW_R9), default=False,
                      action="store_true")
    parser.add_option("--r13", "--R13", dest="r13",
                      help="load SW {0}".format(SW_R13), default=False,
                      action="store_true")
    parser.add_option("--np", "--no-progress", dest="no_progress",
                      help="disable show progress", default=False,
                      action="store_true")

    (options, args) = parser.parse_args()

    if options.r9 and options.r13:
        parser.error("options --R9 and --R13 are mutually exclusive")

    if options.r9:
        target_sw = SW_R9
    if options.r13:
        target_sw = SW_R13

    ds_list_raw = list(extract(ds_name_pattern, ds) for ds in args if extract(ds_name_pattern, ds))

    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines():
                    if not is_contains(comment_line_pattern, line) and extract(ds_name_pattern, line):
                        ds_list_raw.append(extract(ds_name_pattern, line))
        except IOError as e:
            print COLORS.error+"Error while open file: {file}".format(file=options.ds_list_file_name)+COLORS.end
            print COLORS.error+str(e)+COLORS.end

    ds_list = list()
    for ds in ds_list_raw:
        if ds not in ds_list: ds_list.append(ds)

    if not ds_list:
        parser.print_help()
        exit()

    if len(ds_list) < 1:
        print COLORS.error+"No ds found in arguments."+COLORS.end
        exit()

    user = getpass.getuser()
    if options.secret:
        secret = base64.b64decode(options.secret).encode("ascii")
    else:
        secret = getpass.getpass('Password for DS:')

    print COLORS.info+"Load SW: {0}".format(COLORS.warning+target_sw+COLORS.info)+COLORS.end
    print COLORS.info+"Start running: {0}".format(time.strftime("%H:%M:%S"))+COLORS.end
    start_time = time.time()

    io_lock = threading.Lock()
    result = {COMPLETE: list(), FATAL: list(), TEMPORARY: ds_list}
    colorIndex = 0
    ds_colors = {}

    while result[TEMPORARY]:

        result_queue, threads = Queue(), list()
        random_wait_time = len(result[TEMPORARY]) + 1

        if options.no_threads or len(result[TEMPORARY]) == 1:
            handled_ds_count = 0
            start_tour_time = time.time()

            for ds_name in result[TEMPORARY]:
                if ds_name not in ds_colors:
                    ds_colors[ds_name] = None
                try:
                    update_ds(ds_name,
                              user,
                              secret,
                              result_queue=result_queue,
                              force_delete=options.force_delete,
                              log_to_file=options.log_to_file,
                              color=ds_colors[ds_name],
                              no_progress=options.no_progress)
                    utilise_progress()
                except Exception as e:
                    utilise_progress()
                    ds_print(ds_name, "**! Unhandled exception " + str(e), ds_colors[ds_name], COLORS.error)
                    result_queue.put({RESULT: FATAL, NAME: ds_name})
                current_time = time.time()
                handled_ds_count += 1
                print '\n' + COLORS.info +\
                      '=' * 8 + \
                      ' total: {0}\t complete: {1}\t remaining: {2} '.format(len(result[TEMPORARY]),
                                                                             handled_ds_count,
                                                                             len(result[TEMPORARY])-handled_ds_count) + \
                      '=' * 8
                print '=' * 4 + \
                      ' time elapsed: {0}\t time remaining: {1} '.format(time.strftime('%H:%M:%S',
                                                                                       time.gmtime(current_time - start_time)),
                                                                         time.strftime('%H:%M:%S',
                                                                                       time.gmtime((current_time-start_tour_time)/handled_ds_count*(len(result[TEMPORARY])-handled_ds_count)))) + \
                      '=' * 4 + \
                      '\n' + COLORS.end
        else:
            for ds_name in result[TEMPORARY]:
                if ds_name not in ds_colors:
                    if options.colorize:
                        ds_colors[ds_name] = COLORS.colors[colorIndex]
                        colorIndex = (colorIndex + 1) % len(COLORS.colors)
                    else:
                        ds_colors[ds_name] = None

                thread = threading.Thread(target=update_ds, name=ds_name, args=(ds_name,
                                                                                user,
                                                                                secret,
                                                                                result_queue,
                                                                                io_lock,
                                                                                options.force_delete,
                                                                                options.log_to_file,
                                                                                ds_colors[ds_name],
                                                                                options.no_progress))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()
            utilise_progress()

        result[TEMPORARY] = list()

        while not result_queue.empty():
            thread_result = result_queue.get()
            result[thread_result[RESULT]].append(thread_result[NAME])

        # determinate ds with unhandled error and mark it as FATAL
        unhandled_ds = list()
        for ds_name in ds_list:
            if ds_name not in result[COMPLETE] and \
                            ds_name not in result[TEMPORARY] and \
                            ds_name not in result[FATAL]:
                unhandled_ds.append(ds_name)

        for ds_name in unhandled_ds:
            result[FATAL].append(ds_name)
            if options.log_to_file:
                post_result({NAME: ds_name, RESULT: FATAL},
                            None,
                            time.strftime(log_file_format.format(ds_name=ds_name)))

        if options.colorize and not options.no_threads:
            line_complete, line_temporary, line_fatal = COLORS.end, COLORS.end, COLORS.end
        else:
            line_complete, line_temporary, line_fatal = '', '', ''

        for ds in sorted(result[COMPLETE], ds_compare):
            if options.colorize and not options.no_threads:
                line_complete += ds_colors[ds] + ds + COLORS.end + " "
            else:
                line_complete += ds + " "
        for ds in sorted(result[TEMPORARY], ds_compare):
            if options.colorize and not options.no_threads:
                line_temporary += ds_colors[ds] + ds + COLORS.end + " "
            else:
                line_temporary += ds + " "
        for ds in sorted(result[FATAL], ds_compare):
            if options.colorize and not options.no_threads:
                line_fatal += ds_colors[ds] + ds + COLORS.end + " "
            else:
                line_fatal += ds + " "

        if result[COMPLETE]:  print    COLORS.ok + "\nComplete on       : " + line_complete + COLORS.end
        if result[TEMPORARY]: print COLORS.warning + "Temporary fault on: " + line_temporary + COLORS.end
        if result[FATAL]:     print   COLORS.fatal + "Fatal error on    : " + line_fatal + COLORS.end

        if not result[TEMPORARY]: break  # finish try loading
        answer = ''
        while answer not in ["Y", "N"]:
            answer = raw_input("\nRepeat load on temporary faulty nodes (Y-yes): ").strip().upper()
        if answer != "Y": break
        print

    print COLORS.info + "\nFinish running: {0}".format(time.strftime("%H:%M:%S"))
    print 'Time lapsed: {0}'.format(time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))) + COLORS.end
