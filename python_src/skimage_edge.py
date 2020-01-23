# -*- encoding: utf-8 -*-

# Local skimage modules
import startup_checks
import logs_skimage
import parameter_parser
# import images_acquisition
import core

# External modules
import logging

# Initialize logger
logger = logging.getLogger('skimage')
logger.info('Starting Skimage v1.2')

# ****** Start up checks/get parameters ******
# Check file structure
file_paths = startup_checks.check_filesystem()

# Load parameters
parameters = parameter_parser.get_parameters()

if parameters['Debug_Mode']:
    print('Skimage starting in debug mode')
    

# ****** Start core processing ******
camera_core = core.CameraCore(parameters)

camera_core.camera_tracking_loop()



