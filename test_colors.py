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


class COLORS:
    end = "\x1b[0m"
    black   = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=30, background=47)
    red     = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=31, background=40)
    green   = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=32, background=40)
    yellow  = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=33, background=40)
    blue    = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=34, background=40)
    magenta = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=35, background=40)
    cyan    = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=36, background=40)
    white   = '\x1b[{style};{foreground};{background}m'.format(style=0, foreground=37, background=40)

    colors = [green, yellow, blue, magenta, cyan, black, ]

    warning = yellow
    fatal = red
    error = red
    ok = green
    info = blue


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


if __name__ == "__main__":
    print_for_ds('red    ', 'color', color=COLORS.red)
    print_for_ds('green  ', 'color', color=COLORS.green)
    print_for_ds('yellow ', 'color', color=COLORS.yellow)
    print_for_ds('blue   ', 'color', color=COLORS.blue)
    print_for_ds('magenta', 'color', color=COLORS.magenta)
    print_for_ds('cyan   ', 'color', color=COLORS.cyan)
    print_for_ds('white  ', 'color', color=COLORS.white)
    print_for_ds('black  ', 'color', color=COLORS.black)

    for i in range(len(COLORS.colors)):
        print COLORS.colors[i] + 'COLOR' + COLORS.end

    print_for_ds('warning', 'color', color=COLORS.warning)
    print_for_ds('fatal  ', 'color', color=COLORS.fatal)
    print_for_ds('error  ', 'color', color=COLORS.error)
    print_for_ds('ok     ', 'color', color=COLORS.ok)
    print_for_ds('info   ', 'color', color=COLORS.info)
