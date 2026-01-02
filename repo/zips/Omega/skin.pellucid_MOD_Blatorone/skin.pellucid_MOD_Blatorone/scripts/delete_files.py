import os
import shutil
import xbmc
import time

# Kodi 19/20+ kompatibel
try:
    from xbmcvfs import translatePath
except:
    translatePath = xbmc.translatePath

# Pfade
user_addons = translatePath('special://home/addons')
addon_data  = translatePath('special://profile/addon_data')

# Aktuellen Skin schützen
current_skin = xbmc.getSkinDir()
protected = { current_skin }

def delete_safe(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.isfile(path):
        try:
            os.remove(path)
        except:
            pass


# 1️⃣ WARTEN BIS KODI FERTIG GELADEN IST
monitor = xbmc.Monitor()

# Warte solange noch Busy-Dialoge laufen
while xbmc.getCondVisibility('Window.IsVisible(busydialognocancel)') \
   or xbmc.getCondVisibility('Window.IsVisible(busydialog)'):
    monitor.waitForAbort(1)


# 2️⃣ EXTRA-WARTUNG (Failsafe, z.B. 20 Sekunden)
for _ in range(20):
    if monitor.waitForAbort(1):
        raise SystemExit


# 3️⃣ USER-ADDONS LÖSCHEN (ohne Skin)
if os.path.isdir(user_addons):
    for name in os.listdir(user_addons):
        if name in protected:
            continue
        delete_safe(os.path.join(user_addons, name))


# 4️⃣ ADDON-DATEN LÖSCHEN (ohne Skin)
if os.path.isdir(addon_data):
    for name in os.listdir(addon_data):
        if name in protected:
            continue
        delete_safe(os.path.join(addon_data, name))


# 5️⃣ NEUSTART
xbmc.restart()
