#!/usr/bin/env python2.6
# -*- coding: utf-8

import sys
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient


def scp_copy(ds, user, _password, what, where):
    """Function for recursive copy directory to ds
    :parameter what='folder/' copy content of this folder to remove folder (where)
    :parameter what='folder' copy this folder to remove with saving name
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    ssh.connect(ds, username=user, password=str(_password), port=22, look_for_keys=False, allow_agent=False)

    with SCPClient(ssh.get_transport()) as scp:
        scp.put(what, where, recursive=True)

