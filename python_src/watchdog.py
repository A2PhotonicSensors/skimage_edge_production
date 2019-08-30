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

    # add the handlers to the logger
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


def logs_correct(parameter, sleep_time_periods, nowish):
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
    sleep_time_param = sleep_time_periods * parameter['Period_Skimage_Log']

    if delta_time.seconds < sleep_time_param:
        logs_correct = True
        watchdog_logger.info('Sensor ' + str(sensor_id) + ' logs are up to date')
    else:
        logs_correct = False
        watchdog_logger.error('Sensor ' + str(sensor_id) + ' logs are out of date')

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

while True:

    nowish = datetime.now()

    need_to_reboot = False

    sensor_id = str(parameters['Sensor_ID'])

    # Is the station open? If so, check the status of the sensor.
    if in_business(nowish, parameters):
        watchdog_logger.info('Sensor ' + sensor_id + ' is within business hours')

        #  Is the sensor pingable? If so, check the logs are up to date
        if sensor_pingable(parameters):

            watchdog_logger.info('Sensor ' + sensor_id + ' is pingable')
            #  Are the logs up to date? If so, everything it is all good for this sensor
            if logs_correct(parameters, sleep_time_periods, nowish):

                watchdog_logger.info('Sensor ' + sensor_id + ' logs are up to date')
                need_to_reboot = False

            # If we are in business hours and the sensor is pingable but the logs are not up to date there is a
            # problem, and we need to restart ...
            # Todo: We can imagine that the sensor is pingable but it is not operating correctly...
            else:

                watchdog_logger.warning('Logs not recording correctly for sensor '
                                        + str(parameters['Sensor_ID'])
                                        + ' despite being business hours and sensor is pingable. Restarting Skimage')
                need_to_reboot = True

        # If the sensor is not pingable, we don't worry about checking the logs
        else:

            watchdog_logger.warning('Sensor ' + str(parameters['Sensor_ID']) + ' is NOT pingable!')

    #  If the station is closed, we don't worry about checking the sensor or the logs
    else:

        watchdog_logger.info('Station is closed')

    #  If we need to reboot,
    if need_to_reboot:
        watchdog_logger.error('Resetting docker')

        # Check semaphore directory
        parameters_filepath = file_paths['params']
        semaphore_dir = parameters_filepath.parent / 'semaphore'  # this should be data/semaphore
        if not semaphore_dir.is_dir():
            os.mkdir(semaphore_dir)

        semaphore = semaphore_dir / 'semaphore'
        with open(semaphore, 'a') as f:
            f.write('Restarting signal \n')

        watchdog_logger.info('Monitoring the newly reset Skimage. Will recheck in '
                                + str(sleep_time) + ' seconds')
        break


    # Todo: some kind of check/reload if parameter file has been changed
    watchdog_logger.info('Watchdog will recheck skimage in ' + str(sleep_time) + ' seconds')
    time.sleep(sleep_time)