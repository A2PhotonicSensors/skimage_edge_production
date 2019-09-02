# Skimage

This is a publice repository for the production code of the Skimage project. 

### Prerequisites
The following are the necessary components of Skimage:

1. An Odroid version of Ubuntu 18.04:
    This is the operating system that ships with the Odroid, and has some adaptations for the GPU drivers, among other things.
2. The inotify-tools package, which allows efficient monitoring of files and folders. This is the only external prerequisite not bundled into the the docker image.
3. Docker: The docker engine and docker-compose
4. The production Docker image for Skimage
5. This source code repository


# Deployment*

Deployment is handled by the script [deploy_skimage.sh](deploy_skimage.sh)

The deployment script envisages the following 5 uses cases for deployment:
1. **Full fresh installation on all odroids:**
   This use case is for performing a fresh installation of Skimage and all of the prerequisites of Skimage. This option assumes only that all Odroids in the network have the correct operating system and have access to the internet. All of the dependencies, including the docker engine, docker-compose, the Skimage docker image, etc. are installed, and the Skimage is configure to start automatically after a system reboot. This option may be used to configure all Odroids before deployment in the field. **Attention:** All Skimage data (Logs, etc.) will erased after this option is performed. 

2. **Update Docker image:**
   This use case is for updating the docker image on all the Odroids in the network after a change is made to the docker image. This option assumes that the Odroids in the network are deployed in the field, and do *not* have internet access. The docker image is compressed into a tarball and sent out to all the Odroids in the network. The commpressed file is then unpacked and install as an updated Docker image on all of the Odroids. **Note:** This compressed Docker image is a large (~2 Gb) file, and it would be much more efficient to set up a docker image repository on the master Odroid, then have all the Odroids in the network simply use ```docker pull``` to update their local docker image. 

3. **Update all source code:**
   This uses case is for updating the source code folder on all the Odroids in the network (the files in this repository) after a change is made to one or more source code files. This option preserves all local data, such as logs, videos, etc. on Odroid.  

4. **Update parameter file only:**
   This use case is for updating the parameter file [data/skimage_parameters.xlsx](data/skimage_parameters.xlsx) on all the Odroids in the network after a change to the parameter file. While it may seem redundant to force an update to all Odroids even after a small change to the parameter file, the system is designed such that all of the Odroids are functionally similar, and all have the same version of the Skimage code base and parameters. 


5. **Status update:**
   This use case if for reporting on the status of all the Odroids in the network. This option returns a status report that informs the user of any problems on any of the deployed Odroids.

The two principle repositories for Skimage are this github repository and the [Skimage Docker image](https://cloud.docker.com/repository/docker/a2ps/skimage). The deployment script attempts to pull the lastest version of these repositories before updating the rest of the Odroids on the network. If this is not possible, for example
if the Master Odroid is deployed at the Ski station and does not have internet access, the deployment will proceed with the local versions of the files on the Master Odroid. **To avoid confusion, the Skimage repositories at github and dockerhub should be kept updated to be as close to the Master Odroid as possible.  

This repository contains the source code for Skimage. Skimage was written in python 3, with core functionality ported to c++. Python, c++, and linux dependencies are resolved using Docker. The target architecture is armv7, but development take place on x86-64bit architecture. This necessitates two docker containers, one for each architecture. Cross-compiling is handled in the armv7 docker container, which can be run on x86 host.

### Prerequisites

[Docker for linux](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
or
[Docker for windows](https://docs.docker.com/docker-for-windows/install/)


