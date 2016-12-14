#!/usr/bin/env python2.6
# -*- coding: utf-8
# import netmiko
#
# net_connect = netmiko.ConnectHandler(**{
#     'device_type': 'alcatel_sros',
#     'ip': 'ds1-zyt3',
#     'username': 'butko',
#     'password': 'xxxxxx',
#     'port': 22,
#     'verbose': False,
# })
#
# print(net_connect.send_command('environment no more'))
#
#
# out = {u'cf1:/backup': u'<DIR>',
#          u'cf1:/backup/bof.bak': u'700',
#          u'cf1:/bof.cfg': u'798',
#          u'cf1:/bof.cfg.1': u'725',
#          u'cf1:/bof.cfg.2': u'701',
#          u'cf1:/bof.cfg.3': u'663',
#          u'cf1:/boot.tim': u'8426112',
#          u'cf1:/bootlog.txt': u'4197',
#          u'cf1:/bootlog_prev.txt': u'4072',
#          u'cf1:/ds2-zyt3.cfg': u'78130',
#          u'cf1:/ds2-zyt3.cfg.1': u'78130',
#          u'cf1:/ds2-zyt3.cfg.2': u'78106',
#          u'cf1:/ds2-zyt3.cfg.3': u'78106',
#          u'cf1:/ds2-zyt3.cfg.4': u'78106',
#          u'cf1:/ds2-zyt3.cfg.5': u'78106',
#          u'cf1:/ds2-zyt3.ndx': u'2649',
#          u'cf1:/ds2-zyt3.ndx.1': u'2649',
#          u'cf1:/ds2-zyt3.ndx.2': u'2649',
#          u'cf1:/ds2-zyt3.ndx.3': u'2649',
#          u'cf1:/ds2-zyt3.ndx.4': u'2649',
#          u'cf1:/ds2-zyt3.ndx.5': u'2649',
#          u'cf1:/images': u'<DIR>',
#          u'cf1:/images/TiMOS-7.0.R9': u'<DIR>',
#          u'cf1:/images/TiMOS-7.0.R9/boot.tim': u'8426112',
#          u'cf1:/images/TiMOS-7.0.R9/both.tim': u'44325568',
#          u'cf1:/images/TiMOS-B-4.0.R2': u'<DIR>',
#          u'cf1:/ssh': u'<DIR>',
#          u'cf1:/ssh/SSHClientHostFile': u'0',
#          u'cf1:/ssh/sshV2SvrPrivDSAkeyFile': u'896',
#          u'cf1:/ssh/sshV2SvrPrivRSAkeyFile': u'1184',
#          u'cf1:/ssh/sshV2SvrPubDSAkeyFile': u'790',
#          u'cf1:/ssh/sshV2SvrPubRSAkeyFile': u'288'}
#
# for folder in [key for key, val in out.items() if val == '<DIR>']:
#     for key in out.keys():
#         if folder != key and folder in key:
#             print('{0} have child'.format(folder))
#             break
#     else:
#         print('!!! {0} no child'.format(folder))


import sys
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

from paramiko import SSHClient, AutoAddPolicy, AuthenticationException
from scp import SCPClient

ssh = SSHClient()
ssh.set_missing_host_key_policy(AutoAddPolicy())
import time

password = ':0dnytdt1'

for i in range(1, 5):
    try:
        ssh.connect('ds1-chg912', username='butko', password=str(password), port=22, look_for_keys=False, allow_agent=False)
        print('Good')
        break
    except AuthenticationException:
        time.sleep(1.5)
        if i == 3:
            password = ':0dnytdt'
        print(i, 'Fail')
else:
    raise Exception('Fail to copy SW to DS')
