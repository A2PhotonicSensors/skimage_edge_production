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
import subprocess
import paramiko
import logging 
from pathlib import Path
import datetime

import python_src.parameter_parser as parameter_parser
from python_src.startup_checks import check_ping

logging.basicConfig(level=logging.INFO)

def test_internet_connection():
    # Test internet connection, warn that we can't pull latest Docker
    # image or source code from repos w/o internet
    try:
        logging.info('Testing internet connection . . . ')
        response = urllib.request.urlopen('https://www.google.com/', timeout=1)
        logging.info('Internet connection found')
        return True

    except:
        logging.warning('No internet connection found! '
        + 'Proceeding with to do the update with local files '
        + 'Remember to synchronize the source code with the Github repo as soon as possible') 
        return False

def pull_source_code():
    # Attempt to pull source code from Github, warn if not possible
    try:
        logging.info('Pulling latest version of source code from github . . . ')
        git_repo = git.Repo('/home/')
        git_repo.remotes.origin.pull()
        logging.info('Pull successful, source code is synchronized with github')
    except:
        logging.warning('Unable to pull latest version of code from the github repository')
    return

def pull_docker_image(docker_image_name):
    # Attempt to pull Docker image, warn if not possible
    try:
        subprocess.run('docker pull ' + docker_image_name, check=True, shell=True)
    except:
        logging.warning('Unable to pull latest version of the docker image from the repository')

    return 

def create_docker_tarball(docker_image_name):
    # Create compressed docker image file from local docker image
    try:
        subprocess.run('docker save -o ~/docker_image.tar ' + docker_image_name, check=True, shell=True)
    except:
        logging.critical('Unable to compress and save docker image! Check docker_image_name and try again')
        sys.exit(0)

def get_list_of_odroids():
    # Load parameter file and get list of odroid's ip address
    # ping each ip and report results
    try:
        logging.info('Loading parameter file . . . ')
        parameters_all = parameter_parser.get_parameters(param_filename = 'data/skimage_parameters.xlsx',
                                                         get_all_params = True)
    except:
        logging.critical('Unable to load parameter file!')
        sys.exit(0)

    list_of_odroids = []
    for params in parameters_all:
        if not params['Sensor_Label'] == 'Master':
            sensor_label = params['Sensor_Label']
            ip_address = params['Odroid_Path']
            ping_status = check_ping(ip_address)
            if ping_status:
                list_of_odroids.append(ip_address)
                logging.info('Odroid: ' +  sensor_label 
                                     + '   IP address: ' + ip_address 
                                     + '   Connection status: Found on network') 
            else:
                logging.error('Odroid: ' +  sensor_label 
                                      + '   IP address: ' + ip_address 
                                      + '   Connection status: NOT found on network')

    return list_of_odroids

def connect_to_remote_odroid(ip_address, user, password):
    try:
        logging.info('Establishing SSH connection to ' + user + '@' + ip_address + ' . . . ')
        ssh_client =paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip_address,username=user,password=password, timeout=10)
        logging.info('SSH connection established')
        return ssh_client
    except:
        logging.warning('Unable to connect to ' + ip_address + ' via SSH')
        return None

def copy_parameter_file(ssh_client, source_folder, password):
    # Copy parameter file to remote Odroid
    parameter_filepath = source_folder + '/data/skimage_parameters.xlsx'
    parameter_pickle_filepath = source_folder + '/data/skimage_parameters.pickle'
    try:
        stdin, stdout, stderr = ssh_client.exec_command('sudo rm -f ' + parameter_filepath 
                                                + ' ' + parameter_pickle_filepath, get_pty=True)
        stdin.write(password + '\n')
    
    except:
        logging.warning('Error in deleting old verions of the parameter file on the remote machine')
    
    try:
        ftp_client=ssh_client.open_sftp()
        ftp_client.put('/home/data/skimage_parameters.xlsx', parameter_filepath)
        ftp_client.close()
        return True
    
    except:
        logging.warning('Error in copying parameter file to remote odroid')
        return False

def write_my_id(ssh_client, source_folder, ip_address):
    # Create or overwrite (linux command ">") my_id.txt file.
    # Contains the last three numbers of the ip address
    
    my_id_filename = source_folder + '/data/my_id.txt'
    my_id = ip_address[-3::]
    try:
        stdin, stdout, stderr = ssh_client.exec_command('echo \"' + str(my_id) + '\" > ' + my_id_filename)

        logging.info('my_id.txt written successfully')
    except:
        logging.warning('Error in writing to the my_id.txt file on the remote machine')
    
    return

def update_source_code(ssh_client, source_folder, password):
    
    def resolve_remote_path(source_folder, path_object):
        # Get full local path to object minus the root '/home'
        relative_local_path = path_object.relative_to('/home')
        
        # Create Path object from source_folder string
        remote_root = Path(source_folder)

        # Join the remote root and the relative local path
        remote_path = remote_root.joinpath(relative_local_path)

        # Return the full remote path as a string
        return remote_path.as_posix()

    def check_for_names_to_skip(path_object):
        skip = False # By default do not skip

        # Hard code the beginnings of names of files/folder to skip
        forbidden_beginnings = ['.', 'Logs', '__', 'semaphore'] 
        for forbidden_beginning in forbidden_beginnings:
            len_forbidden = len(forbidden_beginning)

            # Check that the beginning of the name of the file/folder doesn't start with a
            # forbidden beginning 
            if path_object.name[0:len_forbidden] == forbidden_beginning:
                skip = True
        return skip

    def copy_files(ftp_client, source_file, source_folder):
        if check_for_names_to_skip(source_file):
            logging.info('Skipping ' + source_file.name )
            return
        remote_filepath = resolve_remote_path(source_folder, source_file)
        logging.info('Copying ' + remote_filepath + ' to remote odroid')
        ftp_client.put(source_file.resolve().as_posix(), remote_filepath)
        return

    def copy_folders(ftp_client, source_subfolder, source_folder):
        if check_for_names_to_skip(source_subfolder):
            logging.info('Skipping ' + source_subfolder.name )
            return
        remote_folder = resolve_remote_path(source_folder, source_subfolder)
        logging.info(' Creating folder ' + remote_folder + ' on remote odroid')
        ftp_client.mkdir(remote_folder)
        
        for path_object in source_subfolder.iterdir():
            if path_object.is_file():
                copy_files(ftp_client, path_object, source_folder)
            elif path_object.is_dir():
                copy_folders(ftp_client, path_object, source_folder)
            else:
                logging.warning('Path object '  + path_object.name + ' was not copied to remote odroid')
        return

    # Delete source code folder on remote, preserving log folders
    try:
        cmd = 'find ' + source_folder + ' -mindepth 1 -not -name \'Logs_*\' -delete'
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        # stdin.write(password + '\n')
    
    except:
        logging.warning('Error in deleting the source folder on the remote machine')
    
    # Copy local source code file to remote (except logs folders)
    try:
        ftp_client=ssh_client.open_sftp()

        # Loop through contents
        local_root_path = Path('/home')
        for path_object in local_root_path.glob('*'):

            if path_object.is_file():
                copy_files(ftp_client,path_object, source_folder)
            
            elif path_object.is_dir():
                copy_folders(ftp_client, path_object, source_folder)

            else:
                logging.warning('Path object '  + path_object.name + ' was not copied to remote odroid')

        ftp_client.close()

        return True
    except:
        
        logging.warning('Error in copying source folder to remote odroid')
        return False
    

def setup_systemd(ssh_client, source_folder, password):
    # After an update of the source code this resets the systemd service

    try:
    # Copy the skimage_watchdog.service file to correct location
        relative_service_filepath = 'Utilities/skimage_watchdog.service'
        source_filepath = Path(source_folder).joinpath(relative_service_filepath)
        remote_destination = '/lib/systemd/system'
        
        cmd = 'sudo cp ' + source_filepath.as_posix() + ' ' + remote_destination

        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        stdin.write(password + '\n')

        # Reload systemd daemon
        stdin, stdout, stderr = ssh_client.exec_command('sudo systemctl daemon-reload')
        stdin.write(password + '\n')

        # Enable systemd service
        stdin, stdout, stderr = ssh_client.exec_command('sudo systemctl enable skimage_watchdog.service')
        stdin.write(password + '\n')

        logging.info('skimage_watchdog systemd service configured successfully')
    except:
        logging.warning('Error in configuring skimage_watchdog systemd service!')
    
    return

def confirm_skimage_logs_folder(ssh_client, source_folder, skimage_log_link_folder):
    # Check that Logs_SKIMAGE folder exists, if not, create it
    # Check that soft link to home/odroid/Logs_SKIMAGE, if not, create it
    logs_file_path = source_folder + '/Logs_SKIMAGE'

    try:
        stdin, stdout, stderr = ssh_client.exec_command('mkdir -p ' + logs_file_path)
        stdin, stdout, stderr = ssh_client.exec_command('ln -sf ' + logs_file_path 
                                                        + ' ' + skimage_log_link_folder)
    
        logging.info('Skimage logs folder checks passed')
    except:
        logging.warning('Error in skimage logs folder checks')
    
    return

def compare_time(ssh_client, password):
    # set timezone
    timezone = 'Europe/Paris'
    try:
        stdin, stdout, stderr = ssh_client.exec_command('sudo timedatectl set-timezone ' + timezone)
        stdin.write(password + '\n')
        logging.info('Successfully set time zone to ' + timezone + ' on remote odroid')
    except:
        logging.warning('Error in setting time zone on remote odroid!')
    
    # Compare date/time local and remote, warn if difference is too great
    try:
        stdin, stdout, stderr = ssh_client.exec_command('date --iso-8601=\'seconds\'')
        nowish = datetime.datetime.now()
        remote_time_list = stdout.readlines()
        remote_time_string = remote_time_list[0]
        remote_time_string = remote_time_string[0:-7] # Get rid of timezone info 

        remote_time_object = datetime.datetime.strptime(remote_time_string, '%Y-%m-%dT%H:%M:%S')

        time_difference = nowish - remote_time_object

        seconds_off = time_difference.total_seconds()

        logging.info('Local odroid time is ' + nowish.strftime('%Y-%m-%dT%H:%M:%S')) 
        logging.info('Remote odroid time is ' + remote_time_string )
        if abs(seconds_off) > 300:
            logging.warning('Remote odroid clock is different from local odroid clock by ' 
                           + str(seconds_off) + ' seconds, over 5 minutes!')

        else:
            logging.info('Remote odroid clock is different from local odroid clock by ' 
                           + str(seconds_off) + ' seconds')
    except:
        logging.warning('Error in comparing date and time between local and remote odroids')
    return

def update_docker_image(ssh_client):
    # Copy zipped docker image to remote
    # Load docker image on remote
    pass

def reboot_remote(ssh_client, password):
    # Reboot remote odroid
    try:
        logging.info('Reboot remote odroid')
        stdin, stdout, stderr = ssh_client.exec_command('sudo reboot', get_pty=True)
        stdin.write(password + '\n')
    except:
        logging.warning('Failed to reboot remote odroid')
    return

def fresh_install(ssh_client, source_folder, password):
    # A fresh install means the remote odroid has simply the factory OS
    # We require that the remote odroid have an internet connection to 
    # do a fresh install
 
    stdin, stdout, stderr = ssh_client.exec_command('sudo rm -rf /home/odroid/skimage_edge_deployment', get_pty=True)
    stdin.write(password + '\n')

    stdin, stdout, stderr = ssh_client.exec_command('mkdir -p /home/odroid/skimage_edge_deployment', get_pty=True)   

    ftp_client=ssh_client.open_sftp()

    ftp_client.put('/home/Utilities/install.sh', '/home/odroid/skimage_edge_deployment/Utilities/install.sh')
    ftp_client.close()

    stdin, stdout, stderr = ssh_client.exec_command('chmod +x ' + source_folder + '/Utilities/install.sh', get_pty=True)
    stdin, stdout, stderr = ssh_client.exec_command('bash /home/odroid/skimage_edge_deployment/Utilities/install.sh')
    stdin.write(password + '\n')
    logging.info(stdout.readlines())

    return

def deploy_skimage(**args):
    # Main update script
    user = 'odroid'
    password = 'odroid'
    source_folder = '/home/odroid/skimage_edge_deployment'
    skimage_log_link_folder = '/home/odroid/Logs_SKIMAGE'
    docker_image_name = 'nickstelzenmuller/skimage:ARM_prod'

    logging.info('''Options:
    1 : Full install from scratch 
    2 : Update docker image
    3 : Update all source code
    4 : Update parameter files only''')
    if not args:
        option = input('Please select and option (1-4) : ')

    # Select option
    if option == '1':
        # Do a fresh install. This will pull the latest docker image and source folder
        do_fresh_install = True
        do_update_docker_image = False
        do_update_source_folder = False
        do_update_parameters = False

    elif option == '2':
        # Update Docker image. Do a source folder update as well
        do_fresh_install = False
        do_update_docker_image = True
        do_update_source_folder = True
        do_update_parameters = False

    elif option == '3':
        # Update source folder. This includes the parameter file 
        do_fresh_install = False
        do_update_docker_image = False
        do_update_source_folder = True
        do_update_parameters = False

    elif option == '4':
        # Update the parameter file only
        do_fresh_install = False
        do_update_docker_image = False
        do_update_source_folder = False
        do_update_parameters = True

    else:
        logging.info('The valid options are 1, 2, 3, or 4. Please choose a valid option')
        deploy_skimage()

    internet_connection = test_internet_connection()

    if internet_connection:
        pull_source_code()
        pull_docker_image(docker_image_name)

    if do_fresh_install:
        if not internet_connection:
            logging.info('The "fresh installation" option requires an internet connection ' +
                  'but one was not found. Exiting now')
            return None
    
    if do_update_docker_image:
        docker_tarball = create_docker_tarball(docker_image_name)

    list_of_odroids = get_list_of_odroids()

    
    bad_connections = []
    for ip_address in list_of_odroids:
        ssh_client = connect_to_remote_odroid(ip_address, user, password)
        if not ssh_client:
            logging.warning('Unable to update Odroid at ' + ip_address)
            bad_connections.append(ip_address)
            continue

        if do_fresh_install:
            fresh_install(ssh_client, source_folder, password)

        if do_update_docker_image:
            update_docker_image(ip_address)

        if do_update_source_folder:
            copy_successful = update_source_code(ssh_client, source_folder, password)
            if copy_successful:
                setup_systemd(ssh_client, source_folder, password)
                compare_time(ssh_client, password)
                write_my_id(ssh_client, source_folder, ip_address)
                confirm_skimage_logs_folder(ssh_client, source_folder, skimage_log_link_folder)
                reboot_remote(ssh_client, password)
            else:
                continue

        if do_update_parameters:
            copy_successful = copy_parameter_file(ssh_client, source_folder, password)
            if copy_successful:
                compare_time(ssh_client, password)
                write_my_id(ssh_client, source_folder, ip_address)
                confirm_skimage_logs_folder(ssh_client, source_folder, skimage_log_link_folder)
                reboot_remote(ssh_client, password)
            else: 
                continue

        ssh_client.close() 

    if bad_connections:
        logging.warning('The Odroid(s) at the following addresses were not able to be updated')
        
        for bad_address in bad_connections:
            logging.warning(bad_address)

if __name__ == "__main__":
    deploy_skimage()

    
