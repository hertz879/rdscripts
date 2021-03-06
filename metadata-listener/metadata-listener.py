#!/usr/bin/python3
# -*- coding: utf8 -*-
import socket
import re
import sys, errno, os
import pytz # required package: python-tz
from xml.sax.saxutils import escape
import subprocess as sp

from datetime import datetime
from optparse import OptionParser

import unicodedata

#TODO: Von .hirse.rc Variablen lesen

# http://stackoverflow.com/questions/3503719/emulating-bash-source-in-python
# command = ['bash', '-c', 'source .hirse.rc && env']
# proc = subprocess.Popen(command, stdout = subprocess.PIPE)

#TODO: Haverie-System / Restart Listener (while true??) -> lieber via bash?

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
# UDP_IP = "0.0.0.0"
#
# Vorgabe: IP des Netzwerk-Devices, was die Verbindung zwischen Studio- und 
# Streamrechner erstellt. 
#
# UDP_IP = "10.11.12.13"

UDP_IP = "0.0.0.0"

# UDP_PORT:
# ---------
# Port auf dem die Nachrichten via UDP eingehen. Den Port nachsehen in Rivendell 
# unter: rdadmin -> Manage Hosts -> Studio-Rechner -> RDAirplay -> Now&Next Data
#
# Vorgabe: 5000

UDP_PORT = 5000

# OUT_UDP_PORT:
# OUT_UDP_IP:
# ---------
# Port und IP auf dem die Nachrichten via UDP weitergeletet werden.
# So kann ein Backup-Streamrechner parallel laufen und die Daten 
# mitschneiden.
#
# Vorgabe: 5001, 127.0.0.1

OUT_UDP_PORT = 5001
OUT_UDP_IP = "127.0.0.1" 

# WANTED_GROUPS:
# --------------
# Welche Gruppen sollen in die Plylist eingebunden werden? Namen in Rivendell
# nachsehen in rdadmin -> Manage Groups
# Groß- und Kleinschreibung beachten.

WANTED_GROUPS = ["JINGLES", "MUSIK", "MUSIK_ALT", "WORT", "TRAILER", "STATION_ID", "AUTO_TT", "AUTO", "TEASER", "ZEIT"]

# TODO: Pfade via Variable
#HIRSE_HOME="/home/ices/"
HIRSE_HOME=""

PID_FILE_DIR=HIRSE_HOME+"run/"
PID_FILE=PID_FILE_DIR+"hertz-metadata-listener.pid"
TMP_DIR=HIRSE_HOME+"tmp/"
XSPF_FRAGMENT_FILENAME=TMP_DIR+'xspf-current-fragment'
PLAIN_FRAGMENT_FILENAME=TMP_DIR+'plain-current-fragment'
CURRENT_ARTIST_FILENAME=TMP_DIR+'current.artist'
CURRENT_TITLE_FILENAME=TMP_DIR+'current.title'
HIRSE_META_SCRIPT_DIR=HIRSE_HOME+'etc/meta.d'

# Timezone for pytz. In an ideal world should be generated automatically.
LOCAL_TIMEZONE = "Europe/Berlin"

# TODO: Exceptions permission, etc
# filename must contain dirpath! (but makes that sense?)
def write_file(string, dirname, filename):
    try:
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        # TODO: Warum nicht dirname mitgeben? 
        outputfile = open(filename, 'w')
        outdata = string
        #outdata = string.encode("utf8")
        outputfile.write(outdata)
        outputfile.close()
        #debug("wrote " + string + " in " + filename + " placed at " + dirname)
    except IOError:
        e = sys.exc_info()[1]
        error_print("Error: " + e.strerror + " [" + repr(e.errno) + "]")
        # TODO: Dateirechte etc behandeln
        clean_exit(1)
    #Macht diese Exception Sinn? Sie erschwert das Debugging ungemein.
    #except Exception:
    #    e = sys.exc_info()[1]
    #    error_print("Error: " + repr(e))
    #    clean_exit(1)

# TODO: Fehlermeldungen/Debug optional in Logdatei
# http://stackoverflow.com/questions/6579496/using-print-statements-only-to-debug
# https://docs.python.org/2/howto/logging.html

# TODO: Output korrekt an log-datei (via stdout/stderr)
# Debug-Funktion
def error_print(*strings):
    # print (strings, file=sys.stderr) # logging in der shell fixen, dann auskommentieren
    print(*strings)
    sys.stdout.flush()

def debug(*strings):
    if option.verbose:
        error_print(*strings)

# Deletes Unicode control characters
# http://stackoverflow.com/a/19016117 
def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

def writePidFile():
    pid = str(os.getpid())
    debug("My PID is: " + pid)
    debug("My PID-Dir is: " + PID_FILE_DIR)
    debug("My PID-File is: " + PID_FILE)
    write_file(pid, PID_FILE_DIR, PID_FILE)

def deletePidFile():
# TODO: Exception handling
    pid_fullpath=PID_FILE_DIR+PID_FILE
    if os.path.isfile(pid_fullpath):
        os.remove(pid_fullpath)
    

def clean_exit(int):
    deletePidFile()
    sys.exit(int)

# Optionen zuweisen, die später ausgewertet werden sollen/können.
# TODO: use argparser instead?

parser = OptionParser(version="%prog 0.10", 
                      usage="usage: %prog [options]")

# Vorgabewerte für Optionen
parser.set_defaults(verbose=False)
parser.set_defaults(web=False)
parser.set_defaults(text=False)
parser.set_defaults(xspf=False)
parser.set_defaults(port=UDP_PORT)
parser.set_defaults(ip=UDP_IP)
parser.set_defaults(rdnownext=False)
parser.set_defaults(outport=OUT_UDP_PORT)
parser.set_defaults(outip=OUT_UDP_IP)

parser.add_option("-p", "--port", dest="port", type="int", help="Port to listen")
parser.add_option("-i", "--ip", dest="ip", help="IP (v4) to listen")
parser.add_option("-w", "--web", action="store_true", 
                  help="Save output for the webserver")
parser.add_option("-t", "--text", action="store_true", 
                  help="Save output in plain-text")
parser.add_option("-x", "--xspf", action="store_true", 
                  help="Save output in XSPF")
parser.add_option("-v", "--verbose", action="store_true", 
                  help="Enable verbose output")
parser.add_option("-r", "--rdnownext", action="store_true",
                  help="Simulate Rivendell Now+Next behavior. Forward received Now+Next data via UDP.")
parser.add_option("-o", "--outport", dest="outport", type="int", help="Port to forward Now+Next data.")
parser.add_option("-u", "--outip", dest="outip", help="IP to forward Now+Next data.")

# Option-Parser starten und Kommandozeilen-Optionen auslesen 
(option, args) = parser.parse_args()

# Hilfsvariable für Statusmeldungen
STATUS = ["Off", "On"]

# Ausgabe, welche Output-Formate erzeugt werden.
debug("web:  " + STATUS[int(option.web)])
debug("text: " + STATUS[int(option.text)])
debug("xspf: " + STATUS[int(option.xspf)])
debug("rdnn: " + STATUS[int(option.rdnownext)])

if not option.web and not option.text and not option.xspf:   # Kein Output aktiviert
    parser.error('No output selected.\n\t\t\t     Use at least one of -t, -w and/or -x')

# Lege PID-file an
writePidFile()

# Werte aus den Kommandozeilen-Optionen für das Skript übernehmen
UDP_IP=option.ip
UDP_PORT=option.port

CREATE_WEB=option.web
CREATE_TEXT=option.text
CREATE_XSPF=option.xspf

RECURRING_ERROR=False

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
XSPF_META_TIMESTAMP_STRING="http://stream.radiohertz.de/xspf/timestamp"

# Datei schreiben. Nimmt vorbereiten String, Pfad und Dateiname entgegen.
# Die Ausgabe-Datei wird überschrieben.


# Generate pytz-timezone object for conversion
PYTZ_OUTPUT_TIMEZONE=pytz.timezone(LOCAL_TIMEZONE)

# Removing ms from Isoformat. Expect string from datetime.isoformat()
def get_clean_xmltime(str):
    return re.sub(r'\..*?\+', '+', str)

# XML von Hand bauen. Für das bissl XSPF lohnt sich keine lib.
# Es gibt xspf.py, aber das hatte <meta> noch nicht implementiert.
# Create <track>-element for XSPF. This is only a fragment, not valid XSPF
def create_xspf_track(artist, song, group, ms, utc_date):
    date = utc_date.astimezone(PYTZ_OUTPUT_TIMEZONE)
    date_str = get_clean_xmltime(date.isoformat())
    

    try:
        xmltitle = "\t<title>"+escape(song)+"</title>\n"
        xmlcreator = "\t<creator>"+escape(artist)+"</creator>\n"
        xmlduration = "\t<duration>"+ms+"</duration>\n"
        xmlmeta = "\t<meta rel=\""+XSPF_META_TIMESTAMP_STRING+"\">"+date_str+"</meta>\n"
    except Exception:
        e = sys.exc_info()[1]
        error_print("Create XSPF Error: " + repr(e))
        xmltitle = "\t<title>Unknown Song</title>\n"
        xmlcreator = "\t<creator>Unknown Artist</creator>\n"
        xmlduration = "\t<duration>0</duration>\n"
        xmlmeta = "\t<meta rel=\""+XSPF_META_TIMESTAMP_STRING+"\">"+date_str+"</meta>\n"

    xmltrack = "<track>\n" + xmltitle + xmlcreator + xmlduration + xmlmeta + "</track>\n"
    debug("----------------\nXSPF output:\n" + xmltrack + "----------------")
    write_file(xmltrack, TMP_DIR, XSPF_FRAGMENT_FILENAME)

# Create plain-text key/value output. Depends on the options at starttime
# it creates the full file (like vorbis-format) and/or webserver files.
def create_plain_output(artist, song, group, ms, utc_date):
    date = utc_date.astimezone(PYTZ_OUTPUT_TIMEZONE)
    creator = "artist="+artist+"\n"
    title = "title="+song+"\n"
    genre = "genre="+group+"\n"
    # Hier wollen wir nur die Sekunden.
    duration = "playTime="+repr(int(round(int(ms)/1000.)))+"\n"
    year = "startYear="+repr(date.year)+"\n"
    month = "startMonth="+repr(date.month)+"\n"
    day = "startDay="+repr(date.day)+"\n"
    time = "startTime="+date.strftime("%H:%M:%S")+"\n"
    comment = 'comment=\n'

    track = creator + title + genre + duration + year + month + day + time + comment

    debug("----------------\nPlain output:" + track + "----------------")
    
    if CREATE_TEXT:
        debug("Creating plain output")
        write_file(track, TMP_DIR, PLAIN_FRAGMENT_FILENAME)
    if CREATE_WEB:
        debug("Creating output for webserver")
        write_file(artist+"\n", TMP_DIR, CURRENT_ARTIST_FILENAME)
        write_file(song+"\n", TMP_DIR, CURRENT_TITLE_FILENAME)

# Forward received data to another computer

def forward_nownext_data(data):
    outsock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
    #if(option.unicode):
    outsock.sendto(data, (OUT_UDP_IP, OUT_UDP_PORT))
    #else:
    #    sock.sendto(data.decode("utf-8").encode("iso-8859-15"), (OUT_UDP_IP, OUT_UDP_PORT))


#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
#sock.bind((UDP_IP, UDP_PORT))

# Diese Zeichenkette UDP_STRING dient nur für eine verständlichen Fehlermeldung.
UDP_STRING=UDP_IP+':'+repr(UDP_PORT)
OUT_UDP_STRING=OUT_UDP_IP+':'+repr(OUT_UDP_PORT)

# Hier lauscht das Skript konkret auf der angegebenen IP/PORT
# TODO: IPv6 ?? -> Kann Rivendell nicht.

try:
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.bind((UDP_IP, UDP_PORT))
except socket.error:
    e = sys.exc_info()[1]
    SOCK_ERR_STR = "[" + UDP_STRING +"]: "
    errorcode=e.errno
    errordesc=e.strerror
    # Fehler, die nicht zu einem exit führen sollen, sind hier nicht vorgesehen
    # Sonst sys.exit in die entsprechenden if-teile reinverschieben.
    if errorcode == errno.EADDRINUSE:
        error_print(SOCK_ERR_STR + errordesc)
        # Spezieller Exitcode für die Bash, damit wir in dem Fall warten können.
        clean_exit(5)
    elif errorcode == socket.EAI_NODATA or errno.EACCES:
         error_print(SOCK_ERR_STR + errordesc)
    elif errorcode == socket.EAI_ADDRFAMILY:
         error_print(SOCK_ERR_STR + errordesc + ". No IPv6 support, yet.")
    else:
        error_print(SOCK_ERR_STR + " Error " + repr(errorcode) + ", " + errordesc)
    clean_exit(1)
except OverflowError:
    e = sys.exc_info()[1]
    # Wir wollen nur die Beschreibung "port must be 0-65535" aus
    # OverflowError('getsockaddrarg: port must be 0-65535.',)
    errordesc=repr(e).split("'")[1].split(":")[1]
    error_print("["+UDP_STRING + "]: " + errordesc)
    clean_exit(1)
except Exception:
    e = sys.exc_info()[1]
    error_print("Unknown Error: " + repr(e))
    clean_exit(1)

# Variablen die zur Auswertung benötigt werden
artist = ""
song = ""
group = ""
ms = ""

former_artist = ""
former_song = ""

# Dauerschleife, für jedes eingehende Paket wird sie einmal durchlaufen
while True:
    try:
        debug('Listening on '+UDP_STRING) 
        if(option.rdnownext):
            debug('Forwarding to '+OUT_UDP_STRING)
            
        incoming, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
        #TODO: Nur pakte vom studiorechner annehmen
        # pseudocode: if addr=studio-pc-ip, then data = incoming, else drop
        
        # We expect ISO-8859-15 from Rivendell, we ignore everything outside
        data = incoming.decode('iso-8859-15','ignore')
        debug('Received message from '+ repr(addr) + ': ' + repr(data) )
        
        # Empfangenes Packet unbehandelt weiterleiten
        if(option.rdnownext):
            forward_nownext_data(incoming)
        
        # Empfangene Zeichenkette aufteilen.
        try:
            group, artist, song, ms, nonsense = data.rstrip('\n').split(SPLIT_CHAR)
        except ValueError:
            error_print("Ignoring packet with wrong value format: " + repr(data))
        
        # Zeichenketten von Leerzeichen etc. säubern.
        artist = remove_control_characters(artist.strip())
        song = remove_control_characters(song.strip())
        group = remove_control_characters(group.strip())
        ms = ms.strip()
        date = datetime.now(pytz.utc)
        
        # Nur die Events in die Playlist einpflegen, die wir oben angegeben haben.
        if group in WANTED_GROUPS:
            
            # ignoriere Duplikate
            if not (artist == former_artist and song == former_song):
            
                former_artist = artist
                former_song = song
                
                if CREATE_XSPF:
                    debug("Creating XSPF output")
                    create_xspf_track(artist, song, group, ms, date)
                
                if CREATE_WEB or CREATE_TEXT:
                    debug("Creating WEB/TEXT output")
                    create_plain_output(artist, song, group, ms, date)
                    
                    # TODO: run-parts  ${HIRSE_META_SCRIPT_DIR} ??
                    
                    metad_run = "run-parts"
                    
                    metad_args = [metad_run]
                    
                    metad_args.append(HIRSE_META_SCRIPT_DIR)
                    
                    p = sp.Popen(metad_args, bufsize=1)
                    p.communicate()
            else:
                debug("Ignoring duplicate " + song + "from" + artist)
        else:
            debug("Excluding GROUP: _" + group + "_")
        
        # Variablen leeren, insbesondere group, da es für "if" genutzt wird
        track = ""
        group = ""
    
    except KeyboardInterrupt:
        debug("\nExit listener by user interrupt.")
        exit(0)

#TODO: kills erkennen und sauber beenden

#TODO: main methode
#def main(argv):
#    pass

#if __name__ == "__main__":
#    main(sys.argv)


