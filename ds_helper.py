#!/usr/bin/env python2.6
# -*- coding: utf-8
import re
import threading


class RE:
    FLAGS = re.IGNORECASE
    FILE_DATE_STRING = r'\b\d\d\/\d\d\/\d\d\d\d\b'
    FILE_TIME_STRING = r'\b\d\d:\d\d[ap]\b'
    FILE_SIZE_PREAMBLE = FILE_DATE_STRING + r'\s+?' + FILE_TIME_STRING + r'\s+?(\d+?)\s+?'
    PRIMARY_BOF_IMAGE = re.compile(r'primary-image\s+?(\S+)\b', FLAGS)
    SECONDARY_BOF_IMAGE = re.compile(r'secondary-image\s+?(\S+)\b', FLAGS)
    FILE_DATE = re.compile(FILE_DATE_STRING)
    FILE_TIME = re.compile(FILE_TIME_STRING)
    DIR_FILE_PREAMBLE = re.compile(FILE_DATE_STRING+r'\s+?'+FILE_TIME_STRING+r'\s+?(?:<DIR>|\d+?)\s+?', FLAGS)
    DS_TYPE = re.compile(r'\bSAS-[XM]\b', FLAGS)
    '''
    TiMOS-B-4.0.R2
    TiMOS-B-5.0.R2
    TiMOS-B-7.0.R9
    TiMOS-B-7.0.R13
    '''
    SW_VERSION = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', FLAGS)
    FREE_SPACE_SIZE = re.compile(r'\b(\d+?)\s+?bytes free\.', FLAGS)
    DS_NAME = re.compile(r'\bds\d-[0-9a-z]+\b', FLAGS)


def extract(regexp, text, flags=re.IGNORECASE):
    """

    :param regexp: regular expression
    :param text: source for extracting
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: first occur regular expression
    """
    try:
        if regexp.__class__.__name__ == 'SRE_Pattern':
            return regexp.findall(text)[0]
        elif regexp.__class__.__name__ == str.__name__:
            return re.findall(regexp, text, flags)[0]
        else:
            return None
    except IndexError as error:
        return None


def is_contains(regexp, text, flags=re.IGNORECASE):
    """

    :param regexp:
    :param text:
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: True if string contains regular expression
    """
    assert(regexp.__class__.__name__ in ['SRE_Pattern', str.__class__.__name__])
    if regexp.__class__.__name__ == 'SRE_Pattern':
        if regexp.search(text):
            return True
        else:
            return False
    if regexp.__class__.__name__ == str.__class__.__name__:
        if re.search(regexp, text, flags):
            return True
        else:
            return False


def ds_print(ds, message, io_lock=None):
    """
    Thread safe printing with DS in start line.

    :param ds:
    :param message:
    :param io_lock: object threading.Lock or threading.RLock
    """
    assert(io_lock and
           io_lock.__class__.__name__ in [threading.Lock().__class__.__name__,
                                          threading.RLock().__class__.__name__])
    if io_lock: io_lock.acquire()
    print "{ds} : {message}".format(ds=ds, message=message)
    if io_lock: io_lock.release()


if __name__ == "__main__":

    sample_text = """A:ds3-kha3# show version
TiMOS-B-7.0.R9 both/mpc ALCATEL SAS-M 7210 Copyright (c) 2000-2015 Alcatel-Lucent.
All rights reserved. All use subject to applicable license agreements.
Built on Thu Oct 15 08:11:18 IST 2015 by builder in /home/builder/7.0B1/R9/panos/main
A:ds3-kha3# shov [1D [1D[1D [1Dwp[1D [1D bof
===============================================================================
BOF (Memory)
===============================================================================
    primary-image      cf1:\images\TiMOS-7.0.R9\both.tim
    secondary-image    cf1:\images\TiMOS-B-4.0.R2\both.tim
    primary-config     cf1:\ds3-kha3.cfg
#eth-mgmt Port Settings:
    no  eth-mgmt-disabled
    eth-mgmt-address   10.50.70.46/24 active
    eth-mgmt-route     10.44.1.219/32 next-hop 10.50.70.1
    eth-mgmt-autoneg
    eth-mgmt-duplex    full
    eth-mgmt-speed     100
#uplinkA Port Settings:
    uplinkA-port       1/1/7
    uplinkA-autoneg
    uplinkA-duplex     full
    uplinkA-speed      1000
    uplinkA-address    0
    uplinkA-vlan       0
#uplinkB Port Settings:
    uplinkB-port       1/1/2
    uplinkB-autoneg
    uplinkB-duplex     full
    uplinkB-speed      1000
    uplinkB-address    0
    uplinkB-vlan       0
#System Settings:
    wait               3
    persist            on
    console-speed      115200
    uplink-mode        network
    use-expansion-card-type   m2-xfp
    no  console-disabled
===============================================================================
A:ds3-kha3# file version cf1:\images\TiMOS-7.0.R9\both.tim
TiMOS-B-7.0.R9 for 7210 SAS-M
Thu Oct 15 08:11:18 IST 2015 by builder in /home/builder/7.0B1/R9/panos/main
A:ds3-kha3# file version boot.tim
TiMOS-L-4.0.R2 for 7210 SAS-M
Mon Oct 31 16:19:31 IST 2011 by builder in /builder/4.0B1/R2/panos/main
A:ds3-kha3# file dit [1D [1D[1D [1Dr boot.tim


Volume in drive cf1 on slot A is /flash.

Volume in drive cf1 on slot A is formatted as FAT16

Directory of cf1:

03/19/2012  12:05p             4235928 boot.tim
               1 File(s)                4235928 bytes.

               0 Dir(s)                27013120 bytes free.

A:ds3-kha3# g[1D [1Dfile dir cf1:\images\TiMOS-7.0.R9\both.tim


Volume in drive cf1 on slot A is /flash.

Volume in drive cf1 on slot A is formatted as FAT16

Directory of cf1:\images\TiMOS-7.0.R9

01/21/2001  01:51p            43352608 both.tim
               1 File(s)               43352608 bytes.

               0 Dir(s)                27013120 bytes free.


A:ds3-kha3# logout"""
    print RE.DS_NAME.findall(sample_text)
    print RE.DS_TYPE.findall(sample_text)
    print RE.PRIMARY_BOF_IMAGE.findall(sample_text)
    print RE.SECONDARY_BOF_IMAGE.findall(sample_text)
    print RE.DIR_FILE_PREAMBLE.findall(sample_text)
    print extract(RE.FILE_SIZE_PREAMBLE, sample_text)
    print RE.FREE_SPACE_SIZE.findall(sample_text)
    print RE.SW_VERSION.findall(sample_text)
