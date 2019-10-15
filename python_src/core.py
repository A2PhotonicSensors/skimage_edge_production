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
import time
import random
import os
import fnmatch
import ftplib
from threading import Thread, Condition
import io
import socketserver
from http import server

if os.uname().machine == 'x86_64':
    import Detect_and_Track_x86 as cpp_fun
else:
    import Detect_and_Track_ARM as cpp_fun

# Core program:
#   -Does object detection
#   -Does tracking
#   -Does counting

core_logger = logging.getLogger('skimage.core')

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing bufferoutput's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global activeStream
        time.sleep(1)
        activeStream = 1
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()   
        elif self.path == '/index.html': # Default
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                core_logger.warning('Removed streaming client %s: %s', self.client_address, str(e))
                activeStream = 0
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def setStreamPage(width,height):
    return """    <html>
    <head>
    <title>SkImage LiveStream</title>
    <link rel="shortcut icon" href="#" />
    </head>
    <body>
    <img src="stream.mjpg" width="{}" height="{}" />
    </body>
    </html>
    """.format(str(width),str(height))

def streamForever():
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()

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
        # self.multi_tracker_py = []
        self.list_of_crossings = pd.DataFrame()
        self.lists_of_trackers_counted = []
        self.multitracker_record = []
        self.skiers_passed = []

        self.station_is_open = True

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
        self.detect_and_track.initialize_camera()
        self.detect_and_track.setup_RoI(parameters['ROI'])

        if self.detect_and_track.isValidHardware:
            core_logger.info("Hardware validation successful")
        else:
            core_logger.critical("Hardware validation failed. Counting disabled.")

        global output, PAGE, activeStream
        activeStream = 0
        PAGE = setStreamPage(self.parameters['Width_Image'],2*self.parameters['Height_Image'])
        output = StreamingOutput()
        streamThread = Thread(target=streamForever,daemon=True)
        streamThread.start()

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
            do_tracking = True
        else:
            do_tracking = False

        # If station has just opened or just closed then log change
        if not do_tracking == self.station_is_open:
            self.station_is_open = do_tracking
            if not do_tracking:
                core_logger.info('Station is closed, stopping tracking on sensor: ' 
                                 + str(self.sensor_id)
                                 + ' and quitting Skimage, see you tomorrow!')

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

        if len(self.list_of_crossings) == 0:
            total_skiers = int(0)
        else:
            totals = []
            keys = []
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

            # Get rid of the lines with zero skiers
            self.list_of_crossings = self.list_of_crossings[self.list_of_crossings.skiers_passed != 0]
            
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

        # # Create copy of skimage log in folder that is scanned by the send to ftp function 'monitor_logging'
        # shutil.copy(skimage_log_name, self.skimage_logToFTP)
        # core_logger.info('SKIMAGE log written from sensor: ' + str(self.sensor_id))
        
        # Reset SKIMAGE dataframe
        self.list_of_crossings = pd.DataFrame()
        self.infoStr += ': ' + str(total_skiers) + ' skiers passed'
        
        # Send the local to remote FTP server
        self.sendToFTP(skimage_log_name)

    def sendToFTP(self,filename):
        server = self.parameters['FTP_Path']
        username = 'skiflux'
        password = 'Sk1Flux.'
        try:
            with ftplib.FTP(server, username, password, timeout=2) as ftp:
                ftp.cwd('/')
                fh = open(filename, 'rb')
                ftp.storbinary('STOR ' + filename.name, fh)
                fh.close()
                self.infoStr += ' and log has been successfully uploaded to FTP.'
                # os.remove(filename)
        except Exception as error:
            self.infoStr += ' but FTP server cannot be reached: ' + str(error)
        return

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

        for tracker in self.multi_tracker:
            # If the track is longer than Valid_Min_Frames
            if tracker.Valid.size >= self.parameters['Valid_Min_Frames']:
                # Last 2 positions
                track_start = self.Point(tracker.Pos[0,-2], tracker.Pos[1, -2])
                track_stop = self.Point(tracker.Pos[0,-1], tracker.Pos[1, -1])

                # This makes sure that we don't count the track if the last two positions of the track are not valid
                # Todo: Clean this up, allow tracks that are valid before, valid after, but for whatever reason NOT valid at the line to still be counted
                if (tracker.Valid[-2:]).all():
                    # Check if track went over line
                    for idx, cut_line in enumerate(self.cut_lines):
                        # Check if any of the tracks crossed this line.
                        # We allow each track to cross each line only once
                        if tracker.UUID not in self.lists_of_trackers_counted[idx]:
                            if self.has_crossed(track_start, track_stop, cut_line):
                                # Count crossing at given cut line (idx)
                                self.count_crossings(idx)
                                self.lists_of_trackers_counted[idx].append(tracker.UUID)

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
        valids = self.detect_and_track.get_valids()
        track_ids = self.detect_and_track.get_uuids()
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


    def stream_video(self):
        self.detect_and_track.activeStream = activeStream
        if activeStream == 0:
            return
        else:
            encoded_im = np.array(self.detect_and_track.im_buf, dtype='uint8', copy=False)
            output.write(encoded_im.tobytes())


    def camera_tracking_loop(self):
        core_logger.info('Starting tracking on odroid ' + str(self.sensor_id))

        if self.debug_mode:
            try:
                import debugger
                debugger = debugger.PythonProcessor(self.parameters)
            except ImportError:
                core_logger.info('The \"Debug_Mode\" was set to true, but this is a' 
                                 ' production version of Skimage that does not allow'
                                 ' the debugging feature.')
                self.debug_mode = False

        while self.station_is_open:
            start_time = datetime.now()
            ret = self.detect_and_track.process_frame()
            if ret:
                core_logger.info('No more frames available, quitting skimage.')
                break

            self.parse_cpp_tracks()

            if self.debug_mode:
                debugger.test()

            # # ****** Recording # ******
            self.do_recording()

            self.stream_video()

            self.nb_processed_frames +=1
            # proc_time = datetime.now() - start_time
            # core_logger.info(str(1/proc_time.microseconds*1e6)[:4] + ' FPS')


# To profile run:
# python -B -m cProfile -o output.prof core.py
# then visualize with:
# snakeviz output.prof
# To profile memory usage run:
# mprof run python core.py
# the visualize with:
# mprof plot
