# -*- encoding: utf-8 -*-

# Local skimage modules
import startup_checks
import logs_skimage
import parameter_parser
# import images_acquisition
import core
import argparse

# External modules
import logging

# Initialize logger
logger = logging.getLogger('skimage')
logger.info('Starting Skimage v1.3')

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--ID", required=False, help="ID to look for")
args = vars(ap.parse_args())

if args["ID"]:
    with open('data/my_id.txt', 'w') as f:
        f.write(args["ID"])
        logger.info('Overwriting my_id.txt with ' + args["ID"])


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



