#!/usr/bin/env python2.6
# -*- coding: utf-8
import base64
import re
import logging
import threading
import multiprocessing
import time

import sys
# sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
# sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/netmiko-1.1.0-py2.6.egg/')
# sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
# sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
# sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

import netmiko
import paramiko
from netmiko import NetMikoAuthenticationException
from netmiko import NetMikoTimeoutException
from scp import SCPClient, SCPException
from netmiko.alcatel import AlcatelSrosSSH

_re_compile_class_name = re.compile(r'').__class__.__name__

def extract(regexp, text, flags=re.IGNORECASE):
    """

    :param regexp: regular expression
    :param text: source for extracting
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: first occur regular expression
    """
    assert(regexp.__class__.__name__ in [_re_compile_class_name, str.__name__])
    if regexp.__class__.__name__ == _re_compile_class_name:
        return regexp.findall(text).pop()
    if regexp.__class__.__name__ == str.__name__:
        return re.findall(regexp, text, flags).pop()
    return ""


def is_contains(regexp, text, flags=re.IGNORECASE):
    """

    :param regexp:
    :param text:
    :param flags: default re.IGNORECASE Only for string regexp arguments
    :return: True if string contains regular expression
    """
    assert(regexp.__class__.__name__ in [_re_compile_class_name, str.__name__])

    if regexp.__class__.__name__ == _re_compile_class_name:
        if regexp.search(text):
            return True
        else:
            return False
    if regexp.__class__.__name__ == str.__name__:
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

    assert(not io_lock or (io_lock and
           io_lock.__class__.__name__ in [threading.Lock().__class__.__name__,
                                          threading.RLock().__class__.__name__,
                                          multiprocessing.Lock().__class__.__name__,
                                          multiprocessing.RLock().__class__.__name__]))
    if io_lock: io_lock.acquire()
    print "{ds} : {message}".format(ds=ds, message=message)
    if io_lock: io_lock.release()


class DS(AlcatelSrosSSH):
    class RE:
        FLAGS = re.IGNORECASE
        FILE_DATE_STRING = r'\b\d{2}\/\d{2}\/\d{4}b'
        FILE_TIME_STRING = r'\b\d{2}:\d{2}[ap]\b'

        DIR_FILE_PREAMBLE = re.compile(FILE_DATE_STRING + r'\s+?' + FILE_TIME_STRING + r'\s+?(?:<DIR>|\d+?)\s+?', FLAGS)
        DS_NAME = re.compile(r'\bds\d-[0-9a-z]+\b', FLAGS)
        DS_TYPE = re.compile(r'\bSAS-[XM]\b', FLAGS)
        FILE_DATE = re.compile(FILE_DATE_STRING)
        FILE_SIZE_PREAMBLE = FILE_DATE_STRING + r'\s+?' + FILE_TIME_STRING + r'\s+?(\d+?)\s+?'
        FILE_TIME = re.compile(FILE_TIME_STRING)
        FREE_SPACE_SIZE = re.compile(r'\b(\d+?)\s+?bytes free\.', FLAGS)
        PRIMARY_BOF_IMAGE = re.compile(r'primary-image\s+?(\S+)\b', FLAGS)
        SECONDARY_BOF_IMAGE = re.compile(r'secondary-image\s+?(\S+)\b', FLAGS)
        PRIMARY_CONFIG_FILE = re.compile(r'primary-config\s+?(\S+)\b', FLAGS)
        '''
        TiMOS-B-4.0.R2
        TiMOS-B-5.0.R2
        TiMOS-B-7.0.R9
        TiMOS-B-7.0.R13
        '''
        SW_VERSION = re.compile(r'TiMOS-\w-\d\.\d\.R\d+?\b', FLAGS)
        
    class RESULT:
        VERSION_MISMATCH = 'warning: version mismatch'
        TYPE_MISMATCH = 'error: type mismatch'
        IMAGE_ABSENT = 'error: image not found'
        BOOT_IMAGE_ABSENT = 'warning: boot.tim image not found'
        BOOT_TYPE_MISMATCH = 'error: boot.tim type mismatch'
        BOOT_VERSION_MISMATCH = 'warning: boot.tim version mismatch'
        SET_ERROR = 'set error'
        COMPLETE = 'complete'

    RETRY_COUNT = 5
    RETRY_DELAY = 7

    _health_check_commands = [b'show system alarms',
                              b'show version',
                              b'show bof',
                              b'file dir',
                              b'show port',
                              b'show card state',
                              b'show service sdp-using',
                              b'show router interface',
                              b'show system ntp',
                              b'show system ptp',
                              b'show system security ssh']

    _boot_tim = b'boot.tim'
    scp_client = None
    _name = None

    def __init__(self, host, user, password, verbose=None, logfile=None):
        self.host = host
        self.username = user
        self.secret = password
        self.password = password
        self.device_type = 'ssh'
        self.verbose = verbose
        if logfile: logging.basicConfig(filename=logfile, level=logging.INFO)
        error = None
        for i in range(DS.RETRY_COUNT):
            try:
                super(self)
                logging.info("Connection established to {0}".format(self.username))
                break
            except NetMikoTimeoutException as e:
                logging.error(e.message)
                error = e
                time.sleep(DS.RETRY_DELAY)
            except NetMikoAuthenticationException as e:
                logging.error(e.message)
                error = e
                time.sleep(DS.RETRY_DELAY)
        else: raise error


    def connect(self):
        for i in range(self.RETRY_COUNT):
            logging.info("Try connect to {0} by {1}, try count: {3}".format(self.host, self.username, i))
            try:
                self.establish_connection()
            except netmiko.NetMikoAuthenticationException:
                logging.error('Can not authorise on {0} by {1}'.format(self.host, self.username))
                raise netmiko.NetMikoAuthenticationException('Can not authorise on {0} by {1}'
                                                             .format(self.host, self.username))
            except netmiko.NetMikoTimeoutException as e:
                pass
            except IOError as e:
                logging.error(e.message)
            time.sleep(self.RETRY_DELAY)
        else:
            raise netmiko.NetmikoAuthError("Can't connect by {user} to {host}"
                                           .format(user=self.username, host=self.host))
        logging.info("Connection established to {0}".format(self.username))
        self.session_preparation()

    def send(self, command_string, expect_string=None):
        logging.info(command_string)
        result = self.send_command(command_string, expect_string)
        logging.info(result)
        return result

    def get_bof_primary(self):
        return extract(DS.RE.PRIMARY_BOF_IMAGE, self.send(b'show bof'))

    def get_bof_secondary(self):
        return extract(DS.RE.SECONDARY_BOF_IMAGE, self.send(b'show bof'))

    def get_config_primary(self):
        return extract(DS.RE.PRIMARY_CONFIG_FILE, self.send(b'show bof'))

    def get_config_version(self):
        return extract(DS.RE.SW_VERSION, self.send(b'file type ' + self.get_config_primary()))

    def get_name(self):
        if not self._name:
            self._name = extract(DS.RE.DS_NAME, self.get_system_info())
        return self._name

    def get_system_info(self):
        return self.send(b'show system info')

    def get_type(self):
        return extract(DS.RE.DS_TYPE, self.send(b'show version'))

    def get_version(self):
        return extract(DS.RE.SW_VERSION, self.send(b'show version'))

    def get_free_space(self):
        return int(extract(DS.RE.FREE_SPACE_SIZE, self.send(b'file dir')))

    def save_configuration(self):
        return self.send(b'save bof') + '\n' + self.send(b'save config')
    
    def file_clear_readonly(self, file):
        return self.send(b'file attrib -r '+file)
    
    def file_copy(self, source, destination, forced=False):
        if forced:
            return self.send(b'file copy ' + source + ' ' + destination + ' forced')
        else:
            return self.send(b'file copy ' + source + ' ' + destination)
        
    def get_file_version(self, file):
        return extract(DS.RE.SW_VERSION, self.send(b'file version ' + file))
    
    def get_file_type(self, file):
        return extract(DS.RE.DS_TYPE, self.send(b'file version ' + file))
    
    def set_bof_primary(self, image):
        if not is_contains(DS.RE.DIR_FILE_PREAMBLE, self.send(b'file dir ' + image)):
            logging.error("Can't set [{0}] as primary image on {1}. File not found!".format(image, self.host))
            return self.RESULT.IMAGE_ABSENT
        if self.get_type().lower() != self.get_file_type(image).lower():
            logging.error("Can't set [{0}] as primary image on {1}. File ad switch type MISMATCH!"
                          .format(image, self.host))
            return self.RESULT.TYPE_MISMATCH

        self.send(b'set primary-image ' + image)
        if image.lower() != self.get_bof_primary():
            logging.error("Can't set [{0}] as primary image on {1}.".format(image, self.host))
            return self.RESULT.SET_ERROR

        if self.get_version().lower() != self.get_file_version(image):
            return self.RESULT.VERSION_MISMATCH
        else:
            return self.RESULT.COMPLETE

    def set_bof_secondary(self, image):
        if not is_contains(DS.RE.DIR_FILE_PREAMBLE, self.send(b'file dir ' + image)):
            logging.error("Can't set [{0}] as primary image on {1}. File not found!".format(image, self.host))
            return self.RESULT.IMAGE_ABSENT
        if self.get_type().lower() != self.get_file_type(image).lower():
            logging.error("Can't set [{0}] as primary image on {1}. File ad switch type MISMATCH!"
                          .format(image, self.host))
            return self.RESULT.TYPE_MISMATCH

        self.send(b'set secondary-image ' + image)
        if image.lower() != self.get_bof_secondary():
            logging.error("Can't set [{0}] as secondary image on {1}.".format(image, self.host))
            return self.RESULT.SET_ERROR

        if self.get_version().lower() != self.get_file_version(image):
            return self.RESULT.VERSION_MISMATCH
        else:
            return self.RESULT.COMPLETE

    def make_health_check(self):
        # result = ""
        # for command in self._health_check_commands:
        #     result += self.send(command)
        return '\n'.join(self.send(command) for command in self._health_check_commands)
        # return result

    def make_check(self):
        result = list()
        bof_primary_image = self.get_bof_primary()
        if not bof_primary_image: result.append(DS.RESULT.IMAGE_ABSENT)
        else:
            if self.get_type().lower() != self.get_file_type(bof_primary_image).lower():
                result.append(DS.RESULT.TYPE_MISMATCH)
            if self.get_version().lower() != self.get_file_version(bof_primary_image).lower():
                result.append(DS.RESULT.VERSION_MISMATCH)
        if not extract(DS.RE.DIR_FILE_PREAMBLE, b'file dir ' + self._boot_tim):
            result.append(DS.RESULT.BOOT_IMAGE_ABSENT)
        else:
            if self.get_type().lower() != self.get_file_type(self._boot_tim).lower():
                result.append(DS.RESULT.BOOT_TYPE_MISMATCH)
            if self.get_version().lower() != self.get_file_version(self._boot_tim).lower():
                result.append(DS.RESULT.BOOT_VERSION_MISMATCH)
        if not result: result.append(DS.RESULT.COMPLETE)
        return result

    def file_is_exist(self, file):
        return is_contains(DS.RE.DIR_FILE_PREAMBLE, self.send(b'file dir ' + file))

    def get_file_size(self, file):
        dir_file = extract(DS.RE.FILE_SIZE_PREAMBLE, self.send(b'file dir ' + file))
        if dir_file:
            return int(dir_file)
        else:
            return -1

    def _get_scp_client(self):
        if not self.scp_client:
            self.scp_client = SCPClient(self.remote_conn_pre.get_transport())
        return self.scp_client

    def scp_get_file(self, source_file, destantion_file):
        for i in range(DS.RETRY_COUNT):
            try:
                with self._get_scp_client() as scp:
                    scp.get(source_file, destantion_file, recursive=True)
                    return
            except SCPException as e:
                logging.error(e.message)
                time.sleep(DS.RETRY_DELAY)

    def scp_put_file(self, source_file, destination_file):
        for i in range(DS.RETRY_COUNT):
            try:
                with self._get_scp_client() as scp:
                    scp.put(source_file, destination_file, recursive=True)
                    return
            except SCPException as e:
                logging.error(e.message)
                time.sleep(DS.RETRY_DELAY)

    def file_delete(self, file, force=False):
        if self.file_is_exist(file):
            if force:
                return self.send(b'file delete ' + file + b' force')
            else:
                return self.send(b'file delete ' + file)
        else:
            return ""

    def directory_delete(self, dir, force=False):
        if self.file_is_exist(dir):
            if dir[-1] == '/': dir = dir[:-1]
            file_delete = self.file_delete(dir + '/*', True)
            if force:
                return file_delete + self.send(b'file rd ' + dir + b' force')
            else:
                return file_delete + self.send(b'file rd ' + dir)
        else:
            return ""

if __name__ == "__main__":
    with DS('ds1-kha3', 'pmalko', base64.b64decode(b'a1A2Qy1ONmQ=').decode('ascii'), verbose=True) as ds:
        print ds.get_name()
        print ds.get_type()
        print ds.get_version()
        print ds.get_config_version()
        print ds.get_bof_primary()
        print ds.get_bof_secondary()
        print ds.get_config_primary()
        print ds.get_free_space()
        print ds.is_file_exist(ds.get_bof_primary())
        print ds.get_file_version(ds.get_bof_primary())
        print ds.get_file_type(ds.get_bof_primary())
        print ds.get_file_size(ds.get_bof_primary())
        print ds.make_check()
        print ds.make_health_check()
