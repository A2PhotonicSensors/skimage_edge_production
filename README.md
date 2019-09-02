# Skimage

This is a publice repository for the production code of the Skimage project. 

### Prerequisites 
The following are the necessary components of Skimage:

1. An Odroid version of Ubuntu 18.04:
    This is the operating system that ships with the Odroid, and has some adaptations for the GPU drivers, among other things.
2. The inotify-tools package, which allows effcient monitoring of files and folders. This is the only external prerequisite not bundled into the the docker image.
3. Docker: The docker engine and docker-compose
4. The production Docker image for Skimage
5. This source code repository 


# Deployment

Deployment is handled by the script [deploy_skimage.sh](deploy_skimage.sh)

The deployment script envisages the following 5 uses cases for deployment:
1. **Full fresh installation on all odroids:**
   This use case installs all of the depen

This repository contains the source code for Skimage. Skimage was written in python 3, with core functionality ported to c++. Python, c++, and linux dependencies are resolved using Docker. The target architecture is armv7, but development take place on x86-64bit architecture. This necessitates two docker containers, one for each architecture. Cross-compiling is handled in the armv7 docker container, which can be run on x86 host.

### Prerequisites

[Docker for linux](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
or
[Docker for windows](https://docs.docker.com/docker-for-windows/install/)


