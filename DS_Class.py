#!/usr/bin/env python2.6
# -*- coding: utf-8
import sys
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/netmiko-1.1.0-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

from netmiko import ConnectHandler
from netmiko import NetMikoTimeoutException, NetMikoAuthenticationException
import re
import logging
import os.path

logging.basicConfig(format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', level = logging.WARN)


class DS(object):
    """ Class for manipulating ds trough ssh"""
    _r_sw_ver = re.compile(r'TiMOS-[BL]-[^ ]*')
    _r_hw_ver = re.compile(r'SAS[^ ]*')
    _r_prime_img = re.compile(r'primary-image[ ]*(.*)')
    _r_secon_img = re.compile(r'secondary-image[ ]*(.*)')
    _r_config = re.compile(r'primary-config[ ]*(.*)')
    _r_not_found = re.compile(r'CLI Could not access')
    _r_free_spce = re.compile(r'(\d*) bytes free')
    _r_date_file = re.compile(r'(^\d{2}/\d{2}/\d{4})')

    def __init__(self, ip, user, password, port=22):
        self.ip = ip.strip()
        self.user = user
        self.password = password
        self.port = int(port)

        self.net_connect = None
        self.sw_ver = None
        self.hw_ver = None
        self.prime_image = None
        self.second_image = None
        self.config = None
        self.files = None

    def __str__(self):
        return '<DS object \"{user}@{ip}:{port}\">'.format(ip=self.ip, port=self.port, user=self.user)

    def __repr__(self):
        return 'DS object \"{user}@{ip}:{port}\"'.format(ip=self.ip, port=self.port, user=self.user)

    def conn(self):
        """Make ssh connection"""
        try:
            self.net_connect = ConnectHandler(**{
                'device_type': 'alcatel_sros',
                'ip': self.ip,
                'username': self.user,
                'password': self.password,
                'port': self.port,
                'verbose': False,
            })
            self.net_connect.send_command('environment no more')
            logging.debug(u'Connect to {0}'.format(self.ip))

        except NetMikoTimeoutException:
            logging.warning(u'Timeout, may be host {0} unreachable'.format(self.ip))
        except NetMikoAuthenticationException:
            logging.warning(u'!!! Wrong password !!!!')
            print('!!! Wrong password !!!!')
            assert ExceptionWrongPassword(self.user)
            # sys.exit()

    def get_base_info(self):
        """ Return base information about switch
        such as path to config and sw images"""

        if self.net_connect:
            out = self.net_connect.send_command('show version')
            self.sw_ver = DS._r_sw_ver.findall(out)[0]
            self.hw_ver = DS._r_hw_ver.findall(out)[0]

            out = self.net_connect.send_command('show bof')
            if DS._r_prime_img.search(out):
                self.prime_image = DS._r_prime_img.search(out).group(1)
            if DS._r_secon_img.search(out):
                self.second_image = DS._r_secon_img.search(out).group(1)
            self.config = DS._r_config.findall(out)[0]

        return self.sw_ver, self.hw_ver, self.prime_image, self.second_image, self.config

    def check_verion(self, _file):
        """Check file version"""
        if self.net_connect:
            out = self.net_connect.send_command('file version {0}'.format(_file))
            # print(out)
            if DS._r_not_found.search(out):
                print('File \"{file}\" not exist on {ip}'.format(file=_file, ip=self.ip))
                return False
            hw = DS._r_hw_ver.search(out)
            sw = DS._r_sw_ver.search(out)
            if hw:
                if hw.group(0) != self.hw_ver:
                    print('!!! File \"{file}\" from another platform ')
                return sw.group(0), hw.group(0),
            return False

    def send(self, cmd, expect_string=None):
        if self.net_connect:
            return self.net_connect.send_command(cmd, expect_string=expect_string)

    def free_space(self):
        if self.net_connect:
            return int(DS._r_free_spce.search(self.net_connect.send_command('file dir')).group(1)) / 1048576

    def get_all_files(self):
        """
        Method for get all files in ds
        :return dict with all files
        """
        file_system = {}

        def get_files(_dir):
            _dir = _dir if _dir[-1] == '/' else _dir + '/'
            out = self.send('file dir ' + _dir)
            # print('### {0}'.format(_dir))
            for line in out.split('\n'):
                if DS._r_date_file.match(line):
                    i = line.split()
                    # print(line)
                    # filter current './' and parent '../' directory
                    if i[3] not in ('./', '../', '.', '..'):
                        file_system[_dir + i[3]] =  i[2]
                        if i[2] == '<DIR>':
                            get_files(_dir + i[3])
        get_files('cf1:/')

        self.files = file_system
        return file_system

    def find_files(self, target):
        """ Find target files on flash(cf1:/) """
        # If for now we not have file structure - get it
        if not self.files:
            self.get_all_files()

        return [g for g in self.files.keys() if os.path.basename(g) == target]

    def save_configs(self):
        """
        Simple save bof and config
        and return print out if it needed
        """
        res = ''
        if self.net_connect:
            res += self.net_connect.send_command_expect('bof save', expect_string='Completed.')
            res += self.net_connect.send_command_expect('admin save', expect_string='Completed.')
        return res

    def find_empty_folders(self):
        """ Return list with empty folder oh cf1:/"""
        self.get_all_files()
        empty_folders = []
        for folder in [key for key, val in self.files.items() if val == '<DIR>']:
            for key in self.files.keys():
                if folder != key and folder in key:
                    break
            else:
                empty_folders.append(folder)
        return empty_folders


class ExceptionWrongPassword(Exception):
    def __init__(self, user_name):
        super.__init__()
        self.user_name = user_name

    def get_user_name(self):
        return self.user_name
