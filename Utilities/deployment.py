# Python script to install and/or update Skimage 

# Options:
#   1) Full install from scratch
#   2) Update docker image
#   3) Update all source code
#   4) Update parameter files only

# The selected option will be performed on all the Odroids listed in the parameter file

# All Odroids in network should have hard-coded login:password "odroid:odroid"
import urllib.request
import git
import sys
import os
import subprocess
import paramiko
import logging 
from pathlib import Path
import datetime
import time 

import python_src.parameter_parser as parameter_parser
from python_src.startup_checks import check_ping, get_my_ip


logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')


class Odroid:
    def __init__(self):

        self.user = os.environ['USER_ALL']
        self.password = os.environ['PASSWORD_ALL']
        self.timezone = os.environ['TZ']
        self.source_folder = os.environ['ROOT_DIR'] + '/' + os.environ['SOURCE_DIR'] 
        self.skimage_log_link_folder = os.environ['ROOT_DIR'] + '/' + os.environ['SKIMAGE_LOGS_LINK'] 
        self.docker_image_name = os.environ['DOCKER_IMAGE'] 

class RemoteOdroid(Odroid):
    def __init__(self, parameters):
        super().__init__()

        self.sensor_id = str(parameters['Sensor_ID'])
        self.sensor_label = parameters['Sensor_Label']
        self.ip_address = parameters['Odroid_Path']
        self.port = 22
        self.ping_status = check_ping(self.ip_address)
        if self.ip_address == '185.195.249.162':
            self.port = 43206
            self.ping_status['ping_status'] = True
        
        self.ssh_client = []
        self.seconds_difference_from_master = []
        self.internet_connection = False

    def establish_ssh_connection(self):
        try:
            logging.info('Establishing SSH connection to ' 
                        + self.user + '@' 
                        + self.ip_address + ' . . . ')

            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=self.ip_address,
                                    username=self.user,
                                    password=self.password,
                                    port=self.port,
                                    timeout=10)

            logging.info('SSH connection established')

        except:
            logging.critical('Unable to connect to ' + self.ip_address + ' via SSH\n')
            self.ssh_client = []
    
    def copy_parameter_file(self):
        # Copy parameter file to remote Odroid
        parameter_filepath = self.source_folder + '/data/skimage_parameters.xlsx'
        parameter_pickle_filepath = self.source_folder + '/data/skimage_parameters.pickle'
        try:
            logging.info('Removing old versions of the parameter file . . . ')
            self.send_ssh_command('rm -f ' + parameter_filepath + ' ' + parameter_pickle_filepath)
        except:
            logging.warning('Error in deleting old versions of the parameter file on the remote Odroid')
        
        self.send_ssh_command('mkdir -p ' + self.source_folder + '/data')

        try:
            ftp_client=self.ssh_client.open_sftp()
            logging.info('Copying local version of parameter file to remote Odroid ' + self.ip_address)
            ftp_client.put('/home/data/skimage_parameters.xlsx', parameter_filepath)
            ftp_client.close()
        except:
            logging.warning('Error in copying parameter file to remote Odroid ' + self.ip_address)

    def write_my_id(self):
        # Create or overwrite (linux command ">") my_id.txt file.
        # Contains the last three numbers of the ip address

        my_id_filename = self.source_folder + '/data/my_id.txt'
        my_id = self.sensor_id
        try:
            logging.info('Writing the my_id.txt file to the remote Odroid ' + self.ip_address)
            self.send_ssh_command('sudo sh -c \"echo ' + str(my_id) + ' > ' + my_id_filename + '\"')
            logging.info('my_id.txt written successfully')
        except:
            logging.warning('Error in writing to the my_id.txt file on the remote Odroid')
        
    def update_source_code(self):
    
        def resolve_remote_path(path_object):
            # Get full local path to object minus the root '/home'
            relative_local_path = path_object.relative_to('/home')
            
            # Create Path object from source_folder string
            remote_root = Path(self.source_folder)

            # Join the remote root and the relative local path
            remote_path = remote_root.joinpath(relative_local_path)

            # Return the full remote path as a string
            return remote_path.as_posix()

        def check_for_names_to_skip(path_object):
            skip = False # By default do not skip

            # Hard code the beginnings of names of files/folder to skip
            forbidden_beginnings = ['.', 'Logs', '__', 'semaphore', 'data']
            for forbidden_beginning in forbidden_beginnings:
                len_forbidden = len(forbidden_beginning)

                # Check that the beginning of the name of the file/folder doesn't start with a
                # forbidden beginning 
                if path_object.name[0:len_forbidden] == forbidden_beginning:
                    skip = True
            
            return skip

        def copy_files(ftp_client, source_file):
            if check_for_names_to_skip(source_file):
                logging.info('Skipping ' + source_file.name )
                return
            remote_filepath = resolve_remote_path(source_file)
            logging.info('Copying ' + remote_filepath + ' to remote odroid')
            ftp_client.put(source_file.resolve().as_posix(), remote_filepath)

            return

        def copy_folders(ftp_client, source_subfolder):
            if check_for_names_to_skip(source_subfolder):
                logging.info('Skipping ' + source_subfolder.name )
                return
            remote_folder = resolve_remote_path(source_subfolder)
            logging.info(' Creating folder ' + remote_folder + ' on remote odroid')
            ftp_client.mkdir(remote_folder)
            
            for path_object in source_subfolder.iterdir():
                if path_object.is_file():
                    copy_files(ftp_client, path_object)
                elif path_object.is_dir():
                    copy_folders(ftp_client, path_object)
                else:
                    logging.warning('Path object '  + path_object.name + ' was not copied to remote Odroid')
            return

        try:
            self.send_ssh_command('mkdir -p ' + self.source_folder)
        except:
            logging.warning('Error in creating ' + self.source_folder)

        # Delete source code folder on remote, preserving log folders
        try:
            self.send_ssh_command('cd '+ self.source_folder + ' ; sudo find * -not \( -path \'Logs_*\' -o -path \'data*\' \) -delete')
        except:
            logging.warning('Error in deleting the source folder on the remote machine')

        # Copy local source code file to remote (except logs folders)
        try:
            ftp_client=self.ssh_client.open_sftp()

            # Loop through contents
            local_root_path = Path('/home')
            for path_object in local_root_path.glob('*'):

                if path_object.is_file():
                    copy_files(ftp_client,path_object)
                
                elif path_object.is_dir():
                    copy_folders(ftp_client, path_object)

                else:
                    logging.warning('Path object '  + path_object.name + ' was not copied to remote odroid')

            ftp_client.close()

        except:
            
            logging.warning('Error in copying source folder to remote odroid')
  
    def setup_systemd(self):
        # After an update of the source code this resets the systemd service

        try:
        # Copy the skimage_watchdog.service file to correct location
            relative_service_filepath = 'Utilities/skimage_watchdog.service'
            source_filepath = Path(self.source_folder).joinpath(relative_service_filepath)
            
            self.send_ssh_command('sudo cp ' + source_filepath.as_posix() + ' ' + '/lib/systemd/system')

            # Give execute permission over the skimage script
            self.send_ssh_command('chmod +x ' + self.source_folder + '/skimage.sh')

            # Reload systemd daemon
            self.send_ssh_command('sudo systemctl daemon-reload')

            # Enable systemd service
            self.send_ssh_command('sudo systemctl enable skimage_watchdog.service')
            logging.info('skimage_watchdog systemd service configured successfully')

        except:
            logging.warning('Error in configuring skimage_watchdog systemd service!')
        
    def make_skimage_logs_link(self):
        # Check that Logs_SKIMAGE folder exists, if not, create it
        # Check that soft link to home/odroid/Logs_SKIMAGE, if not, create it
        logs_file_path = self.source_folder + '/Logs_SKIMAGE'

        try:
            self.send_ssh_command('mkdir -p ' + logs_file_path)
            self.send_ssh_command('ln -sf ' + logs_file_path + ' ' + self.skimage_log_link_folder)
        
            logging.info('Skimage logs folder checks passed')
        except:
            logging.warning('Error in skimage logs folder checks')
    
    def set_timezone(self):
        # set timezone
        try:
            self.send_ssh_command('sudo timedatectl set-timezone ' + self.timezone)
            logging.info('Successfully set time zone to ' + self.timezone + ' on remote odroid')

        except:
            logging.warning('Error in setting time zone on remote odroid!')
    
    def compare_datetimes(self):

        try:
            stdin, stdout, stderr = self.ssh_client.exec_command('date --iso-8601=\'seconds\'')
            nowish = datetime.datetime.now()
            remote_time_list = stdout.readlines()
            remote_time_string = remote_time_list[0]
            remote_time_string = remote_time_string[0:-7] # Get rid of timezone info 

            remote_time_object = datetime.datetime.strptime(remote_time_string, '%Y-%m-%dT%H:%M:%S')

            time_difference = nowish - remote_time_object

            self.seconds_difference_from_master = time_difference.total_seconds()

            logging.info('Local odroid time is ' + nowish.strftime('%Y-%m-%dT%H:%M:%S')) 
            logging.info('Remote odroid time is ' + remote_time_string )

            if abs(self.seconds_difference_from_master) > 300:
                logging.warning('Remote odroid clock is different from local odroid clock by ' 
                            + str(self.seconds_difference_from_master) + ' seconds, over 5 minutes!')

            else:
                logging.info('Remote odroid clock is different from local odroid clock by ' 
                            + str(self.seconds_difference_from_master) + ' seconds')
        except:

            logging.warning('Error in comparing date and time between local and remote odroids')
  
    # def update_docker_image(self):
    #     # Copy zipped docker image to remote
    #     # Load docker image on remote
    #     pass

    def reboot_remote(self):
        # Reboot remote odroid
        try:
            logging.info('Reboot remote odroid')
            self.send_ssh_command('sudo reboot now')
        except:
            logging.warning('Failed to reboot remote odroid')

    def fresh_install(self):
        # A fresh install requires only that the remote odroid has the factory OS and an internet connection
        self.send_ssh_command('sudo rm -rf ' + self.source_folder)
        self.send_ssh_command('mkdir -p ' + self.source_folder + '/Utilities')

        ftp_client=self.ssh_client.open_sftp()
        ftp_client.put('/home/Utilities/install.sh', self.source_folder + '/Utilities/install.sh')
        ftp_client.put('/home/Utilities/skimage_variables.env', self.source_folder + '/Utilities/skimage_variables.env')
        logging.info('Successfully copied environment variables and installation script')
        ftp_client.close()

        logging.info('Starting the fresh install script')
        self.send_ssh_command('chmod +x ' + self.source_folder + '/Utilities/install.sh')                                                   
        self.send_ssh_command('bash ' + self.source_folder + '/Utilities/install.sh ' + self.source_folder)
        logging.info('Fresh install script has finished on the remote odroid')

    def send_ssh_command(self, cmd):
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd + ' 2>&1', get_pty=True)
        
        if cmd.find('sudo') != -1:
            stdin.write(self.password + '\n')

        while not stdout.channel.exit_status_ready():
            info = stdout.readline().rstrip('\n')
            if info:
                if info.startswith('After this operation'):
                    stdin.write('Y\n')
                if info.startswith('Sudo-ing'):
                    stdin.write(self.password + '\n')
                if info.startswith(self.password):
                    continue
                if info.startswith('[sudo]'):
                    continue
                logging.info(info)

class MasterOdroid(Odroid):
    def __init__(self, option):
        super().__init__()

        self.do_fresh_install = False
        # self.do_update_docker_image = False
        self.do_update_source_folder = False
        self.do_update_parameters = False

        self.deployment_option = option

        self.internet_connection = False
        self.test_internet_connection()
        if self.internet_connection:
            self.pull_source_code()

        self.parameters_all = []
        self.remote_odroids = {}
        self.ip_address = get_my_ip()
        self.get_remote_odroids()

    def test_internet_connection(self):
        # Test internet connection, warn that we can't pull latest Docker
        # image or source code from repos w/o internet
        try:
            logging.info('Testing internet connection . . . ')
            response = urllib.request.urlopen('https://www.google.com/', timeout=1)
            logging.info('Internet connection found')
            self.internet_connection =True

        except:
            logging.warning('No internet connection found! '
            + 'Updating with local files. '
            + 'Remember to synchronize the source code with the Github repo as soon as possible') 
            self.internet_connection = False

    def pull_source_code(self):
        # Attempt to pull source code from Github, warn if not possible
        try:
            logging.info('Pulling latest version of source code from github . . . ')
            git_repo = git.Repo('/home/')
            git_repo.remotes.origin.pull()
            logging.info('Pull successful, source code is synchronized with github')
        except:
            logging.warning('Unable to pull latest version of code from the github repository')
        
    def get_remote_odroids(self):
        # Load parameter file and get list of odroid's ip address
        # ping each ip and report results
        logging.info('Loading parameter file . . . ')
        self.parameters_all = parameter_parser.get_parameters(param_filename = 'data/skimage_parameters.xlsx',
                                                        get_all_params = True)

        for params in self.parameters_all:
            remote_odroid = RemoteOdroid(params)

            if remote_odroid.ip_address == self.ip_address:
                logging.info('Odroid: ' +  remote_odroid.sensor_id
                            + ' at ' +  remote_odroid.sensor_label 
                            + '   IP address: ' + remote_odroid.ip_address 
                            + '   Connection status: this running odroid: ignored.') 
                continue

            if remote_odroid.ping_status['ping_status']:
                self.remote_odroids.update({remote_odroid.sensor_id : remote_odroid })
                logging.info('Odroid: ' +  remote_odroid.sensor_id
                            + ' at ' +  remote_odroid.sensor_label 
                            + '   IP address: ' + remote_odroid.ip_address 
                            + '   Connection status: Found on network') 
            else:
                logging.info('Odroid: ' +  remote_odroid.sensor_id
                            + ' at ' +  remote_odroid.sensor_label 
                            + '   IP address: ' + remote_odroid.ip_address 
                            + '   Connection status: NOT found on network') 

    def deploy_skimage(self):
        # Main update function

        # 1 : Full install from scratch 
        # 2 : Update docker image
        # 3 : Update all source code
        # 4 : Update parameter files only

        # Select option
        if option == '1':
            # Do a fresh install. This will pull the latest docker image and 
            # source folder on the remote odroid. REQUIRES INTERNET access
            # on the remote odroid. 
            self.do_fresh_install = True
            self.do_update_parameters = True

        elif option == '2':
            # Update source folder. This includes the parameter file 
            self.do_update_source_folder = True
            self.do_update_parameters = True

        elif option == '3':
            # Update source folder. Ignore parameter file and my_id.txt 
            self.do_update_source_folder = True
            
        elif option == '4':
            # Update the parameter file only
            self.do_update_parameters = True

        else:
            logging.warning('The valid options are 1, 2, 3 or 4. Please choose a valid option!')


        # Loop over remote odroids and do the deployment tasks specified by the 
        # deployment option that was chosen

        for sensor_id, remote_odroid in self.remote_odroids.items():
            remote_odroid.establish_ssh_connection()

            if not remote_odroid.ssh_client:
                continue

            if self.do_fresh_install:
                remote_odroid.fresh_install()
                remote_odroid.compare_datetimes()

            if self.do_update_source_folder:
                remote_odroid.update_source_code()
                remote_odroid.setup_systemd()

            if self.do_update_parameters:
                remote_odroid.copy_parameter_file()
                remote_odroid.write_my_id()

            remote_odroid.reboot_remote()
            remote_odroid.ssh_client.close()
            logging.info('Finished with odroid: ' +  remote_odroid.sensor_id + '\n')


if __name__ == "__main__":
    option = str(sys.argv[1])
    master_odroid = MasterOdroid(option)
    master_odroid.deploy_skimage()

    
