#!/usr/bin/env python2.6
# -*- coding: utf-8

import sys
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

import time
from paramiko import SSHClient, AutoAddPolicy, AuthenticationException
from scp import SCPClient


def scp_copy(ds, user, _password, what, where):
    """Function for recursive copy directory to ds
    :parameter what='folder/' copy content of this folder to remove folder (where)
    :parameter what='folder' copy this folder to remove with saving name
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    for i in range(1, 5):
        try:
            ssh.connect(ds, username=user, password=str(_password), port=22, look_for_keys=False, allow_agent=False)
            break
        except AuthenticationException:
            # Try reconnect
            time.sleep(2)
    else:
        raise Exception('Fail to copy SW to DS')

    with SCPClient(ssh.get_transport()) as scp:
        scp.put(what, where, recursive=True)

