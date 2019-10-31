# -*- encoding: utf-8 -*-
from pathlib import Path
import logging
import os
from datetime import datetime
import subprocess
import pingparsing
import socket


module_logger = logging.getLogger('skimage.startup_checks')


def check_filesystem():
    base_fp = Path.cwd()

    logs_SKIMAGE_fp = base_fp / 'Logs_SKIMAGE'
    logs_program_fp = base_fp / 'Logs_program'
    data_fp = base_fp / 'data'

    file_paths = {'logs_SKIMAGE': logs_SKIMAGE_fp,
                  'logs_program': logs_program_fp,
                  'params': data_fp}

    if not logs_program_fp.is_dir():
        try:
            os.mkdir(logs_program_fp)
        except PermissionError:
            module_logger.exception('The program lacks the permission to create the necessary directory structure')

    if not logs_SKIMAGE_fp.is_dir():
        try:
            os.mkdir(logs_SKIMAGE_fp)
        except PermissionError:
            module_logger.exception('The program lacks the permission to create the necessary directory structure')

    if not all([logs_program_fp.is_dir(),
                logs_SKIMAGE_fp.is_dir(),
                data_fp.is_dir()]):

        module_logger.critical(
                'HALTING:'
                ' Directory tree incorrectly configured, please'
                ' consult the readme for the correct installation'
                ' procedure and try again')
        raise SystemExit
    else:
        return file_paths

# def remove_processed_video():

def skimage_log_filepaths(sensorID):
    """ SensorID is string, name of sensor"""
    file_paths = check_filesystem()

    nowish = datetime.now()
    month_dir = nowish.strftime('%B')
    day_dir = nowish.strftime('%d')

    if sensorID == 'ftp':
        skimage_log_dir = file_paths['logs_SKIMAGE'] / 'to_ftp'
        if not skimage_log_dir.is_dir():
            os.mkdir(skimage_log_dir)
    else:
        skimage_log_dir = file_paths['logs_SKIMAGE'] / ('sensorID_' + str(sensorID)) / month_dir / day_dir
        os.makedirs(skimage_log_dir, exist_ok=True)

    module_logger.info('Logs_SKIMAGE filepath valid')

    return skimage_log_dir


def check_ping(ip_address):

    # Get base ip address from full sensor path (e.g. rtsp://root:nahuatl23@192.168.138.212/axis-media/media.amp)
    try:
        tmp1 = ip_address.split('@')
        tmp2 = tmp1[1].split('/')
        ip_address_base = tmp2[0]

    except:
        ip_address_base = ip_address
        pass

    ping_status = {'ping_status': False}
    response = subprocess.run(['ping', '-c 1', '-w 1', ip_address_base],
                              stdout=subprocess.PIPE,
                              encoding='UTF-8')

    # and then check the response...
    if response.returncode == 0:

        # Parse results
        ping_parser = pingparsing.PingParsing()
        ping_status = ping_parser.parse(response.stdout).as_dict()
        ping_status.update({'ping_status': True})

    return ping_status

def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP