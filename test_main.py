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


class COLORS:

    class STYLE:
        normal    = 0
        highlight = 1
        underline = 4
        blink     = 5
        negative  = 7

    class FOREGROUND:
        black   = 30
        red     = 31
        green   = 32
        yellow  = 33
        blue    = 34
        magenta = 35
        cyan    = 36
        white   = 37

    class BACKGROUND:
        black   = 40
        red     = 41
        green   = 42
        yellow  = 43
        blue    = 44
        magenta = 45
        cyan    = 46
        white   = 47

    end = "\x1b[0m"
    colored = '\x1b[{style};{foreground};{background}m'

    black   = colored.format(style=STYLE.normal, foreground=FOREGROUND.black  , background=BACKGROUND.white)
    red     = colored.format(style=STYLE.normal, foreground=FOREGROUND.red    , background=BACKGROUND.black)
    green   = colored.format(style=STYLE.normal, foreground=FOREGROUND.green  , background=BACKGROUND.black)
    yellow  = colored.format(style=STYLE.normal, foreground=FOREGROUND.yellow , background=BACKGROUND.black)
    blue    = colored.format(style=STYLE.normal, foreground=FOREGROUND.blue   , background=BACKGROUND.black)
    magenta = colored.format(style=STYLE.normal, foreground=FOREGROUND.magenta, background=BACKGROUND.black)
    cyan    = colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan   , background=BACKGROUND.black)
    white   = colored.format(style=STYLE.normal, foreground=FOREGROUND.white  , background=BACKGROUND.black)

    colors = [white, green, yellow, blue, magenta, cyan, black]

    warning = yellow
    fatal = colored.format(style=STYLE.highlight, foreground=FOREGROUND.red, background=BACKGROUND.black)
    error = red
    ok = green
    info = cyan


def print_for_ds(host, message, io_lock=None, log_file_name=None, color=COLORS.white):
    if io_lock: io_lock.acquire()
    print color+"[{0}] : {1}".format(host, message)+COLORS.end
    if io_lock: io_lock.release()
    if log_file_name:
        try:
            with open(log_file_name, 'a') as log_file:
                log_file.write("[{0}] : {1}\n".format(host, message))
                log_file.close()
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
              color=COLORS.white):

    if io_lock: time.sleep(random_wait_time * random.random())
    if log_to_file:
        log_file_name = time.strftime(log_file_format.format(ds_name=ds_name))
    else:
        log_file_name = None

    # Create object
    node = DS(ds_name, user, password)

    # Connect and get basic inform
    print_for_ds(ds_name,
                 '=' * 15 + ' Start process for \"{ds}\" '.format(ds=node.ip) + '=' * 15,
                 io_lock,
                 log_file_name)

    try:
        node.conn()
    except Exception:
        print_for_ds(ds_name, 'Cannot connect!', io_lock, log_file_name, COLORS.error)
        post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
        return

    node.get_base_info()

    # Check node SW version
    if node.sw_ver.lower() == target_sw_version.lower():
        print_for_ds(ds_name, "*** Running SW version already \"{0}\"".format(node.sw_ver), io_lock, log_file_name, color)
        post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)
        return

    # Check primary image
    primary_img = node.check_verion(node.prime_image)
    if primary_img:
        if primary_img[1] == node.hw_ver:
            print_for_ds(ds_name,
                         '*** Primary image good and has version {0}'.format(primary_img[0]),
                         io_lock,
                         log_file_name,
                         color)
            print_for_ds(ds_name, '*** ' + node.prime_image, io_lock, log_file_name, color)
        else:
            print_for_ds(ds_name, '!!! Problem with primary image', io_lock, log_file_name, color)
            print_for_ds(ds_name, '**! ' + node.prime_image, io_lock, log_file_name, color)
            post_result({NAME: ds_name, RESULT: FATAL}, result_queue, log_file_name)
            return

        if primary_img[0] != node.sw_ver:
            print_for_ds(ds_name,
                         '!!! Version of the bof primary-image is {0} current running {1}.'
                         .format(primary_img[0], node.sw_ver),
                         io_lock,
                         log_file_name,
                         color)
            print_for_ds(ds_name,
                         '!!! May be this switch already prepare for update!',
                         io_lock,
                         log_file_name,
                         color)

            # check file sizes
            ds_type = extract(ds_type_pattern, node.send(b'show version'))
            primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
            primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
            if primary_bof_image_size != file_sizes[ds_type.upper()]['both.tim']:
                print_for_ds(ds_name,
                             '**! {0} file has size {1} and this is - WRONG!'
                             .format(primary_bof_image, primary_bof_image_size),
                             io_lock,
                             log_file_name,
                             color)
            else:
                print_for_ds(ds_name,
                             '*** {0} file has correct size.'
                             .format(primary_bof_image, primary_bof_image_size),
                             io_lock,
                             log_file_name,
                             color)

            boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
            if boot_tim_file_size != file_sizes[ds_type.upper()]['boot.tim']:
                print_for_ds(ds_name,
                             '**! {0} file has size {1} and this is - WRONG!'
                             .format('boot.tim', boot_tim_file_size),
                             io_lock,
                             log_file_name,
                             color)
            else:
                print_for_ds(ds_name,
                             '*** {0} file has correct size.'
                             .format('boot.tim', boot_tim_file_size),
                             io_lock,
                             log_file_name,
                             color)

            post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)
            return

    # Write primary image to secondary in bof
    print_for_ds(ds_name, '*** Write primary-image to secondary in bof file', io_lock, log_file_name, color)
    cmd = 'bof secondary-image {0}'.format(node.prime_image)
    print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
    print_for_ds(ds_name, '*** {0}'.format(node.send(cmd)), io_lock, log_file_name, color)

    # Find old soft
    print_for_ds(ds_name, '*** Finding all sw in cf1:/...', io_lock, log_file_name, color)
    old_boots = node.find_files('boot.tim')

    try:
        # remove from delete list file cf1:/boot.tim
        old_boots.remove('cf1:/boot.tim')
    except ValueError:
        print_for_ds(ds_name, '**! cf1:/boot.tim Not exist!', io_lock, log_file_name, color)

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
            print_for_ds(ds_name,
                         '**! '+node.prime_image.replace('\\', '/')+"both.tim+"+' Not exist!',
                         io_lock,
                         log_file_name,
                         color)

    # Remove old SW
    print_for_ds(ds_name, '*** Removing old, not used SW', io_lock, log_file_name, color)
    for files in (old_boots, old_both):
        for f in files:
            if not force_delete:
                # For beginning ask user for deleting
                if io_lock: io_lock.acquire()
                answer = raw_input("[{0}] : *** Delete {1} (y/n)? ".format(ds_name, f))
                if io_lock: io_lock.release()
            if force_delete or answer.lower() == 'y':
                command_send_result = node.send('file delete {0} force'.format(f))
                print_for_ds(ds_name, '*** ' + command_send_result, io_lock, log_file_name, color)

    # Delete empty folders
    emt_folders = node.find_empty_folders()
    if emt_folders:
        print_for_ds(ds_name,
                     '*** Deleting empty folders {0}'.format(','.join(emt_folders)),
                     io_lock,
                     log_file_name,
                     color)
        for folder in emt_folders:
            command_send_result = node.send('file rd {0} force'.format(folder))
            print_for_ds(ds_name, "*** " + command_send_result, io_lock, log_file_name, color)

    # Check free space
    mb = node.free_space()
    print_for_ds(ds_name, '*** Free {mb}MB on {ip}'.format(mb=mb, ip=node.ip), io_lock, log_file_name, color)
    if mb < free_space_limit:
        print_for_ds(ds_name, '!!! Not enough space for continue', io_lock, log_file_name, color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Make image folder
    print_for_ds(ds_name, '*** Try to create directory \"images\"', io_lock, log_file_name, color)
    print_for_ds(ds_name, '*** #file md cf1:\{0}'.format(folder_for_SW), io_lock, log_file_name, color)
    node.send('file md cf1:\images')
    node.send('file md cf1:\{0}'.format(folder_for_SW))

    # Copy new sw to ds
    print_for_ds(ds_name, '*** Start coping new sw...', io_lock, log_file_name, color)
    try:
        scp_copy(node.ip, node.user, node.password, new_SW[node.hw_ver], folder_for_SW)
    except Exception as e:
        print_for_ds(ds_name, str(e), io_lock, log_file_name, color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Check free space
    mb = node.free_space()
    print_for_ds(ds_name,
                 '*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=node.ip),
                 io_lock,
                 log_file_name,
                 color)

    # Check new SW and write to bof.cfg
    print_for_ds(ds_name, '*** Write new SW to primary-image', io_lock, log_file_name, color)
    if node.check_verion(new_primary_img)[1] == node.hw_ver:
        cmd = 'bof primary-image {0}'.format(new_primary_img).replace('/', '\\')
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
        print_for_ds(ds_name, '*** {0}'.format(node.send(cmd)), io_lock, log_file_name, color)
    else:
        print_for_ds(ds_name, '!!! New both.tim not from this platform', io_lock, log_file_name, color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # Save bof and config
    print_for_ds(ds_name, '*** Save new bof and config', io_lock, log_file_name, color)
    node.save_configs()

    # Change boot.tim in root directory
    print_for_ds(ds_name,
                 '*** Change file cf1:/boot.tim to new ({0})'.format(new_boot_file),
                 io_lock,
                 log_file_name,
                 color)

    if node.check_verion(new_boot_file)[1] == node.hw_ver:
        # remove read only attribute
        command_send_result = node.send('file attrib -r cf1:/boot.tim')
        print_for_ds(ds_name, '*** {0}'.format(command_send_result), io_lock, log_file_name, color)
        cmd = 'file copy {0} cf1:/boot.tim force'.format(new_boot_file)
        print_for_ds(ds_name, '*** #{0}'.format(cmd), io_lock, log_file_name, color)
        node.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
    else:
        print_for_ds(ds_name, '!!! New boot.tim not from this platform', io_lock, log_file_name, color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    # after work check
    ds_type = extract(ds_type_pattern, node.send(b'show version'))
    primary_bof_image = extract(primary_bof_image_pattern, node.send(b'show bof'))
    primary_bof_image_print = node.send(b'file version ' + primary_bof_image)
    primary_bof_image_type = extract(ds_type_pattern, primary_bof_image_print)
    if primary_bof_image_type.lower() != ds_type.lower():
        print_for_ds(ds_name,
                     '!!! Primary BOF type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(primary_bof_image_type, ds_type),
                     io_lock,
                     log_file_name,
                     color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    primary_bof_image_version = extract(sw_version_pattern, primary_bof_image_print)
    if primary_bof_image_version.lower() != target_sw_version.lower():
        print_for_ds(ds_name,
                     '**! Primary BOF SW version: {0}, target script SW version: {1}'
                     .format(primary_bof_image_version, target_sw_version),
                     io_lock,
                     log_file_name,
                     color)

    boot_tim_file_print = node.send(b'file version boot.tim')
    boot_tim_type = extract(ds_type_pattern, boot_tim_file_print)
    if boot_tim_type.lower() != ds_type.lower():
        print_for_ds(ds_name,
                     '!!! boot.tim type: {0}, ds has type: {1}. Configuration INCONSISTENT!!!.'
                     .format(boot_tim_type, ds_type),
                     io_lock,
                     log_file_name,
                     color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    boot_tim_version = extract(sw_version_pattern, boot_tim_file_print)
    if boot_tim_version.lower() != target_sw_boot_version.lower():
        print_for_ds(ds_name,
                     '**! boot.tim SW version: {0}, target script SW version: {1}'
                     .format(boot_tim_version, target_sw_boot_version),
                     io_lock,
                     log_file_name,
                     color)

    # check file sizes
    primary_bof_image_size = extract(file_size_pattern, node.send(b'file dir {0}'.format(primary_bof_image)))
    if primary_bof_image_size != file_sizes[ds_type.upper()]['both.tim']:
        print_for_ds(ds_name,
                     '**! {0} file has size {1} and this is - WRONG!'
                     .format(primary_bof_image, primary_bof_image_size),
                     io_lock,
                     log_file_name,
                     color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    boot_tim_file_size = extract(file_size_pattern, node.send(b'file dir {0}'.format('boot.tim')))
    if boot_tim_file_size != file_sizes[ds_type.upper()]['boot.tim']:
        print_for_ds(ds_name,
                     '**! {0} file has size {1} and this is - WRONG!'
                     .format('boot.tim', boot_tim_file_size),
                     io_lock,
                     log_file_name,
                     color)
        post_result({NAME: ds_name, RESULT: TEMPORARY}, result_queue, log_file_name)
        return

    print_for_ds(ds_name,
                 '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=node.ip) + '=' * 15,
                 io_lock,
                 log_file_name,
                 COLORS.white)
    post_result({NAME: ds_name, RESULT: COMPLETE}, result_queue, log_file_name)


if __name__ == "__main__":
    parser = optparse.OptionParser(description='Prepare DS upgrade SW to \"{0}\" version.'.format(target_sw_version),
                                   usage="usage: %prog [-y] [-n] [-l] [-f <DS list file> | ds ds ds ...]")
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
    args = ['ds1-kha3', 'ds2-kha3', 'ds3-kha3', 'ds4-kha3']

    ds_list_raw = list(extract(ds_name_pattern, ds) for ds in args if extract(ds_name_pattern, ds))

    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines():
                    ds_list_raw.append(extract(ds_name_pattern, line))
        except IOError as e:
            print COLORS.error+"Error while open file: {file}".format(file=options.ds_list_file_name)+COLORS.end
            print COLORS.error+str(e)+COLORS.end

    ds_list = list(set(ds_list_raw))

    if not ds_list:
        parser.print_help()
        exit()

    if len(ds_list) < 1:
        print COLORS.error+"No ds found in arguments."+COLORS.end
        exit()

    user = getpass.getuser()
    secret = getpass.getpass('Password for DS:')

    print COLORS.info+"Start running: {0}".format(time.strftime("%H:%M:%S"))+COLORS.end

    if len(ds_list) == 1:
        update_ds(ds_list[0],
                  user,
                  secret,
                  force_delete=options.force_delete,
                  log_to_file=options.log_to_file)
    else:
        io_lock = threading.Lock()
        result = {COMPLETE: list(), FATAL: list(), TEMPORARY: ds_list}
        colorIndex = 0

        while result[TEMPORARY]:

            result_queue, threads = Queue(), list()

            if options.no_threads:
                result_queue.put({RESULT: COMPLETE, NAME: args[0]})
                result_queue.put({RESULT: TEMPORARY, NAME: args[1]})
                result_queue.put({RESULT: FATAL, NAME: args[2]})

            else:
                result_queue.put({RESULT: COMPLETE, NAME: args[0]})
                result_queue.put({RESULT: TEMPORARY, NAME: args[1]})
                result_queue.put({RESULT: FATAL, NAME: args[2]})

            result = {COMPLETE: list(), FATAL: list(), TEMPORARY: list()}

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

            if result[COMPLETE]:  print '\033[92m'+"\nComplete on       : " + " ".join(sorted(result[COMPLETE]))+'\033[0m'
            if result[TEMPORARY]: print   '\033[93m'+"Temporary fault on: " + " ".join(sorted(result[TEMPORARY]))+'\033[0m'
            if result[FATAL]:     print   '\033[91m'+"Fatal error on    : " + " ".join(sorted(result[FATAL]))+'\033[0m'
            print "\n"

            if not result[TEMPORARY]: break  # finish try loading
            if raw_input("Repeat load on temporary faulty nodes (Y-yes): ").strip().upper() != 'Y':
                break

    print COLORS.info+"Finish running: {0}".format(time.strftime("%H:%M:%S"))+COLORS.end
