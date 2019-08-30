# -*- encoding: utf-8 -*-
import pandas
from pathlib import Path
import numpy as np
import logging
from str2bool import str2bool
import sys
from datetime import datetime
import pickle
import os

param_logger = logging.getLogger('skimage.parameter_parser')

class param_type_error(BaseException):
    pass

def checkvalid_boolean(var_str):
    # Helper function to verify that the parameter that should be a boolean
    # can indeed be converted from a string (read from the file) to a boolean.
    #
    # The function str2bool converts common strings (like 'True', 'true', 't',
    # 'False', etc) to boolean. If the input string is not valid (for list of all
    # valid inputs see https://github.com/symonsoft/str2bool) the function
    # returns nothing and does not throw an exception.
    if var_str:
        var_str = str(var_str)
        try:
            var = str2bool(var_str.lower())
             # Because str2bool returns nothing if there is invalid input
             #    we have to check if var is a boolean
            assert isinstance(var, bool), (['"'
                                            + str(var_str)
                                            + '"'
                                            + ' parameter can not be converted to'
                                            + ' a boolean: Verify parameter file'])
            return var
        except Exception as e:
            param_logger.exception(e)

    else:
        return None

def checkvalid_int(var_str):
    # Helper function to verify that the parameter that should be an integer
    # can indeed be converted from a string (read from the file) to an integer.
    if var_str:
        try:
            var = abs(int(var_str))
            return var
        except Exception as e:
            param_logger.exception(e)
            param_logger.exception(var_str + ' is not a valid input')
            param_logger.exception('Verify that the parameter is an integer')
    else:
        return var_str

def checkvalid_float(var_str):
    # Helper function to verify that the parameter that should be a positive float
    # can indeed be converted from a string (read from the file) to a positive.
    if var_str:
        try:
            var = abs(float(var_str))
            return var
        except Exception as e:
            param_logger.exception(e)
            param_logger.exception(var_str + ' is not a valid input')
            param_logger.exception('Verify that the parameter is a float')
    else:
        return var_str

def check_valid_list_of_points(var_str):

    # Helper function to verify that the input string can be evaluated as a list of 
    # two element lists, each defining a point of boundary of the RoI in 
    # normalized image coordinates
    if var_str:
        try:
            var = eval(var_str)
            try:
                if not type(var) == list:
                    raise param_type_error
                for item in var:
                    if not (type(item) == list and len(item) == 2):
                        raise param_type_error
        
            except param_type_error as e1:
                param_logger.exception(e1)
                param_logger.exception(var_str + ' is not a valid input')
                param_logger.exception('Verify that the ROI parameter in the spreadsheet'
                                       'has the form: [[x1, y1], [x2, y2], etc. ]')
                exit(1)
        except param_type_error as e:
            param_logger.exception(e)
            param_logger.exception(var_str + ' is not a valid input for eval')
            param_logger.exception('Verify that the ROI parameter in the spreadsheet'
                                   'has the form: [[x1, y1], [x2, y2], etc.]')
            exit(1)
        
        return var_str

def checkvalid_list_of_tuples(var_str):
    # Helper function to verify that string evaluates to list of tuples
    # E. g. cut line parameter returns a list of two tuples (start point and stop point)
    # If string is empty we continue
    if var_str:
        try:
            var = eval(var_str)
            try:
                assert type(var) == list
                for item in var:
                    assert type(item) == tuple
                return var_str
            except Exception as e1:
                param_logger.exception(e1)
                param_logger.exception(var_str + ' is not a valid input')
                param_logger.exception('Verify that the cut line parameter in the spreadsheet'
                                       'has the form: [(x1, y1), (x2, y2)]')
        except Exception as e:
            param_logger.exception(e)
            param_logger.exception(var_str + ' is not a valid input for eval')
            param_logger.exception('Verify that the cut line parameter in the spreadsheet'
                                   'has the form: [(x1, y1), (x2, y2)]')
    else:
        return None

def checkvalid_list_of_times(var_str):
    # Helper function to verify that string evaluates to list of valid times
    # If string is empty we continue
    if var_str:
        try:
            var = eval(var_str)
            try:
                assert type(var) == list
                for item in var:
                    datetime.strptime(item, '%H:%M')
                return var_str
            except ValueError:
                param_logger.exception(var_str + ' does not evaluate to a list of times of the form "HH:MM"')

        except Exception:
            param_logger.exception(var_str + ' is not a valid input for eval')
            param_logger.exception('Verify that the list of times in the spreadsheet \n'
                                   'has the form: [\'%H:%M\', \'%H:%M\']')
    else:
        return None

def checkvalid_string(var_str):
    var_str = str(var_str)

    if var_str == 'sensorLabel':
        return var_str

    elif var_str == 'sensorType':
        if var_str == 'camera':
            return var_str
        elif var_str == 'radar':
            return var_str
        else:
            param_logger.exception(var_str + ' must be either "camera" or "radar". Check parameter file!')
            return None

    elif var_str == 'sensorPath':
        return var_str

    elif var_str == 'trackerClass':
        if var_str == 'KTracker':
            return var_str
        elif var_str == 'CTracker':
            return var_str
        else:
            param_logger.exception(var_str + ' must be either "KTracker" or "CTracker". Check parameter file!')
            return None
    else:
        return var_str

def compose_camera_url(params):


    root_url = params['Camera_Path']

    # Allow for local videos
    file_path = Path(root_url)
    if file_path.is_file():
        full_url = root_url

    else:
        w_im = params['Width_Image']
        h_im = params['Height_Image']
        fps = params['FPS']
        full_url = f'{root_url}?resolution={w_im}x{h_im}&fps={fps}'
    
    params.update({'Camera_Path': full_url})

    return params

def dimensionalize_parameters(params):

    def get_max_distance(params):
        # Returns maxDistance in number of pixels (integer)
        # Redimensionalized by typical length scale sqrt(w*h)
        length_scale = np.sqrt(params['Width_Image'] * params['Height_Image'] )
        max_distance = int(params['Max_Distance_Norm'] * length_scale)
        return max_distance

    def get_filter_size(params):
        # Returns filterSize in number of pixels (integer)
        # Redimensionalized by typical length scale sqrt(w*h)
        length_scale = np.sqrt(params['Width_Image'] * params['Height_Image'] )
        filter_size_raw = params['Filter_Size_Norm'] * length_scale

        #Ensure that filterSize is an odd integer
        if np.ceil(filter_size_raw) % 2 == 0:
            filter_size = int(np.floor(filter_size_raw))
        else:
            filter_size = int(np.ceil(filter_size_raw))
        return filter_size

    def get_max_blob_size(params):
        # Returns maxBlobSize in number of pixels (integer)
        max_blob_size = int(params['Max_Blob_Size_Norm'] 
                            * params['Width_Image'] * params['Height_Image'])
        return max_blob_size

    def get_min_blob_size(params):
        # Returns minBlobSize in number of pixels (integer)
        min_blob_size = int(params['Min_Blob_Size_Norm'] 
                            * params['Width_Image'] * params['Height_Image'])
        return min_blob_size

    def get_still_valid_max_frames(params):
        # Return stillValidMaxFrames in number of frames (integer)
        still_valid_max_frames =  int(params['Still_Valid_Max_Frames_Norm'] * params['FPS'])
        return still_valid_max_frames

    def get_valid_min_frames(params):
        # Return validMinFrames in number of frames (integer)
        valid_min_frames = int(params['Valid_Min_Frames_Norm'] * params['FPS'])
        return valid_min_frames

    def get_roi(params):
        # Returns list of two element lists, each defining a point of boundary of the RoI in 
        # normalized image coordinates
        if params['ROI']:
            roi_list = eval(params['ROI'])
        else:
            roi_list = [[0,0], [0,1], [1,1], [1,0]]
        return roi_list
        
    def get_cut_line(params, cut_line_string ):
        # Returns list of two element lists, each defining a point of boundary of the RoI in 
        # normalized image coordinates
        if params[cut_line_string]:
            cut_line = eval(params[cut_line_string])
        else:
            cut_line = []
        return cut_line

    # Factor used to change processing variables related to changing fps,(e.g. if we
    # have to reduce the fps in half because of slow processing we can change the speed factor to 0.5
    speed_factor = 1
    params.update({'Speed_Factor': speed_factor})

    still_valid_max_frames_full = get_still_valid_max_frames(params)
    params.update({'Still_Valid_Max_Frames': int(still_valid_max_frames_full * speed_factor)})

    valid_min_frames_full = get_valid_min_frames(params)
    params.update({'Valid_Min_Frames': int(valid_min_frames_full * speed_factor)})

    max_distance = get_max_distance(params)
    params.update({'Max_Distance': max_distance})

    filter_size = get_filter_size(params)
    params.update({'Filter_Size': filter_size})

    max_blob_size = get_max_blob_size(params)
    params.update({'Max_Blob_Size': max_blob_size})

    min_blob_size = get_min_blob_size(params)
    params.update({'Min_Blob_Size': min_blob_size})

    roi = get_roi(params)
    params.update({'ROI': roi})

    for i in range(1,5):
        cut_line_string = 'Cut_Line' + str(i)
        cut_line = get_cut_line(params, cut_line_string)
        params.update({cut_line_string: cut_line})
        
    return params

def check_display(params):

    display = os.environ.get('DISPLAY')
    param_logger.info('$DISPLAY=' + str(display))
    
    if not display:
        param_logger.info('$DISPLAY is not found on system, setting Display_Mode to false')
        params.update({'Display_Mode': False})
    
    return params

def get_parameters_all(param_filename):

    # Enforce data types in parameter spreadsheet
    converters_dict = {
                       # Progam options
                       'Debug_Mode': checkvalid_boolean,
                       'Display_Mode': checkvalid_boolean,
                       # Camera parameters
                       'Sensor_ID': checkvalid_int,
                       'Sensor_Label': checkvalid_string,
                       'Camera_Path': checkvalid_string,
                       # Camera options
                       'Width_Image': checkvalid_int,
                       'Height_Image': checkvalid_int,
                       'FPS': checkvalid_int,
                       #Region of interest and counting lines
                       'ROI': check_valid_list_of_points,
                       'Cut_Line1': check_valid_list_of_points,
                       'Cut_Line2': check_valid_list_of_points,
                       'Cut_Line3': check_valid_list_of_points,
                       'Cut_Line4': check_valid_list_of_points,
                       #  Logging parameters
                       'Tracking_Start_Daily': checkvalid_int,
                       'Tracking_Stop_Daily': checkvalid_int,
                       'Period_Skimage_Log': checkvalid_int,
                       'Save_Tracks': checkvalid_boolean,
                       'Period_Track_Log': checkvalid_int,
                       # Saved video clips
                       'Save_Video_Frames': checkvalid_int,
                       'Times_Video_Save': checkvalid_list_of_times,
                       # Image processing parameters
                       'Background_Contrast': checkvalid_int,
                       'Background_History': checkvalid_int,
                       'Detect_Shadows': checkvalid_boolean,
                       'Filter_Size_Norm': checkvalid_float,
                       'Min_Blob_Size_Norm': checkvalid_float,
                       'Max_Blob_Size_Norm': checkvalid_float,
                       # Tracking parameters
                       'Still_Valid_Max_Frames_Norm': checkvalid_float,
                       'Max_Distance_Norm': checkvalid_float,
                       'Valid_Min_Frames_Norm': checkvalid_float
                       }

    # Load spreadsheet, ref:
    # https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_excel.html



    # First we need to find the last row of the list of active sensors
    # Read in first column of spreadsheet:
    df_first_column = pandas.read_excel(param_filename,
                                        sheet_name=0,
                                        squeeze=True,
                                        header=0,
                                        usecols=[0,0])

    # Find the row where 'END' is in the first column, if not found stop, throw error
    try:
        cutoff = df_first_column[df_first_column == 'END'].index[0] 
    except Exception as e:
        param_logger.critical(str(e) + '\n' +
                              ' Attention, "END" not found in the first column of the parameter spreadsheet. \n'
                              ' Please open the spreadsheet and write "END" in the first column on the row after'
                              ' the last sensor that will be monitored by SKIMAGE \n'
                              ' Exiting the program \n')
        sys.exit(0)

    df = pandas.read_excel(param_filename,
                           sheet_name='All',
                           header=0,
                           usecols=None,
                           nrows=cutoff,
                           squeeze=False,
                           dtype=None,
                           engine=None,
                           converters=converters_dict,
                           true_values=None,
                           false_values=None,
                           skiprows=0,
                           na_values=None,
                           parse_dates=False,
                           date_parser=None,
                           thousands=None,
                           comment=None,
                           skipfooter=0,
                           convert_float=True
                           )

    parameters_all = df.to_dict(orient='records')

    return parameters_all

def get_parameters(param_filename = 'data/skimage_parameters.xlsx',
                  param_pickled_filename = 'data/skimage_parameters.pickle',
                  get_all_params = False):
    
    # If get_all_params flag is set to true we read the exel file and return 
    # all of the parameters
    if get_all_params:
        parameters_all = get_parameters_all(param_filename)
        return parameters_all
    
    # Fast loader, returns parameters from pickled file if the pickled file was saved
    # at a later time than the spreadsheet. Skips loading from spreadsheet
    if Path(param_pickled_filename).exists():
        pickled_params_mtime = Path(param_pickled_filename).stat().st_mtime
        params_mtime = Path(param_filename).stat().st_mtime
        if pickled_params_mtime > params_mtime:
            param_logger.info('Loading pickled parameters from previous session')
            with open(param_pickled_filename, 'rb') as f:
                parameters = pickle.load(f)

            parameters = check_display(parameters)
            return parameters
        else:
            param_logger.info(param_filename + 
                              ' was recently saved, so parameters will be loaded from this file')
    else:
        param_logger.info(param_pickled_filename + 
                          ' not found, loading parameters from '
                          + param_filename)

    
    # First, check that we have a vaild my_id.txt file and read in the id
    try:
        with open('data/my_id.txt', 'r') as f:
            my_id = int(f.read())

    except IOError:
        param_logger.critical('The file "data/my_id.txt" was not found. \n'
                              'Please ensure that this file exists, and contains a string \n'
                              'corresponding to one of the Sensor_ID\'s found in the \n' 
                              'skimage_parameters.xlsx spreadsheet')
        sys.exit(0)

    # Now get all the parameters
    parameters_all = get_parameters_all(param_filename)

    # Select the parameters corresponding to my_id
    parameters = {}
    for params in parameters_all:
        if params['Sensor_ID'] == my_id:
            parameters = params
            break
    if not parameters:
        param_logger.critical('No set of parameters were found that match the sensor ID: ' 
                               + str(my_id) + ' \n'
                               + 'Please confirm that "data/my_id.txt" contains on of the Sensor_ID\'s \n'
                               + 'found in the "data/skimage_parameters.xlsx"')
        sys.exit(0)

    parameters = compose_camera_url(parameters)
    parameters = dimensionalize_parameters(parameters)

    with open(param_pickled_filename, 'wb') as f:
        pickle.dump(parameters, f)

    parameters = check_display(parameters)
    return parameters

if __name__ == '__main__':
    param_filename = '/home/data/skimage_parameters.xlsx'
    parameters = get_parameters(param_filename)
