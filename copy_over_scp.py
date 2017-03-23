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
from ds_helper import COLORS, ds_print


FAIL_CONNECTION_WAIT_INTERVALS = [2, 3, 3, 7, 9, 13, 17, 25, 39]
RETRY_COUNT = 5


def scp_copy(ds, user, _password, what, where, io_lock=None, progress=None):
    """Function for recursive copy directory to ds
    :parameter what='folder/' copy content of this folder to remove folder (where)
    :parameter what='folder' copy this folder to remove with saving name
    :exception Exception() if AuthenticationException occurred 5-times
    """
    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    for i in range(RETRY_COUNT):
        try:
            ssh.connect(ds,
                        username=user,
                        password=str(_password),
                        port=22,
                        timeout=20,
                        allow_agent=True)
            break
        except Exception as e:
            # Try reconnect
            if i < RETRY_COUNT - 1:
                ds_print(ds, "Warning: " + str(e) + " Try reconnect...", io_lock, None, None, COLORS.info)
                time.sleep(FAIL_CONNECTION_WAIT_INTERVALS[i])
            else:
                ds_print(ds, "Error: " + str(e) + " STOP trying.", io_lock, None, None, COLORS.error)
                raise Exception('Fail to copy SW to {0}'.format(ds))

    with SCPClient(ssh.get_transport(), socket_timeout=20, progress=progress) as scp:
        scp.put(what, where, recursive=True)
