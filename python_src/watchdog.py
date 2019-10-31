import time
from datetime import datetime
import glob
import logging
import os
from pathlib import Path
import parameter_parser
import startup_checks

# create logger
watchdog_logger = logging.getLogger('watchdog')

def setup_logging():
    watchdog_logger.setLevel(logging.DEBUG)

    # create file handler which logs to file
    logfile_dir = Path.cwd() / 'Logs_watchdog'
    if not logfile_dir.is_dir():
        os.mkdir(logfile_dir)
    logfile_name = logfile_dir / (
            'watchdog-'
            + datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
            + '.log')

    fh = logging.FileHandler(logfile_name)
    fh.setLevel(logging.DEBUG)

    # create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter and add it to the handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # remove the previous loggers if needed
    for h in list(watchdog_logger.handlers):
        watchdog_logger.removeHandler(h)

    # add the new ones
    watchdog_logger.addHandler(fh)
    watchdog_logger.addHandler(ch)

def in_business(current_time, parameter):
    # Check to see that we are within business hours
    start_hour = parameter['Tracking_Start_Daily']
    stop_hour = parameter['Tracking_Stop_Daily']

    if current_time.hour >= start_hour and current_time.hour < stop_hour:
        station_open = True
    else:
        station_open = False

    return station_open

def sensor_pingable(parameter):

    sensor_path = parameter['Camera_Path']
    ping_status = startup_checks.check_ping(sensor_path)

    if ping_status['ping_status']:
        sensor_alive  = True
    else:
        sensor_alive = False

    return sensor_alive


def logs_correct(parameter, nowish):
    sensor_id = parameter['Sensor_ID']
    skimage_log_dir = startup_checks.skimage_log_filepaths(sensor_id)
    list_of_files = glob.glob(str(skimage_log_dir / '*'))

    # If some files are found in the folder, check how old they are
    if list_of_files:
        latest_file = max(list_of_files, key=os.path.getmtime)
        lastlog_timestamp = datetime.fromtimestamp(os.path.getctime(latest_file))
    else:
        lastlog_timestamp = datetime.now().replace(hour=0, minute=0, second=0)

    delta_time = nowish - lastlog_timestamp
    sleep_time_param = 2 * parameter['Period_Skimage_Log']

    if delta_time.seconds < sleep_time_param:
        logs_correct = True
    else:
        logs_correct = False

    return logs_correct


# Setup watchdog logs
setup_logging()

# Get file paths
file_paths = startup_checks.check_filesystem()

# Load parameters
parameters = parameter_parser.get_parameters()

# Number of cycles between every check (1 cycle ~ 60s)
sleep_time_periods = 5

# Get initial value of sleep time
max_period = parameters['Period_Skimage_Log']
sleep_time = max_period * sleep_time_periods

watchdog_logger.info('Starting watch')
while True:
    time.sleep(sleep_time)

    nowish = datetime.now()
    need_to_reboot = False
    sensor_id = str(parameters['Sensor_ID'])
    infoStr = ''

    # Is the station open? If so, check the status of the sensor.
    if in_business(nowish, parameters):
        infoStr += 'Sensor ' + sensor_id + ' is within business hours'

        #  Is the sensor pingable? If so, check the logs are up to date
        if sensor_pingable(parameters):
            infoStr += ', camera is pingable'
            #  Are the logs up to date? If so, everything it is all good for this sensor
            if logs_correct(parameters, nowish):
                infoStr += ' and logs are up to date'
                need_to_reboot = False

            # If we are in business hours and the sensor is pingable but the logs are not up to date there is a
            # problem, and we need to restart ...
            # Todo: We can imagine that the sensor is pingable but it is not operating correctly...
            else:
                infoStr += ' but logs are outdated'
                need_to_reboot = True

        # If the sensor is not pingable, we don't worry about checking the logs
        else:
            infoStr += ' but the camera is not pingable'

    #  If the station is closed, we don't worry about checking the sensor or the logs
    else:
        infoStr += 'Station is closed'

    #  If we need to reboot,
    if need_to_reboot:
        infoStr += ': resetting skimage.\n\n'

        # Check semaphore directory
        parameters_filepath = file_paths['params']
        semaphore_dir = parameters_filepath / 'semaphore'  # this should be data/semaphore
        if not semaphore_dir.is_dir():
            semaphore_dir.mkdir(parents=True, exist_ok=True)

        semaphore = semaphore_dir / 'semaphore'
        with open(semaphore, 'a') as f:
            f.write(str(nowish) + ' : restarting signal \n')

        watchdog_logger.warning(infoStr)

        setup_logging() # Change the watchdog log file
        watchdog_logger.info('Monitoring the newly reset Skimage. Will recheck in '
                                + str(sleep_time) + ' seconds')
    else:
        infoStr += ': next check in ' + str(sleep_time) + ' seconds.'
        watchdog_logger.info(infoStr)