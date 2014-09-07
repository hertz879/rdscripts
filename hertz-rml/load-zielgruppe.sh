#!/bin/bash

# This script tries to load the log (aka playlist) for the special interest music show
# "Zielgruppe" (German for target group) of today and start the log
# afterwards. 

# get the date in the form Rivendell use it: 2014_08_31
NOW_DATE=$(date +%Y_%m_%d)

# Check if there is a argument
if [ $# -eq 1 ]; then

    # name of the "Zielgruppe" from command line
    ZG_NAME=$1

    # Load the Log for the 'Zielgruppe' of today
    # LL <mach> <logname> <start-line>
    #
    # mach: 1=Main Log (we only use the main log)
    # logname: Date with underscores e.g. 2014_08_31

    echo 'rmlsend "LL 1 ZIELGRUPPE_'${ZG_NAME}_${NOW_DATE}'"!'
    rmlsend "LL 1 ZIELGRUPPE_${ZG_NAME}_${NOW_DATE}"!
else
    # Error output, if more then one argument is given at start time
    echo -e "\n\terror: exactly. one argument ("zielgruppe" name) allowed" >&2
    echo -e "\tusage: ${0} [ZIELGRUPPE_NAME]}\n" >&2
    exit 1
fi

