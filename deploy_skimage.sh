#!/usr/bin/env bash

# Main update script

# Load in variables from env file
source Utilities/skimage_variables.env

echo ""
echo "This deployment script will deploy and/or update Skimage on all the odroids 
listed in the parameter file skimage_parameters.xlsx"
echo ""

read -p "Please enter the username for all deployed odroids : " USER_ALL;

echo -n "Please enter the password for all deployed odroids :"; 
read -s PASSWORD_ALL;

echo "Choose a deployment option, which will be applied to all odroids "
echo ""
export USER_ALL 
export PASSWORD_ALL

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
   [1]* ) /usr/bin/wget -O - -q -t 1 http://www.example.com/cron.php
           echo "Okay, just ran the cron script."
           break;;

   [2]*  ) echo "Updating docker . . ."
           docker pull ${DOCKER_IMAGE} 
           echo "Compressing docker image to tarball, this will take a few minutes."
           docker save -o "${ROOT_DIR}/${SOURCE_DIR}/docker_image.tar" ${DOCKER_IMAGE}
           exit;;

   [3]*  ) echo "3"
           docker-compose -f "${ROOT_DIR}/${SOURCE_DIR}/Utilities/docker-compose.yml" up Deploy ;;

   [4]*  ) echo "4";;

   [Qq]* ) exit;;

   * )     echo "Invalid selection! Please enter one of the following choices: 1, 2, 3, 4, or q";;
  esac
done