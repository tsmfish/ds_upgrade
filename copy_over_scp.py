#!/usr/bin/env python2.6
# -*- coding: utf-8

import sys
import time

sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException
from scp import SCPClient
from ds_helper import COLORS, print_for_ds


FAIL_CONNECTION_WAIT_INTERVALS = [2, 3, 3, 7, 9, 13, 17, 25, 39]
RETRY_COUNT = 5


def scp_copy(ssh_transport, what, where, io_lock=None):
    """Function for recursive copy directory to ds
    :parameter what='folder/' copy content of this folder to remove folder (where)
    :parameter what='folder' copy this folder to remove with saving name
    :exception Exception() if AuthenticationException occurred 5-times
    """

    with SCPClient(ssh_transport) as scp:
        scp.put(what, where, recursive=True)
