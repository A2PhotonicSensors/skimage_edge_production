#!/bin/bash
# Main bash script that starts up and manages Skimage


# Setup function to monitor semphore directory
function monitor_semaphore {
  # This function returns True when a file is created or 
  # modified in the semaphore directory    
  inotifywait \
        -e modify,create \
        ${semaphore_dir}
}


if [ -d "/tmp/.docker.xauth/" ]
    then
    sudo rm -R /tmp/.docker.xauth/

fi

# Make a "RESET" file in the semaphore directory
# (and make the semaphore directory if it doesn't already exist)
# This tells other instances of Skimage to shutdown
semaphore_dir="/home/odroid/skimage_edge_deployment/data/semaphore"
mkdir -p --mode=777 ${semaphore_dir}
touch "${semaphore_dir}/RESET"

# Check if other instances of Skimage are running.
# Wait until only one (this script) is found.
running_skimage_pids=($(pgrep -f skimage.sh))
if [ ${#running_skimage_pids[@]} -gt 1 ]
    then 
    echo "Waiting for previously started skimage.sh to terminate . . ."
fi
while [ ${#running_skimage_pids[@]} -gt 1 ]
do  
    sleep 0.1
    running_skimage_pids=($(pgrep -f skimage.sh))
done
echo "All previously started instances of Skimage have stopped, Skimage will now start"

# Clear semaphore directory
echo "Resetting semaphore directory"
rm -r ${semaphore_dir}
mkdir -p --mode=777 ${semaphore_dir}

# Shutdown all docker containers that may be lingering, just in case
docker-compose \
    -f /home/odroid/skimage_edge_deployment/Utilities/docker-compose.yml \
    down


# Set xauth for graphics display. If this causes problems, simply deleting
# the xauth file /tmp/.docker.xauth* should fix it
XAUTH=/tmp/.docker.xauth
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f $XAUTH nmerge -

# Start Skimage in detached mode.
# If you want to see the terminal output use the command :
# docker logs -f <container-name>
docker-compose \
    -f /home/odroid/skimage_edge_deployment/Utilities/docker-compose.yml \
    up -d 

# While loop in bash calls "monitor_semaphore", then goes through the loop
# if "monitor_semaphore" returns TRUE. Monitor semaphore returns TRUE only
# when a semphore is created or modified, otherwise it simply efficiently monitors
# the semaphore directory. Thus "monitor_semaphore" never returns false, and the
# while loop never exits.
while monitor_semaphore
do  

    if [ -f ${semaphore_dir}/RESET ]
    then
        echo "Semaphore received, stopping Skimage"
        # Remove any containers left by a forced shutdown
        docker-compose \
        -f /home/odroid/skimage_edge_deployment/Utilities/docker-compose.yml \
        down
        echo "Exiting skimage.sh"
        exit 0
    
    else
        # docker-compose start skimage
        echo "Restarting Skimage"

        docker-compose \
            -f /home/odroid/skimage_edge_deployment/Utilities/docker-compose.yml \
            restart Skimage
    fi
    
done

