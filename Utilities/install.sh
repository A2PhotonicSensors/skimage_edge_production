#!/usr/bin/env bash
#### Hard-coded variables ####
root_dir="/home/odroid"
source_dir="skimage_edge_deployment"
skimage_docker_image="nickstelzenmuller/skimage:ARM_prod"
git_repo="https://github.com/nstelzen/skimage_edge_deployment.git"
timezone="Europe/Paris"
skimage_logs="Logs_SKIMAGE"
skimage_logs_link_location="/home/odroid/${skimage_logs}"
###############################


echo "Removing ${root_dir}/${source_dir}"
cd 
sudo rm -rf "${root_dir}/${source_dir}"
echo "Removed ${root_dir}/${source_dir}"

# clone Github repo
echo "Cloning into github repo ${git_repo}"
git clone ${git_repo}
echo "Github repo has been pulled"

# Allow watchdog.sh to be executable 
echo "Setting execute permissions on skimage.sh"
chmod +x "${root_dir}/${source_dir}/skimage.sh"

# Set time zone
echo "Setting time zone"
sudo timedatectl set-timezone ${timezone}

# Install docker
echo "Installing docker"
sudo apt-get -y remove docker docker-engine docker.io containerd runc

sudo apt-get -y update

sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

sudo add-apt-repository \
   "deb [arch=armhf] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"

sudo apt-get -y update

sudo apt-get -y install docker-ce docker-ce-cli containerd.io

sudo groupadd docker

sudo usermod -aG docker $USER

echo "Docker installed"

# Remove all docker images
echo " Remove all docker images"
docker stop $(docker ps -a -q)
docker rm $(docker ps -a -q)
docker rmi $(docker images)
echo "Docker images have been removed"

# Pull Docker image
echo "Pull docker image"
docker pull ${skimage_docker_image}
echo "Docker image pulled"

# Install docker-compose
echo "Installing docker-compose"
sudo apt-get -y install docker-compose
echo "docker-compose installed"

# Install inotify-tools (Necessary for monitoring of semaphore file by watchdog)
echo "Installing inotify-tools"
sudo apt-get -y install inotify-tools
echo "Inotify-tools installed"

# Set up link to skimage logs folder
echo "Making Logs_SKIMAGE directory if it doesn't already exist"
mkdir -p "${root_dir}/${source_dir}/${skimage_logs}" 
echo "Making soft link to ${skimage_logs_link_location}"
sudo ln -s "${root_dir}/${source_dir}/${skimage_logs}" ${skimage_logs_link_location}

# Copy skimage_watchdog.service to /lib/systemd/system
echo "Copying skimage_watchdog.service to /lib/systemd/system"
sudo cp "${root_dir}/${source_dir}/Utilities/skimage_watchdog.service" /lib/systemd/system

# Enable service
echo "Reloading systemd daemon and enabling skimage_watchdog service"
sudo systemctl daemon-reload
sudo systemctl enable skimage_watchdog.service

echo "Rebooting"
# Reboot
sudo reboot