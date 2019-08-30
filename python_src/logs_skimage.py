# coding: utf-8
import logging
from datetime import datetime
import os
from pathlib import Path

# create logger
logger = logging.getLogger('skimage')
logger.setLevel(logging.DEBUG)

# create file handler which logs to file
logfile_dir = Path.cwd() / 'Logs_program'
if not logfile_dir.is_dir():
    os.mkdir(logfile_dir)
logfile_name = logfile_dir / (
                    'Skimage_program-'
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
logger.addHandler(fh)
logger.addHandler(ch)



