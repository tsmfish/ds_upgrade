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
from main import COLORS, print_for_ds

WAIT_TIME, RETRY_COUNT = 7, 5


def scp_copy(ds, user, _password, what, where, io_lock=None):
    """Function for recursive copy directory to ds
    :parameter what='folder/' copy content of this folder to remove folder (where)
    :parameter what='folder' copy this folder to remove with saving name
    :exception Exception() if AuthenticationException occurred 5-times
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    for i in range(RETRY_COUNT):
        try:
            ssh.connect(ds, username=user, password=str(_password), port=22, look_for_keys=False, allow_agent=False)
            break
        except AuthenticationException as e:
            # Try reconnect
            print_for_ds(ds, "Warning: " + str(e), io_lock, COLORS.error)
            time.sleep(WAIT_TIME)
    else:
        raise Exception('Fail to copy SW to {0}'.format(ds))

    with SCPClient(ssh.get_transport()) as scp:
        scp.put(what, where, recursive=True)
