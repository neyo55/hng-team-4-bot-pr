#!/bin/bash

if [ -z "$1" ]; then
  echo "Branch name not provided."
  exit 1
fi

BRANCH_NAME=$1
REMOTE_USER="team-4"
REMOTE_HOST="91.229.239.118"
PR_NUMBER=$2

ssh -o LogLevel=ERROR -o StrictHostKeyChecking=no $REMOTE_USER@$REMOTE_HOST << EOF
  # Find and read all container info files for the given branch and PR
  for CONTAINER_INFO_FILE in /tmp/container_info_${BRANCH_NAME}_${PR_NUMBER}_*.txt; do
    if [ -f "\$CONTAINER_INFO_FILE" ]; then
      read CONTAINER_NAME PORT < \$CONTAINER_INFO_FILE
      
      if [ -n "\$CONTAINER_NAME" ]; then
        # Stop and remove the container
        docker stop "\$CONTAINER_NAME"
        docker rm "\$CONTAINER_NAME"
        echo "Container \$CONTAINER_NAME cleaned up successfully."

        # Remove the container info file
        rm "\$CONTAINER_INFO_FILE"
      else
        echo "No container found for branch $BRANCH_NAME with PR $PR_NUMBER."
      fi
    else
      echo "No container information file found for branch $BRANCH_NAME with PR $PR_NUMBER."
    fi
  done
EOF
