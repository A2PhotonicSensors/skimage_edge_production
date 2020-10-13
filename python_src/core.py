# -*- encoding: utf-8 -*-
# Import skimage modules
import parameter_parser
import startup_checks

# import cv2

# Import external modules
import logging
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import time
from collections import namedtuple
import shutil
import random
import os
import fnmatch
import ftplib

if os.uname().machine == 'armv71':
    import Detect_and_Track_ARM as cpp_fun
else:
    import Detect_and_Track_x86 as cpp_fun

# Core program:
#   -Does object detection
#   -Does tracking
#   -Does counting

core_logger = logging.getLogger('skimage.core')

class Tracker:
    def __init__(self,track_id, x, y, size, valids, color):
        self.UUID = track_id
        self.Pos = np.array([x, y], np.float32)
        self.Vit = np.array([0, 0], np.float32)
        self.Size = np.array(size, np.int32)
        self.Valid = np.array(valids)
        self.color = color 

class CameraCore:
    def __init__(self, parameters):

        # Set parameters for this camera
        self.parameters = parameters
        paramsStr = ''
        for attribute, value in parameters.items():
            paramsStr += '\n{} : {}'.format(attribute, value)
        core_logger.info('Skimage starting with the following parameters:' + paramsStr)

        if parameters['Width_Image']/parameters['Height_Image']*9 != 16:
            core_logger.warning('Image format is not 16/9, cut-lines and ROI may be distorted !')
        # Basic attributes
        self.sensor_id = self.parameters['Sensor_ID']
        self.debug_mode = self.parameters['Debug_Mode']

        # Initialize trackers and counters
        self.multi_tracker = []
        self.list_of_crossings = pd.DataFrame()
        self.lists_of_trackers_counted = []
        self.skiers_passed = []

        self.station_is_open = True
        self.check_business_hours()

        # Initialize logging timers
        self.time_last_skimage_log = time.time()
        self.nb_processed_frames = 0

        # Set up logging directory structure
        self.skimage_logDir = startup_checks.skimage_log_filepaths(self.parameters['Sensor_ID'])
        self.infoStr = ''

        # Initialize cut lines, created named tuples
        self.cut_lines = []
        self.Point = namedtuple('Point', ['x', 'y'])
        self.initialize_cut_line()
        for cut_line in self.cut_lines:
            self.lists_of_trackers_counted.append([])
            self.skiers_passed.append(0)
        self.detect_and_track = cpp_fun.DetectAndTrack(parameters)
        self.detect_and_track.setup_RoI(parameters['ROI'])
        self.detect_and_track.set_skiers_passed(self.skiers_passed)
        video_dims = self.detect_and_track.initialize_camera()
        success = video_dims[0]
        if success != 0:
            if success == -1:
                core_logger.critical("Error opening video stream or file: " + self.parameters["Camera_Path"])
            elif success == -2:
                core_logger.critical('Video width, height or FPS do not match the values specified in the parameter file :\n'
                                    'Expected: ' + str(self.parameters['Width_Image']) + 'x' + str(self.parameters['Height_Image']) + ' at ' + str(self.parameters['FPS']) + ' FPS,\n'
                                    'Got: ' + str(video_dims[1]) + 'x' + str(video_dims[2]) + ' at ' + str(video_dims[3]) + ' FPS.')

        if self.parameters["Local_File"]:
            success = self.detect_and_track.initialize_videowriter()
            if success != 0:      
                core_logger.warning("Error opening the file to write: processed video cannot be saved")

        if self.detect_and_track.isValidHardware:
            core_logger.info("Hardware validation successful")
        else:
            core_logger.critical("Hardware validation failed. Counting disabled.")

    def initialize_cut_line(self):
        # Builds the cut_lines array from the parameters
        # Get all parameter fields that begin with 'cutLine
        cutline_keys = fnmatch.filter(self.parameters.keys(), 'Cut_Line*')

        # For each cut line specified in the parameters file in normalized coordinates
        # (x1,y1), (x2,y2), ... read in and scale into image coordinates
        for key in cutline_keys:
            cutLine = self.parameters[key]
            if cutLine:
                cut_line_rel = np.array(cutLine, np.float32)
                cut_line_rel[:,0] = cut_line_rel[:,0]*self.parameters['Width_Image']
                cut_line_rel[:,1] = cut_line_rel[:,1]*self.parameters['Height_Image']
                self.cut_lines.append(cut_line_rel)

    def check_business_hours(self):
        # Check to see that we are within business hours
        nowish = datetime.now()
        if nowish.hour >= self.parameters['Tracking_Start_Daily'] and nowish.hour < self.parameters['Tracking_Stop_Daily']:
            self.station_is_open = True
        else:
            self.station_is_open = False

    def count_crossings(self, idx):
        # Generate a line in the SKIMAGE log when a skier crosses the line
        date_string = datetime.now().strftime('%d/%m/%Y')
        time_string = datetime.now().strftime('%H:%M:%S:%f')[:-3]

        log_dict = {'sensorID': str(self.sensor_id),
                    'date': date_string,
                    'time': time_string,
                    'cut_period': 0,  # Milliseconds barrier was cut, not relevant for us so set to zero
                    'voltage1': '',
                    'voltage2': '',
                    'voltage3': ''
                    }
        for i in range(len(self.cut_lines)):
            key = 'skiers_passed_cutline_' + str(i)
            if i == idx:
                log_dict[key] = 1
                self.skiers_passed[i] += 1
            else:
                log_dict[key] = 0

        # Update pour l'affichage dans le C
        self.detect_and_track.set_skiers_passed(self.skiers_passed)
        new_row = pd.Series(log_dict)

        self.list_of_crossings = self.list_of_crossings.append(new_row, ignore_index=True)

    def has_crossed(self, a1, b1, cut_line):
        """ Returns True if line segments a1b1 and a2b2 intersect. """
        'https://www.toptal.com/python/computational-geometry-in-python-from-theory-to-implementation'
        # If a radar instance calls this works because pol2cart is a valid method, else continue
        def ccw(A, B, C):
            """ Returns True if orientation is counter clockwise
            Tests whether the turn formed by A, B, and C is ccw by computing cross product
            If cross product is positive orientation is counter clockwise, if negative then clockwise """
            if (B.x - A.x) * (C.y - A.y) > (B.y - A.y) * (C.x - A.x):
                counter_clockwise = True
            else:
                counter_clockwise = False
            return counter_clockwise

        crossed_segment = []
        for ii in range(len(cut_line)-1):
            a2 = self.Point(cut_line[ii][0],cut_line[ii][1])
            b2 = self.Point(cut_line[ii+1][0],cut_line[ii+1][1])
            crossed_segment.append(ccw(a1, b1, a2) != ccw(a1, b1, b2) and ccw(a2, b2, a1) != ccw(a2, b2, b1))        
        return any(crossed_segment)

    def save_skimage_log(self):
        # Write SKIMAGE log
        nowish = datetime.now()
        datestr = datetime.now().strftime('%d/%m/%Y')
        timestr = datetime.now().strftime('%H:%M:%S:%f')[:-3]

        skimage_log_names = []
        keys = []
        for ii in range(len(self.cut_lines)):
            keys.append('skiers_passed_cutline_' + str(ii))
            
        for ii in range(len(self.cut_lines)):
            if len(self.list_of_crossings) == 0:
                total = 0
                cutline_list_of_crossings = pd.DataFrame()
            else:
                key = 'skiers_passed_cutline_' + str(ii)
                # Add the standard column for counting
                self.list_of_crossings['skiers_passed'] = self.list_of_crossings[key]
                # Only keep the lines corresponding to this cutline
                cutline_list_of_crossings = self.list_of_crossings[self.list_of_crossings[key] != 0]
                # Drop the specific columns
                cutline_list_of_crossings = cutline_list_of_crossings.drop(columns=keys)
                total = self.list_of_crossings[key].sum()
            
            total_row = pd.Series(
                {'sensorID': str(self.sensor_id),
                'date': datestr,
                'time': timestr,
                'cut_period': int((time.time() - self.time_last_skimage_log) * 1000),  # millisecs since last log
                'voltage1': '',
                'voltage2': '',
                'voltage3': '',
                'skiers_passed': total
                })

            cutline_list_of_crossings = cutline_list_of_crossings.append(total_row, ignore_index=True)
            cutline_list_of_crossings.skiers_passed.astype(int)
            cutline_list_of_crossings.cut_period.astype(int)

            skimage_log_name = self.skimage_logDir / (nowish.strftime("%Y%m%d_%H%M")
                                                    + '_'
                                                    + str(self.parameters['Sensor_ID'])
                                                    + str(ii)
                                                    + '.csv')

            skimage_log_names.append(skimage_log_name)

            cutline_list_of_crossings.to_csv(skimage_log_name,
                                        header=0,
                                        index=False,
                                        columns=['sensorID',
                                                'date',
                                                'time',
                                                'cut_period',
                                                'voltage1',
                                                'voltage2',
                                                'voltage3',
                                                'skiers_passed'])

            # # Create copy of skimage log in folder that is scanned by the send to ftp function 'monitor_logging'
            # shutil.copy(skimage_log_name, self.skimage_logToFTP)
            # core_logger.info('SKIMAGE log written from sensor: ' + str(self.sensor_id))
            
        self.infoStr += ': ' + '/'.join(str(int(x)) for x in self.skiers_passed)  + ' skiers passed'
        
        # Send the local to remote FTP server
        self.sendToFTP(skimage_log_names)
        # Reset SKIMAGE dataframe
        self.list_of_crossings = pd.DataFrame()
        self.skiers_passed = [0]*len(self.cut_lines)
        self.detect_and_track.set_skiers_passed(self.skiers_passed)

    def sendToFTP(self,filenames):
        server = self.parameters['FTP_Path']
        username = 'skiflux'
        password = 'Sk1Flux.'
        try:
            with ftplib.FTP(server, username, password, timeout=1) as ftp:
                ftp.cwd('/')
                for filename in filenames:
                    fh = open(filename, 'rb')
                    ftp.storbinary('STOR ' + filename.name, fh)
                    fh.close()
                self.infoStr += ' and logs has been successfully uploaded to FTP.'
        except Exception as error:
            self.infoStr += ' but FTP server cannot be reached: ' + str(error)
        return

    def do_recording(self):
        # List of all existing trackers still in record
        uuids_extant = [tracker.UUID for tracker in self.multi_tracker]

        # For each cut_line
        for idx, cut_line in enumerate(self.cut_lines):
            # Only keep exisiting trackers in the list of already counted trackers 
            self.lists_of_trackers_counted[idx] = [x for x in self.lists_of_trackers_counted[idx] if x in uuids_extant]
            # core_logger.info('trackers_counted : ' + str(self.lists_of_trackers_counted[idx]))
            # Check every tracker
            for tracker in self.multi_tracker:
                # core_logger.info('tracker with ID' + str(tracker.UUID) + ' at ' + str(self.Point(tracker.Pos[0,-1], tracker.Pos[1, -1])))
                # If the track is longer than Valid_Min_Frames
                if tracker.Valid.size >= self.parameters['Valid_Min_Frames']:
                    # If the last two positions of the track are valid
                    # Todo: Clean this up, allow tracks that are valid before, valid after, but for whatever reason NOT valid at the line to still be counted
                    if (tracker.Valid[-2:]).all():
                        # If the track has not been already counted
                        if tracker.UUID not in self.lists_of_trackers_counted[idx]:
                            # Last 2 positions
                            track_start = self.Point(tracker.Pos[0,-2], tracker.Pos[1, -2])
                            track_stop = self.Point(tracker.Pos[0,-1], tracker.Pos[1, -1])
                            # core_logger.info('Last 2 positions : ' + str(track_start) + ' and ' + str(track_stop))
                            if self.has_crossed(track_start, track_stop, cut_line):
                                # core_logger.info('CROSSED !')
                                # Count crossing at given cut line (idx)
                                self.count_crossings(idx)
                                self.lists_of_trackers_counted[idx].append(tracker.UUID)
                #         else:
                #             core_logger.info('Already counted')                    
                #     else:
                #         core_logger.info('Last 2 points not valid')
                        
                # else:
                #     core_logger.info('Not enough frames yet (' + str(tracker.Valid.size) + ')')

        # If time period specified in parameter file has elapsed, write the skimage log file
        if time.time() - self.time_last_skimage_log > self.parameters['Period_Skimage_Log']:
            self.time_last_skimage_log += self.parameters['Period_Skimage_Log'] # Reset timer
            avgFPS = round(self.nb_processed_frames/self.parameters['Period_Skimage_Log'],1)
            self.infoStr = str(avgFPS) + ' FPS'
            self.save_skimage_log()
            core_logger.info(self.infoStr)
            self.nb_processed_frames = 0

            # Check we are still in business
            self.check_business_hours()

    def parse_cpp_tracks(self):

        states = self.detect_and_track.get_multitracker_states()
        valids = self.detect_and_track.get_multitracker_valids()
        track_ids = self.detect_and_track.get_multitracker_uuids()
        self.multi_tracker = []
        
        for idx, track_id in enumerate(track_ids):
            track_state = states[idx]
            x = track_state[:, 0]
            y = track_state[:, 1]
            size = track_state[:, 4]
            valids_track = np.asarray(valids[idx]) 
            color = [255,255,255]
            track = Tracker(track_id, x, y , size, valids_track, color)
            self.multi_tracker.append(track)

    def camera_tracking_loop(self):
        core_logger.info('Starting tracking on sensor ' + str(self.sensor_id))

        # if self.debug_mode:
        #     try:
        #         import debugger
        #         debugger = debugger.PythonProcessor(self.parameters)
        #     except ImportError:
        #         core_logger.info('The \"Debug_Mode\" was set to true, but this is a' 
        #                          ' production version of Skimage that does not allow'
        #                          ' the debugging feature.')
        #         self.debug_mode = False

        while self.station_is_open:
            start_time = datetime.now()
            ret = self.detect_and_track.process_frame()
            if ret:
                core_logger.info('No more frames available, quitting skimage.')
                if self.parameters["Local_File"]:
                    os.system("touch data/semaphore/RESET") # exit skimage and watchdog dockers
                break

            self.parse_cpp_tracks()

            # if self.debug_mode:
            #     debugger.test()

            # # ****** Recording # ******
            self.do_recording()

            self.nb_processed_frames +=1
            # core_logger.info('')
            # core_logger.info('Processing frame ' + str(self.nb_processed_frames))
            # proc_time = datetime.now() - start_time
            # core_logger.info(str(1/proc_time.microseconds*1e6)[:4] + ' FPS')

        if not self.station_is_open:
            core_logger.info('Station is closed, stopping tracking on sensor: ' 
                                    + str(self.sensor_id)
                                    + ' and quitting Skimage.\n\n')

# To profile run:
# python -B -m cProfile -o output.prof core.py
# then visualize with:
# snakeviz output.prof
# To profile memory usage run:
# mprof run python core.py
# the visualize with:
# mprof plot
