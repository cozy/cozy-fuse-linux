import couchmount
import threading
import subprocess
import time
import sys
import requests
from multiprocessing import Process
import appindicator
import gtk
import sys
import replication
from couchdb import Database, Document, ResourceNotFound, Server
from couchdb.client import Row, ViewResults
try:
    import simplejson as json
except ImportError:
    import json # Python 2.6


database = "cozy-files"

def database_connection():
    try:
        server = Server('http://localhost:5984/')
        server.version()
        return server
    except Exception, e:
        time.sleep(5)
        database_connection()

server = Server('http://localhost:5984/')
# Read file
f = open('/etc/cozy-files/couchdb.login')
lines = f.readlines()
f.close()
username = lines[0].strip()
password = lines[1].strip()

# Add credentials
server.resource.credentials = (username, password)


def _replicate_to_local(url, pwd, name, idDevice):
    target = 'http://%s:%s@localhost:5984/%s' % (username, password, database)
    url = url.split('/')
    source = "https://%s:%s@%s/cozy" % (name, pwd, url[2])
    rep = server.replicate(source, target, continuous=True, filter="%s/filter" %idDevice)

def _replicate_from_local(url, pwd, name, idDevice):
    source = 'http://%s:%s@localhost:5984/%s' % (username, password, database)
    url = url.split('/')
    target = "https://%s:%s@%s/cozy" % (name, pwd, url[2])
    rep = server.replicate(source, target, continuous=True, filter="%s/filter" %idDevice)

def _one_shot_replicate_to_local(url, pwd, name, idDevice):
    target = 'http://%s:%s@localhost:5984/%s' % (username, password, database)
    url = url.split('/')
    source = "https://%s:%s@%s/cozy" % (name, pwd, url[2])
    rep = server.replicate(source, target, filter="%s/filter" %idDevice)

def _one_shot_replicate_from_local(url, pwd, name, idDevice):
    source = 'http://%s:%s@localhost:5984/%s' % (username, password, database)
    url = url.split('/')
    target = "https://%s:%s@%s/cozy" % (name, pwd, url[2])
    rep = server.replicate(source, target, filter="%s/filter" %idDevice)
class Menu():
    def __init__(self, fuse, repli): 
        db = server[database]

        self.ind = appindicator.Indicator (
                                  "cozy-files",
                                  "/etc/cozy-files/couchdb-fuse/icon/icon.png",
                                  appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_status (appindicator.STATUS_ACTIVE)
        self.ind.set_attention_icon ("/etc/cozy-files/couchdb-fuse/icon/icon.png")
        # create a menu
        self.menu = gtk.Menu()
        # Add line to open cozy-files folder
        folder = gtk.MenuItem("Ouvrir le fichier cozy-files")
        self.menu.append(folder)
        folder.show()
        # Add line to start synchronisation
        sync = gtk.MenuItem("Forcer une synchronisation")
        self.menu.append(sync)
        sync.show()
        # Add line to stop automatic synchronisation
        stop = gtk.MenuItem("Stopper la synchronisation automatique")
        self.menu.append(stop)
        stop.show()
        # Add line to start autmotic synchronisation
        autoSync = gtk.MenuItem("Redemarrer la synchronisation automatique")
        self.menu.append(autoSync)
        #autoSync.show()
        # Add line for preferences
        preferences = gtk.MenuItem("Preferences...")
        self.menu.append(preferences)
        preferences.show()
        # Add line to quit cozy-files
        quit = gtk.MenuItem("Quitter cozy-files")
        self.menu.append(quit)
        quit.show()

        # Display menu
        self.menu.show()
        self.ind.set_menu(self.menu)

        def _recover_path(): 
            res = db.view("device/all")
            if not res:
                time.sleep(5)
                return _recover_path(db)
            else:
                for device in res:
                    if not device.value["folder"]: 
                        time.sleep(5)
                        return _recover_path(db)
                    else:
                        return device.value['folder']


        def openFolder(item):
           path = _recover_path()
           subprocess.Popen(["xdg-open", path])

        def stopSync(item):
            # Stop binary synchronisation
            repli.terminate()
            # Stop database replication
            r = requests.get('http://localhost:5984/_active_tasks')
            replications = json.loads(r.content)
            for rep in replications:
                idRep =  str(rep["replication_id"])
                data = {"replication_id":"%s" % idRep, "cancel": True}
                r = requests.post("http://localhost:5984/_replicate", data=json.dumps(data) , headers={'Content-Type': 'application/json'})
            stop.hide()
            autoSync.show()

        def startSync(item):
           # Start metadata replication
            res = db.view("device/all")
            for device in res:
                device = device.value
                url = device['url']
                pwd = device['password']
                name = device['login']
                idDevice = device['_id']
                _one_shot_replicate_to_local(url, pwd, name, idDevice)
                _one_shot_replicate_from_local(url, pwd, name, idDevice)


        def startAutoSync(item):             
            # Start metadata replication
            res = db.view("device/all")
            for device in res:
                device = device.value
                url = device['url']
                pwd = device['password']
                name = device['login']
                idDevice = device['_id']
                _replicate_to_local(url, pwd, name, idDevice)
                _replicate_from_local(url, pwd, name, idDevice)
            # Start binaries synchronisation      
            repli = Process(target = replication.main)
            repli.start()
            stop.show()
            autoSync.hide()

        def pref(item):
            config = subprocess.call(['python','/etc/cozy-files/couchdb-fuse/preferences_window.py'])

        def exit(item):
            # Stop fuse and replication
            fuse.terminate()
            repli.terminate()
            path = _recover_path()
            # Unmount cozy-files folder
            subprocess.call(["fusermount", "-u", path])
            # Remove icon
            gtk.main_quit()

        # Add connection between menu and function
        folder.connect('activate', openFolder)
        stop.connect('activate', stopSync)
        sync.connect('activate', startSync)
        autoSync.connect('activate', startAutoSync)
        preferences.connect('activate', pref)
        quit.connect('activate', exit)

def start_prog():
    # Start fuse
    fuse = Process(target = couchmount.main)
    fuse.start()
    # Start replication
    repli = Process(target = replication.main)
    repli.start()
    # Start menu
    indicator = Menu(fuse, repli)
    gtk.main()

    #print threading.currentThread()
    fuse.join()
    #icon.join()
    repli.join()


try:
    server = database_connection()
    server = Server('http://localhost:5984/')
    db = server[database]
    r = requests.get('http://localhost:5984/_active_tasks')
    replications = json.loads(r.content)
    if len(replications) is 0:
        res = db.view("device/all")
        for device in res:
            device = device.value
            url = device['url']
            pwd = device['password']
            name = device['login']
            idDevice = device['_id']
            _replicate_to_local(url, pwd, name, idDevice)
            _replicate_from_local(url, pwd, name, idDevice)
        # Start binaries synchronisation      
        repli = Process(target = replication.main)
        repli.start()
    start_prog()
except Exception, e:
    config = subprocess.call(['python','/etc/cozy-files/couchdb-fuse/configuration_window.py'])
    if config is 0:
        end = subprocess.call(['python','/etc/cozy-files/couchdb-fuse/end_configuration.py'])
        start_prog()
    else:
        sys.exit(1)

