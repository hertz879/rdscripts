#!/bin/bash

# This script checks, if the new event is empty and updates the message bay

# Check if there is a argument
if [ $# -gt 0 ]; then

    if ! [[ $@ = "-" ]] ;then
        SONG="Das war: $@"
        echo 'rmlsend "LB '$SONG' "!'
        rmlsend "LB $SONG "!
    fi
else
    # Error output, if more then one argument is given at start time
    echo -e "\n\terror: at least. one argument (track info)" >&2
    exit 1
fi

