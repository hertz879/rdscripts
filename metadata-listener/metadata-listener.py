#!/usr/bin/python
# -*- coding: utf8 -*-
import socket, re, sys, errno, os
from datetime import datetime
from optparse import OptionParser

# Dieses Skript lauscht auf Now-and-Next Nachrichten von Rivendell, die
# Angaben über das gerade gespielte Event (Song, Jingle, Beitrag, …) enthalten.
# Rivendell sendet per UDP. Daher Port und IP vom lauschenden Rechner angeben.

# Das Skript läuft non-stop bis es per CTRL-C o.ä. beendet wird oder auf einen
# Netzwerk-Fehler stößt.

# Exit Codes:
# 
#   0   Beendet mit CTRL-C.
#
#   1   Generischer Fehler. 
#
#   5   Gewählte IP:Port-Kombination ist bereits belegt.

# TODO: Akzeptiert auch hostnamen, prüfen, ob IP/Host zum eigenen System gehört
# UDP_IP:
# -------
# IP des Netzwerk-Devices, auf dem nach Now&Next-Paketen gelauscht werden soll.
# Nur lokal lauschen (nur zum testen sinnvoll)
# UDP_IP = "127.0.0.1" 
#
# Auf allen Netzwerk-Geräten lauschen
# UDP_IP = ""
#
# Vorgabe: IP des Netzwerk-Devices, was die Verbindung zwischen Studio- und 
# Streamrechner erstellt. 

# UDP_IP = "129.70.176.39"

UDP_IP = ""

# UDP_PORT:
# ---------
# Port auf dem die Nachrichten via UDP eingehen. Den Port nachsehen in Rivendell 
# unter: rdadmin -> Manage Hosts -> Studio-Rechner -> RDAirplay -> Now&Next Data
#
# Vorgabe: 5000

UDP_PORT = 5000


# WANTED_GROUPS:
# --------------
# Welche Gruppen sollen in die Plylist eingebunden werden? Namen in Rivendell
# nachsehen in rdadmin -> Manage Groups
# Groß- und Kleinschreibung beachten.

WANTED_GROUPS = ["MUSIC", "MusikArchiv", "WORT", "TRAFFIC", "SHOWS"]

# TODO: Pfade via Variable

TMP_DIR="tmp/"
XSPF_FRAGMENT_FILENAME=TMP_DIR+'xspf-current-fragment'
PLAIN_FRAGMENT_FILENAME=TMP_DIR+'plain-current-fragment'
CURRENT_ARTIST_FILENAME=TMP_DIR+'current.artist'
CURRENT_TITLE_FILENAME=TMP_DIR+'current.title'
# Optionen zuweisen, die später ausgewertet werden sollen/können.

parser = OptionParser(version="%prog 0.10", 
                      usage="usage: %prog [options]")

parser.set_defaults(verbose=False)
parser.set_defaults(port=UDP_PORT)
parser.set_defaults(ip=UDP_IP)

parser.add_option("-p", "--port", dest="port", type="int", help="Port to listen")
parser.add_option("-i", "--ip", dest="ip", help="IP (v4) to listen")
parser.add_option("-v", "--verbose", action="store_true", 
                  help="Enable verbose output")

# Option-Parser starten und Kommandozeilen-Optionen auslesen 
(option, args) = parser.parse_args()

DEBUG=option.verbose
UDP_IP=option.ip
UDP_PORT=option.port

RECURRING_ERROR=False

#TODO: Von .hirse.rc Variablen lesen

#TODO: Haverie-System / Restart Listener (while true??)


# SPLIT_CHAR:
# -----------
# Zeichen, welches die einzelnen Felder trennt. Gnaues Format den 
# Now&Next-Einstellungen entnehmen. Derzeit: 
#
# "%g|%a|%t|%h %r"
# 
# %g = group, %a = artist, %t = track, %h = dauer in ms, %r = Zeilenumbruch

SPLIT_CHAR = "|"

# XSPF_META_TIMESTAMP_STRING:
# ---------------------------
# Zeichenkette, für die Metadaten in der Playliste. Arg unwichtig.
XSPF_META_TIMESTAMP_STRING="http://radio.uni-bielefeld.de/xspf/timestamp"


# Debug-Funktion
#TODO: Ausgabe auf stderr?

def error_print(string):
    print >> sys.stderr, string

def debug(string):
    if DEBUG:
        error_print(string)

def write_file(track, dir, filename, replace):
    if replace:
        mode = 'w' # replace
    else:
        mode = 'a' # append
#    try: 
#        os.makedirs(path)
#    except OSError:
#        if not os.path.isdir(path):
#            raise
    try:
        if not os.path.isdir(dir):
            os.makedirs(dir)
        outputfile = open(filename, mode)
        outputfile.write(track)
        outputfile.close()
    except IOError, e:
        errorcode=e[0]
        errordesc=e[1]
        error_print(errordesc, "[", errorcode, "]")
        # TODO: Dateirechte etc behandeln
        sys.exit(1)
    except Exception, e:
        error_print(type(e).__name__ +": " + e[0])
        sys.exit(1)
        
def create_xspf(artist, song, group, ms, date):

    date_str = date.strftime("%Y-%m-%dT%H:%M:%S+01:00")

    xmltitle = "\t<title>"+song+"</title>\n"
    xmlcreator = "\t<creator>"+artist+"</creator>\n"
    xmlduration = "\t<duration>"+ms+"</duration>\n"
    xmlmeta = "\t<meta rel=\""+XSPF_META_TIMESTAMP_STRING+"\">"+date_str+"</meta>\n"
    xmltrack = "<track>\n" + xmltitle + xmlcreator + xmlduration + xmlmeta + "</track>\n"
    debug(xmltrack)
    write_file(xmltrack, TMP_DIR, XSPF_FRAGMENT_FILENAME, True)

def create_plain(artist, song, group, ms, date):

    creator = "artist="+artist+"\n"
    title = "title="+song+"\n"
    genre = "genre="+group+"\n"
    # Hier wollen wir nur die Sekunden.
    duration = "playTime="+`int(round(int(ms)/1000.))`+"\n"
    year = "startYear="+`date.year`+"\n"
    month = "startMonth="+`date.month`+"\n"
    day = "startDaz="+`date.day`+"\n"
    time = "startYear="+date.strftime("%H:%M:%S")+"\n"
    comment = 'comment=\n'

    track = creator + title + genre + duration + year + month + day + time + comment

    debug("----------------\nPlain output:" + track + "----------------")
    
    write_file(track, TMP_DIR, PLAIN_FRAGMENT_FILENAME, True)
    write_file(artist+"\n", TMP_DIR, CURRENT_ARTIST_FILENAME, True)
    write_file(song+"\n", TMP_DIR, CURRENT_TITLE_FILENAME, True)

# Copy-Paste-Haufen
#    if errorcode == errno.EACCES:
#        error_print(SOCK_ERR_STR + errordesc)
#    elif errorcode == errno.EADDRINUSE:
#        error_print(SOCK_ERR_STR + errordesc)
#        # Spezieller Exitcode für die Bash, damit wir in dem Fall warten können.
#        sys.exit(5)
#    elif errorcode == socket.EAI_NODATA:
#         error_print(SOCK_ERR_STR + errordesc)
#    else:
#        error_print(SOCK_ERR_STR + " Error " + `errorcode` + "], " + errordesc)
#    sys.exit(1)



#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
#sock.bind((UDP_IP, UDP_PORT))

# Diese Zeichenkette UDP_STRING dient nur für eine verständlichen Fehlermeldung.
if UDP_IP=="":
    UDP_STRING= '*:'+`UDP_PORT`
else:
    UDP_STRING= UDP_IP+':'+`UDP_PORT`

# Hier lauscht das Skript konkret auf der angegebenen IP/PORT
# TODO: IPv6 ?? -> Kann Rivendell nicht.

#TODO: remove after testing
#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
#sock.bind((UDP_IP, UDP_PORT))
try:
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.bind((UDP_IP, UDP_PORT))
except socket.error, e:
    SOCK_ERR_STR = "[" + UDP_STRING +"]: "
    errorcode=e[0]
    errordesc=e[1]
    # Fehler, die nicht zu einem exit führen sollen, sind hier nicht vorgesehen
    # Sonst sys.exit in die entsprechenden if-teile reinverschieben.
    if errorcode == errno.EADDRINUSE:
        error_print(SOCK_ERR_STR + errordesc)
        # Spezieller Exitcode für die Bash, damit wir in dem Fall warten können.
        sys.exit(5)
    elif errorcode == socket.EAI_NODATA or errno.EACCES:
         error_print(SOCK_ERR_STR + errordesc)
    elif errorcode == socket.EAI_ADDRFAMILY:
         error_print(SOCK_ERR_STR + errordesc + ". No IPv6 support, yet.")
    else:
        error_print(SOCK_ERR_STR + " Error " + `errorcode` + ", " + errordesc)
    sys.exit(1)
except OverflowError, e:
    # Wir wollen nur die Beschreibung "port must be 0-65535" aus
    # OverflowError('getsockaddrarg: port must be 0-65535.',)
    errordesc=e[0].split("'")[0].split(":")[1]
    error_print("["+UDP_STRING + "]: " + errordesc)
    sys.exit(1)
except Exception, e:
    error_print("Unknown Error: " + `e`)
    sys.exit(1)

# Variablen die zur Auswertung benötigt werden
artist = ""
song = ""
group = ""
ms = ""

# Dauerschleife, für jedes eingehende Paket wird sie einmal durchlaufen
while True:
    try:
        debug('Listening on '+UDP_STRING) 
        data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        debug('Received message from '+ `addr` + ': ' + data )
        
        # Empfangene Zeichenkette aufteilen.
        try:
            group, artist, song, ms = data.rstrip('\n').split(SPLIT_CHAR)
        except ValueError:
            error_print("Ignoring packet with wrong value format: " + data)
        
        # Zeichenketten von Leerzeichen etc. säubern.
        artist = artist.strip()
        song = song.strip()
        group = group.strip()
        ms = ms.strip()
        # TODO: Zeitzone korrekt ermitteln und einbinden
        date = datetime.today()
        
        # Nur die Events in die Playlist einpflegen, die wir oben angegeben haben.
        if group in WANTED_GROUPS:
            # XML von Hand bauen. Für das bissl XSPF lohnt sich keine lib.
            # Es gibt xspf.py, aber das hat <meta> noch nicht implementiert.
            
            create_xspf(artist, song, group, ms, date)
            
            create_plain(artist, song, group, ms, date)
            
        else:
            debug("Excluding GROUP: _" + group + "_")
        
        # Variablen leeren, insbesondere group, da es für "if" genutzt wird
        track = ""
        group = ""
    
    except KeyboardInterrupt:
        debug("\nExit listener by user interrupt.")
        exit(0)


