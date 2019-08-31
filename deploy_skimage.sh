#!/usr/bin/env bash

# Main update script

# Load in variables from env file
source Utilities/skimage_variables.env

echo ""
echo "This deployment script will deploy and/or update Skimage on all the odroids 
listed in the parameter file skimage_parameters.xlsx"
echo ""

# read -p "Please enter the username for all deployed odroids : " USER_ALL;

# echo -n "Please enter the password for all deployed odroids :"; 
# read -s PASSWORD_ALL;
USER_ALL="odroid"
PASSWORD_ALL="odroid"
echo "Choose a deployment option, which will be applied to all odroids "
echo ""

# Variable used by docker-compose must be exported
export USER_ALL 
export PASSWORD_ALL
export ROOT_DIR
export SOURCE_DIR
export DOCKER_IMAGE

while true
do
  # (1) prompt user, and read command line argument
  read -p "Deployment options:  
1 : Full install from scratch 
2 : Update docker image 
3 : Update all source code 
4 : Update parameter files only
Please enter a selection [1-4], or q to exit, and press enter : " answer

  # (2) handle the input we were given
case $answer in
   [1]* )  echo "Doing full install from scratch . . ." 
           OPTION=${answer}; export OPTION;;


   [2]*  ) echo "Updating docker . . ."
           OPTION=${answer}; export OPTION
           docker pull ${DOCKER_IMAGE} 
           echo "Compressing docker image to tarball, this will take a few minutes."
           docker save -o "${ROOT_DIR}/${SOURCE_DIR}/docker_image.tar" ${DOCKER_IMAGE};;


   [3]*  ) echo "Updating all source code . . . "
           OPTION=${answer}; export OPTION;;

   [4]*  ) echo "Updating parameter files only . . . "
           OPTION=${answer}; export OPTION ;;
          

   [Qq]* ) docker-compose -f "${ROOT_DIR}/${SOURCE_DIR}/Utilities/docker-compose.yml" down  
           exit;;

   * )     echo "Invalid selection! Please enter one of the following choices: 1, 2, 3, 4, or q";;
esac
docker-compose -f "${ROOT_DIR}/${SOURCE_DIR}/Utilities/docker-compose.yml" up Deploy 

done