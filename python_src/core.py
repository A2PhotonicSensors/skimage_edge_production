# -*- encoding: utf-8 -*-

# Import skimage modules
import parameter_parser
import startup_checks

# Import external modules
import logging
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import time
from collections import namedtuple
import shutil
import time
import random
import os

if os.uname().machine == 'x86_64':
    import Detect_and_Track_x86 as cpp_fun
else:
    import Detect_and_Track_ARM as cpp_fun

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
        self.Size = np.array([size], np.int32)
        self.Valid = np.array([valids])
        self.color = color 
class CameraCore:
    def __init__(self, parameters):

        # Set parameters for this camera
        self.parameters = parameters
        self.active = True
        # Basic attributes
        self.sensor_id = self.parameters['Sensor_ID']
        self.debug_mode = self.parameters['Debug_Mode']
        self.display_mode = self.parameters['Display_Mode']

        # Initialize trackers and counters
        self.multi_tracker = []
        self.multi_tracker_py = []
        self.list_of_crossings = pd.DataFrame()
        self.lists_of_trackers_counted = []
        self.multitracker_record = []

        self.station_is_open = True

        # Initialize logging timers
        self.time_last_track_log = time.time()
        self.time_last_skimage_log = time.time()

        # Set up logging directory structure
        self.tracks_log_dir = startup_checks.track_log_filepaths(self.parameters['Sensor_ID'])
        self.skimage_logDir = startup_checks.skimage_log_filepaths(self.parameters['Sensor_ID'])
        self.skimage_logToFTP = startup_checks.skimage_log_filepaths('ftp')


        # This is for skipping images if processing is too slow. Using all images <=> processing_mode = 1
        self.processing_mode = 1

        # Initialize cut lines, created named tuples
        self.cut_lines = []
        self.Cut_Line = namedtuple('Cut_Line', ['start', 'stop'])
        self.Point = namedtuple('Point', ['x', 'y'])

        # Initialize display info for camera and radar
        self.skiers_passed = []
        self.display_info = {'skiers_crossed': '',
                             'buffer_queue_size': '',
                             'core_queue_size': '',
                             'processing_rate': ''}

        self.start_time = []

        self.image_size = (self.parameters['Height_Image'], self.parameters['Width_Image'])
        self.update_im_size_params()

        self.detect_and_track = cpp_fun.DetectAndTrack(parameters)
        self.detect_and_track.initialize_camera()
        self.detect_and_track.setup_RoI(parameters['ROI'])

        for cut_line in self.cut_lines:
            self.lists_of_trackers_counted.append([])
            self.skiers_passed.append(0)

    def business_hours(self):
        # Check to see that we are within business hours
        start_hour = self.parameters['Tracking_Start_Daily']
        stop_hour = self.parameters['Tracking_Stop_Daily']
        nowish = datetime.now()
        if nowish.hour >= start_hour and nowish.hour < stop_hour:
            do_tracking = True
        else:
            do_tracking = False

            # Quit Skimage
            core_logger.info('Station is closed, quitting Skimage, see you tomorrow! ')
            self.active = False

        # If station has just opened or just closed then log change
        if not do_tracking == self.station_is_open:
            self.station_is_open = do_tracking
            if do_tracking:
                core_logger.info('The station has opened, starting to track skiers on sensor: ' 
                                 + str(self.sensor_id))
            else:
                core_logger.info('The station has closed, stopping tracking on sensor: ' 
                                 + str(self.sensor_id))

        return do_tracking

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

        new_row = pd.Series(log_dict)

        self.list_of_crossings = self.list_of_crossings.append(new_row, ignore_index=True)

    def has_crossed(self, a1, b1, a2, b2):
        """ Returns True if line segments a1b1 and a2b2 intersect. """
        'https://www.toptal.com/python/computational-geometry-in-python-from-theory-to-implementation'
        # If a radar instance calls this works because pol2cart is a valid method, else continue
        try:
            x_start, y_start = self.pol2cart(a1.x, a1.y)
            a1 = self.Point(x_start, y_start)
            x_stop, y_stop = self.pol2cart(b1.x, b1.y)
            b1 = self.Point(x_stop, y_stop)

        except AttributeError:
            pass

        def ccw(A, B, C):
            """ Returns True if orientation is counter clockwise
            Tests whether the turn formed by A, B, and C is ccw by computing cross product
            If cross product is positive orientation is counter clockwise, if negative then clockwise """
            if (B.x - A.x) * (C.y - A.y) > (B.y - A.y) * (C.x - A.x):
                counter_clockwise = True
            else:
                counter_clockwise = False
            return counter_clockwise

        return ccw(a1, b1, a2) != ccw(a1, b1, b2) and ccw(a2, b2, a1) != ccw(a2, b2, b1)

    def save_tracklog(self):
        # TODO-Clean up what is saved
        # save all tracks to tracks log dir

        # # Can't pickle the cv2.Tracker object, so delete it for now
        # for tracker in self.multitracker_record:
        #     del(tracker.Tracker)

        # In case program runs overnight without restarting we want to check
        # that the folder name reflects the day of the month
        nowish = datetime.now()
        if not self.tracks_log_dir.stem == nowish.strftime('%d'):
            self.tracks_log_dir = startup_checks.track_log_filepaths(self.parameters['Sensor_ID'])
        if not self.skimage_logDir.stem == nowish.strftime('%d'):
            self.skimage_logDir = startup_checks.skimage_log_filepaths(self.parameters['Sensor_ID'])

        track_filename = self.tracks_log_dir / (nowish.strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
                                                + '_Skiers_crossed_is_'
                                                + str(len(self.list_of_crossings))
                                                + '.pickle')

        with open(track_filename, "wb") as f:
            pickle.dump(self.multitracker_record, f, pickle.HIGHEST_PROTOCOL)

        # Reset record to currently existing tracks. This will result in some overlap, but better that
        # losing data by breaking up the tracks that exist in both the old and new records
        self.multitracker_record = self.multi_tracker

    def save_skimage_log(self):
        # Write SKIMAGE log
        nowish = datetime.now()
        datestr = datetime.now().strftime('%d/%m/%Y')
        timestr = datetime.now().strftime('%H:%M:%S:%f')[:-3]

        if len(self.list_of_crossings) == 0:
            total_skiers = int(0)
        else:
            totals = []
            keys = []
            self.list_of_crossings
            for i in range(len(self.cut_lines)):
                key = 'skiers_passed_cutline_' + str(i)
                total = self.list_of_crossings[key].sum()
                keys.append(key)
                totals.append(int(total))

            total_skiers = max(totals)
            idx_max = np.argmax(totals)
            for idx, key in enumerate(keys):
                if idx == idx_max:
                    self.list_of_crossings['skiers_passed'] = self.list_of_crossings[key]
                self.list_of_crossings = self.list_of_crossings.drop(columns=key)

        # Todo: Get rid of the lines with zero skiers, clean up above
        total_row = pd.Series(
            {'sensorID': str(self.sensor_id),
             'date': datestr,
             'time': timestr,
             'cut_period': int((time.time() - self.time_last_skimage_log) * 1000),  # millisecs since last log
             'voltage1': '',
             'voltage2': '',
             'voltage3': '',
             'skiers_passed': total_skiers
             })

        self.list_of_crossings = self.list_of_crossings.append(total_row, ignore_index=True)
        self.list_of_crossings.skiers_passed.astype(int)
        self.list_of_crossings.cut_period.astype(int)

        skimage_log_name = self.skimage_logDir / (nowish.strftime("%Y%m%d_%H%M")
                                                  + '_'
                                                  + str(self.parameters['Sensor_ID'])
                                                  + '.csv')

        self.list_of_crossings.to_csv(skimage_log_name,
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

        # Create copy of skimage log in folder that is scanned by the send to ftp function 'monitor_logging'
        shutil.copy(skimage_log_name, self.skimage_logToFTP)

        # Reset SKIMAGE dataframe
        self.list_of_crossings = pd.DataFrame()
        core_logger.info('SKIMAGE log written from sensor: ' + str(self.sensor_id))

    def do_recording(self):
        # Update multitracker_record
        # List of all existing trackers in record
        uuids_extant = [tracker.UUID for tracker in self.multitracker_record]

        # Loop through updated multitracker list
        # If a tracker already exists in multitracker_record we update it
        # If not we add the new tracker to the multitracker_record
        for tracker in self.multi_tracker:
            if tracker.UUID in uuids_extant:
                # replace
                idx = uuids_extant.index(tracker.UUID)
                self.multitracker_record[idx] = tracker
            else:
                self.multitracker_record.append(tracker)

        # Initialize counter for this loop
        count = 0

        for tracker in self.multi_tracker:
            if tracker.Pos.size >= self.parameters['Valid_Min_Frames']:
                track_start = self.Point(tuple(tracker.Pos[-2, :])[0], tuple(tracker.Pos[-2, :])[1])
                track_stop = self.Point(tuple(tracker.Pos[-1, :])[0], tuple(tracker.Pos[-1, :])[1])

                # This makes sure that we don't count the track if the last two positions of the track are not valid
                # Todo: Clean this up, allow tracks that are valid before, valid after, but for whatever reason NOT valid at the line to still be counted
                if (tracker.Valid[-2:]).all():
                    # Check if track went over line
                    for idx, cut_line in enumerate(self.cut_lines):
                        # Check if any of the tracks crossed this line.
                        # We allow each track to cross each line only once
                        if tracker.UUID not in self.lists_of_trackers_counted[idx]:
                            a1 = track_start
                            b1 = track_stop

                            if self.has_crossed(a1, b1, cut_line.start, cut_line.stop):

                                # Count crossing at given cut line (idx)
                                self.count_crossings(idx)
                                self.lists_of_trackers_counted[idx].append(tracker.UUID)
                                count = count + 1

        # If time period specified in parameter file has elapsed, write the track log file
        if time.time() - self.time_last_track_log > self.parameters['Period_Track_Log']:
            self.save_tracklog()
            self.time_last_track_log = time.time()  # Reset timer

        # If time period specified in parameter file has elapsed, write the skimage log file
        if time.time() - self.time_last_skimage_log > self.parameters['Period_Skimage_Log']:
            self.save_skimage_log()
            self.time_last_skimage_log = time.time()  # Reset timer

        return count

    def manage_fps(self):

        def update_temporal_parameters(speed_factor):
            self.parameters['speedFactor'] = speed_factor
            self.parameters['stillValidMaxFrames'] = int(self.parameters['stillValidMaxFrames_full'] * speed_factor)
            self.parameters['validMinFrames'] = int(self.parameters['validMinFrames_full'] * speed_factor)

        def clear_sensor_buffers():
            if self.q_to_core.full():
                q_max_size = self.parameters['coreQueueSize']
                for i in range(q_max_size):
                    __ = self.q_to_core.get()

        if self.q_to_core.full():
            clear_sensor_buffers()

        almost_empty = 0.1
        almost_full = 0.9

        if self.processing_mode == 1:
            frame = self.q_to_core.get()

            if self.q_to_core.qsize() > almost_full * self.parameters['coreQueueSize']:
                # core_logger.info('Queue almost full on sensor ' + str(self.sensor_id)
                #                  + ', Reducing fps to half-speed ')
                self.processing_mode = 0.5
                update_temporal_parameters(0.5)

        elif self.processing_mode == 0.5:
            __ = self.q_to_core.get()
            frame = self.q_to_core.get()

            if self.q_to_core.qsize() > almost_full * self.parameters['coreQueueSize']:
                # core_logger.info('Queue almost full on sensor ' + str(self.sensor_id)
                #                  + ', Reducing fps to quarter-speed ')
                self.processing_mode = 0.25
                update_temporal_parameters(0.25)

            if self.q_to_core.qsize() < almost_empty * self.parameters['coreQueueSize']:
                # core_logger.info('Queue almost empty on sensor ' + str(self.sensor_id)
                #                  + ', increasing fps back to full-speed ')
                self.processing_mode = 1
                update_temporal_parameters(1)

        elif self.processing_mode == 0.25:
            __ = self.q_to_core.get()
            __ = self.q_to_core.get()
            frame = self.q_to_core.get()

            if self.q_to_core.qsize() < almost_empty * self.parameters['coreQueueSize']:
                # core_logger.info('Queue almost empty on sensor ' + str(self.sensor_id)
                #                  + ', increasing fps back to half-speed ')
                self.processing_mode = 0.5
                update_temporal_parameters(0.5)

            if self.q_to_core.qsize() > almost_full * self.parameters['coreQueueSize']:
                pass
                # core_logger.error('Queue almost full on sensor ' + str(self.sensor_id)
                #                   + ', but we can not reduce fps below quarter-speed!')

        return frame

    def parse_cpp_tracks(self):

        states = self.detect_and_track.get_multitracker_states()
        valids = self.detect_and_track.get_valids()
        track_ids = self.detect_and_track.get_uuids()
  
        color = [random.randint(0,255), random.randint(0,255), random.randint(0,255)]
        self.multi_tracker = []
        
        for idx, track_id in enumerate(track_ids):
            
            track_state = states[idx]
            x = track_state[:, 0]
            y = track_state[:, 1]
            size = track_state[:, 4]
            valids_track = np.asarray(valids[idx]) 
            
            track = Tracker(track_id, x, y , size, valids_track, color)
            self.multi_tracker.append(track)

    def update_im_size_params(self):
        self.parameters['Width_Image'] = self.image_size[1]
        self.parameters['Height_Image'] = self.image_size[0]

        return
    
    def camera_tracking_loop(self):
        """Process images in a loop.

        Extended description of function.

        Args:
            arg1 (int): Description of arg1
            arg2 (str): Description of arg2

        Returns:
            bool: Description of return value

        Note:
            A usage note.
        """


        core_logger.info('Starting tracking on camera ' + str(self.sensor_id))
        loop = 0
        srt = time.time()


        
        if self.debug_mode:
            try:
                import debugger
                debugger = debugger.PythonProcessor(self.parameters)
            except ImportError:
                core_logger.info('The \"Debug_Mode\" was set to true, but this is a' 
                                 ' production version of Skimage that does not allow'
                                 ' the debugging feature.')
                self.debug_mode = False
       
        while self.active:

            # Check the time, if station is closed loop until station opens
            if not self.business_hours():
                continue

            self.start_time = datetime.now()
            self.detect_and_track.process_frame()

            self.parse_cpp_tracks()
            
            if self.debug_mode:
                debugger.test()


            # # ****** Recording # ******
            self.do_recording()

        # proc_time = time.time() - srt
        # print(f'Processing time = {proc_time}')


# To profile run:
# python -B -m cProfile -o output.prof core.py
# then visualize with:
# snakeviz output.prof
# To profile memory usage run:
# mprof run python core.py
# the visualize with:
# mprof plot
