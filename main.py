#!/usr/bin/env python2.6
# -*- coding: utf-8

import optparse
import getpass
import sys
from DS_Class import DS
from copy_over_scp import scp_copy
from pprint import pprint

parser = optparse.OptionParser(description='Prepare for DS upgrade', usage="usage: %prog [ds_name]")
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("incorrect number of arguments")


user = getpass.getuser()
secret = getpass.getpass('Password for DS:')

ds_name = args[0]
new_SW = {
    'SAS-X': '/home/mpls/soft/7210-SAS-X-TiMOS-7.0.R13/',
    'SAS-M': '/home/mpls/soft/7210-SAS-M-TiMOS-7.0.R13/'}
folder_for_SW = 'images/TiMOS-7.0.R13'
new_primery_img = 'cf1:/{0}/both.tim'.format(folder_for_SW)
new_boot_file = 'cf1:/{0}/boot.tim'.format(folder_for_SW)


# Create object
i = DS(ds_name, user, secret)

# Connect and get basic inform
print('\n' + '=' * 15 + ' Start process for \"{ds}\" '.format(ds=i.ip) + '=' * 15 + '\n')
i.conn()
i.get_base_info()

# Get all files
# pprint(i.get_all_files())
# input()

# Check prim image
primary_img = i.check_verion(i.prime_image)
if primary_img:
    if primary_img[1] == i.hw_ver:
        print('*** Primary image good and has version {0}'.format(primary_img[0]))
        print('*** ' + i.prime_image)
    else:
        print('!!!! Problem with primary image')
        print('*** ' + i.prime_image)
        sys.exit()

# Write primary image to secondary in bof
print('*** Write primary-image to secondary in bof file')
cmd = 'bof secondary-image {0}'.format(i.prime_image)
print('*** #{0}'.format(cmd))
print(i.send(cmd))
# print(i.send('show bof'))

# Find old soft
print('*** Finding all sw in cf1:/...')
old_boots = i.find_files('boot.tim')
try:
    old_boots.remove('cf1:/boot.tim')
except ValueError:
    print('**! cf1:/boot.tim Not exist!')

old_both = i.find_files('both.tim')
old_both.remove(i.prime_image.replace('\\', '/'))


# Remove old SW
print('*** Removing old SW')
for files in (old_boots, old_both):
    for f in files:
        # For beginning ask user for all deleting in future may be auto
        answer = raw_input("*** Delete {0} (y/n)? ".format(f))
        if answer.lower() == 'y':
            cmd = 'file delete {0} force'.format(f)
            print('*** ' + i.send(cmd))

# Delete empty folders
emt_folders = i.find_empty_folders()
if emt_folders:
    print('*** Deleting empty folders {0}'.format(','.join(emt_folders)))
    for folder in emt_folders:
        cmd = 'file rd {0} force'.format(folder)
        print(i.send(cmd))

# Check free space
mb = i.free_space()
print('*** Free {mb}MB on {ip}'.format(mb=mb, ip=i.ip))
if mb < 62:
    print('!!! Not enough space for continue')
    sys.exit('!!! Not enough space for continue')

# Make image folder
print('*** Try to create directory \"images\"')
print('*** #file md cf1:\{0}'.format(folder_for_SW))
i.send('file md cf1:\images')
i.send('file md cf1:\{0}'.format(folder_for_SW))


# Copy new sw to ds
print('*** Start coping new sw...')
scp_copy(i.ip, i.user, i.password, new_SW[i.hw_ver], folder_for_SW)

# Check free space
mb = i.free_space()
print('*** Free {mb}MB on {ip} after copy new SW'.format(mb=mb, ip=i.ip))

# Check new SW and write to bof.cfg
print('*** Write new SW to primary-image')
if i.check_verion(new_primery_img)[1] == i.hw_ver:
    cmd = 'bof primary-image {0}'.format(new_primery_img).replace('/', '\\')
    print('*** #{0}'.format(cmd))
    print(i.send(cmd))
    # print(i.send('show bof'))
else:
    print('!!! New both.tim not from this platform')
    sys.exit()

# Save bof and config
print('*** Save new bof and config')
i.save_configs()


# Change boot.tim in root directory
print('*** Change file cf1:/boot.tim to new ({0})'.format(new_boot_file))

if i.check_verion(new_boot_file)[1] == i.hw_ver:
    # remove read only attribute
    print(i.send('file attrib -r cf1:/boot.tim'))
    cmd = 'file copy {0} cf1:/boot.tim force'.format(new_boot_file)
    print('*** #{0}'.format(cmd))
    # print(i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5))
    i.net_connect.send_command(cmd, expect_string='copied.', delay_factor=5)
else:
    sys.exit('!!! New boot.tim not from this platform')

print('\n' + '=' * 15 + ' Finish process for \"{ds}\" '.format(ds=i.ip) + '=' * 15 + '\n')
