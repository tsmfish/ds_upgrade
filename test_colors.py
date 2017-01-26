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

    class STYLE:
        normal    = 0
        bold      = 1
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

    black   = colored.format(style=STYLE.normal, foreground=FOREGROUND.black  , background=BACKGROUND.black)
    red     = colored.format(style=STYLE.normal, foreground=FOREGROUND.red    , background=BACKGROUND.white)
    green   = colored.format(style=STYLE.normal, foreground=FOREGROUND.green  , background=BACKGROUND.white)
    yellow  = colored.format(style=STYLE.normal, foreground=FOREGROUND.yellow , background=BACKGROUND.white)
    blue    = colored.format(style=STYLE.normal, foreground=FOREGROUND.blue   , background=BACKGROUND.white)
    magenta = colored.format(style=STYLE.normal, foreground=FOREGROUND.magenta, background=BACKGROUND.white)
    cyan    = colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan   , background=BACKGROUND.white)
    white   = colored.format(style=STYLE.normal, foreground=FOREGROUND.white  , background=BACKGROUND.white)

    colors = [green, yellow, blue, magenta, cyan, black, red]

    warning = yellow
    fatal = colored.format(style=STYLE.bold, foreground=FOREGROUND.red, background=BACKGROUND.white)
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
