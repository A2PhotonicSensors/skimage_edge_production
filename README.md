# Skimage

This is a private development repository for the Skimage project. 

There are two ways to read the documentation:
* Clone or download this repository, then open [the html file](docs/build/html/index.html) (preferred)
* [The pdf version](https://github.com/nstelzen/skimage_edge/blob/master/docs/build/latex/skimage.pdf)

## Getting Started

This repository contains the source code for Skimage. Skimage was written in python 3, with core functionality ported to c++. Python, c++, and linux dependencies are resolved using Docker. The target architecture is armv7, but development take place on x86-64bit architecture. This necessitates two docker containers, one for each architecture. Cross-compiling is handled in the armv7 docker container, which can be run on x86 host.

### Prerequisites

[Docker for linux](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
or
[Docker for windows](https://docs.docker.com/docker-for-windows/install/)


