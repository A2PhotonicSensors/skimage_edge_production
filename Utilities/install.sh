#!/usr/bin/env bash

# Log stdout and stderr in installation.log on home directory

echo "Starting installation script . . ."
 sudo -S rm "${HOME}/installation.log"


# Load skimage variables
echo " Loading skimage variables . . . "
source "${1}/Utilities/skimage_variables.env"

echo "Removing ${ROOT_DIR}/${SOURCE_DIR}"
cd 
echo "${2}" | sudo rm -rf "${ROOT_DIR}/${SOURCE_DIR}"
echo "Removed ${ROOT_DIR}/${SOURCE_DIR}"

# clone Github repo
echo "Cloning into github repo ${GIT_REPO}"
git clone ${GIT_REPO}
echo "Github repo has been pulled"

# Allow watchdog.sh to be executable 
echo "Setting execute permissions on skimage.sh"
chmod +x "${ROOT_DIR}/${SOURCE_DIR}/skimage.sh"

# Set time zone
echo "Setting time zone"
sudo timedatectl set-timezone ${TZ}

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
docker pull ${DOCKER_IMAGE}
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
mkdir -p "${ROOT_DIR}/${SOURCE_DIR}/${SKIMAGE_LOGS_DIR}" 
echo "Making soft link to ${SKIMAGE_LOGS_LINK}"
sudo ln -s "${ROOT_DIR}/${SOURCE_DIR}/${SKIMAGE_LOGS_DIR}" ${SKIMAGE_LOGS_LINK}

# Copy skimage_watchdog.service to /lib/systemd/system
echo "Copying skimage_watchdog.service to /lib/systemd/system"
sudo cp "${ROOT_DIR}/${SOURCE_DIR}/Utilities/skimage_watchdog.service" /lib/systemd/system

# Enable service
echo "Reloading systemd daemon and enabling skimage_watchdog service"
sudo systemctl daemon-reload
sudo systemctl enable skimage_watchdog.service

echo "Rebooting"
# Reboot
sudo reboot
