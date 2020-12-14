#!/usr/bin/env bash

# Log stdout and stderr in installation.log on home directory

echo "Starting installation script on remote odroid. . ."

# In order to run all the next commands without having to enter the password
echo "Sudo-ing"
sudo false

echo " Loading skimage variables . . . "
source $(dirname $BASH_SOURCE)/skimage_variables.env

echo "Removing $ROOT_DIR/$SOURCE_DIR"
sudo rm -rf "$ROOT_DIR/$SOURCE_DIR"

#echo "Setting time zone"
#sudo timedatectl set-timezone $TZ

sudo apt-get -y update
sudo apt-get -y upgrade

sudo apt-get -y install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common \
	inotify-tools \
	git

echo "Installing docker"
sudo apt-get -y remove docker docker-engine docker.io containerd runc

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

if [ `uname -m` = "x86_64" ]
then
    sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
else
    sudo add-apt-repository \
   "deb [arch=armhf] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
fi

sudo apt-get -y update
sudo apt-get -y install docker-ce docker-ce-cli containerd.io
sudo groupadd docker
sudo usermod -aG docker $USER

echo "Installing docker-compose"
#sudo apt-get -y install docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/1.17.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "Pulling docker image"
sudo docker pull $DOCKER_IMAGE

echo "Making odroid directory "
sudo mkdir -p $ROOT_DIR/$SOURCE_DIR
sudo chown -hR $USER:users $ROOT_DIR

# clone Github repo
echo "Cloning into github repo $GIT_REPO"
git clone $GIT_REPO $ROOT_DIR/$SOURCE_DIR
echo "Github repo has been pulled"

echo "Making data directory "
mkdir -p $ROOT_DIR/$SOURCE_DIR/data
echo "Copying default skimage_parameters.xlsx' from /docs to /data"
cp $ROOT_DIR/$SOURCE_DIR/docs/skimage_parameters.xlsx $ROOT_DIR/$SOURCE_DIR/data/skimage_parameters.xlsx
echo "Copying default my_id.txt' from /docs to /data"
cp $ROOT_DIR/$SOURCE_DIR/docs/my_id.txt $ROOT_DIR/$SOURCE_DIR/data/my_id.txt

echo "Making Logs_SKIMAGE directory if it doesn't already exist"
mkdir -p $ROOT_DIR/$SOURCE_DIR/$SKIMAGE_LOGS_DIR

echo "Setting execute permissions on skimage.sh"
chmod +x $ROOT_DIR/$SOURCE_DIR/skimage.sh

echo "Copying skimage_watchdog.service to /lib/systemd/system"
sudo cp $ROOT_DIR/$SOURCE_DIR/Utilities/skimage_watchdog.service /lib/systemd/system

echo "Reloading systemd daemon and enabling skimage_watchdog service"
sudo systemctl daemon-reload
sudo systemctl enable skimage_watchdog.service

echo "Cleaning apt"
sudo apt -y autoremove