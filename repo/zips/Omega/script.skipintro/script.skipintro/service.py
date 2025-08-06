# -*- coding: utf-8 -*-

'''
    TvSkipIntro Add-on
    Copyright (C) 2018 aenema

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import xbmc,xbmcvfs,xbmcaddon,json,os,xbmcgui,time,re

import xbmcaddon
_ = xbmcaddon.Addon().getLocalizedString

KODI_VERSION = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
addonInfo = xbmcaddon.Addon().getAddonInfo
settings = xbmcaddon.Addon().getSetting
profilePath = xbmcvfs.translatePath(addonInfo('profile'))
addonPath = xbmcvfs.translatePath(addonInfo('path'))
skipFile = os.path.join(profilePath, 'skipintro.json')
defaultSkip = settings('default.skip')
if not os.path.exists(profilePath): xbmcvfs.mkdir(profilePath)

def cleantitle(title):
    if title == None: return
    title = title.lower()
    title = re.sub('&#(\d+);', '', title)
    title = re.sub('(&#[0-9]+)([^;^0-9]+)', '\\1;\\2', title)
    title = title.replace('&quot;', '\"').replace('&amp;', '&')
    title = re.sub(r'\]*\>','', title)
    title = re.sub('\n|([[].+?[]])|([(].+?[)])|\s(vs|v[.])\s|(:|;|-|"|,|\'|\_|\.|\?)|\(|\)|\[|\]|\{|\}|\s', '', title).lower()
    return title.lower()
    
def updateSkip(title, seconds=defaultSkip, start=0, service=True):
    try:
        with open(skipFile, 'r') as file:
            json_data = json.load(file)
    except:
        json_data = {}

    # Titel als Key im Dictionary
    json_data[title] = {
        'start': int(start),
        'skip': int(seconds),
        'service': service,
        'auto': json_data.get(title, {}).get('auto', False)
    }

    with open(skipFile, 'w') as file:
        json.dump(json_data, file, indent=2)


def newskip(title, seconds, start=0):
    if not seconds:
        seconds = defaultSkip

    try:
        with open(skipFile, 'r') as f:
            data = json.load(f)
    except:
        data = {}

    if not isinstance(data, dict):
        data = {}

    data[title] = {
        'start': int(start),
        'skip': int(seconds),
        'service': True,
        'auto': False
    }

    with open(skipFile, 'w') as f:
        json.dump(data, f, indent=2)


def getSkip(title):
    try:
        with open(skipFile) as f:
            data = json.load(f)

        for key, value in data.items():
            if cleantitle(key) == cleantitle(title) and value.get('service', True):
                return value.get('skip', int(defaultSkip))

        raise Exception("Serie nicht gefunden oder Service deaktiviert")
    except:
        newskip(title, defaultSkip)
        return int(defaultSkip)

    
def checkService(title):
    try:
        with open(skipFile) as f:
            data = json.load(f)
        for key, value in data.items():
            if cleantitle(key) == cleantitle(title):
                return value.get('service', True)
    except:
        pass
    return True

def checkAuto(title):
    try:
        with open(skipFile) as f:
            data = json.load(f)
        for key, value in data.items():
            if cleantitle(key) == cleantitle(title):
                return value.get('auto', False)
    except:
        pass
    return False

def checkStartTime(title):
    try:
        with open(skipFile) as f:
            data = json.load(f)
        for key, value in data.items():
            if cleantitle(key) == cleantitle(title):
                return int(value.get('start', 0))
    except:
        pass
    return 0
    
if not os.path.exists(skipFile): newskip('default', defaultSkip)


class Service():

    WINDOW = xbmcgui.Window(10000)

    def __init__(self, *args):
        addonName = 'Skip Player'
        self.skipped = False



    def ServiceEntryPoint(self):
        monitor = xbmc.Monitor()


        while not monitor.abortRequested():
            # check every 5 sec
            if monitor.waitForAbort(5):
                # Abort was requested while waiting. We should exit
                break
            if xbmc.Player().isPlaying():
                try:
                    playTime = xbmc.Player().getTime()

                    totalTime = xbmc.Player().getTotalTime()

                    self.currentShow = xbmc.getInfoLabel("VideoPlayer.TVShowTitle")
                    if self.currentShow: 
                        
                        if playTime > 250: self.skipped = True
                        if not self.skipped:
                            if checkService(self.currentShow):
                                auto_enabled = checkAuto(self.currentShow)
                                print(f"[DEBUG] Service aktiv: {self.currentShow}, Auto: {auto_enabled}")
                                if auto_enabled:
                                    self.AutoSkip(self.currentShow)
                                else:
                                 self.SkipIntro(self.currentShow)
                            else:
                                print(f"[DEBUG] Service deaktiviert für: {self.currentShow}")
                except:pass
            else: self.skipped = False
                
    
    def AutoSkip(self, tvshow):
        try:
            if not xbmc.Player().isPlayingVideo():
                raise Exception()

            timeNow = xbmc.Player().getTime()
            status = checkService(tvshow)
            if not status:
                self.skipped = True
                raise Exception()

            startTime = checkStartTime(tvshow)
            skipTime = int(getSkip(tvshow))

            if int(timeNow) < int(startTime):
                print(f"[DEBUG] AutoSkip – Startzeit {startTime} noch nicht erreicht (aktuell {timeNow})")
                raise Exception()

            xbmc.Player().seekTime(skipTime)
            self.skipped = True
            time.sleep(0.5)
            
            xbmcgui.Dialog().notification("SkipIntro", f"{_(32026)} – {tvshow}", xbmcgui.NOTIFICATION_INFO, 3000)

            Dialog = CustomDialog('script-dialog.xml', addonPath, show=tvshow, auto_triggered=True)
            self.skipped = True
            self.close()
        except Exception as e:
            print(f"[AutoSkip ERROR] {e}")


    def SkipIntro(self, tvshow):
        try:
            if not xbmc.Player().isPlayingVideo():
                raise Exception()

            timeNow = xbmc.Player().getTime()
            startTime = checkStartTime(tvshow)

            if int(timeNow) < int(startTime):
                print(f"[DEBUG] Startzeit noch nicht erreicht: {timeNow} < {startTime}")
                raise Exception()

            Dialog = CustomDialog('script-dialog.xml', addonPath, show=tvshow)
            Dialog.doModal()
            self.skipped = True
            del Dialog

        except Exception as e:
         print(f"[SkipIntro ERROR] {e}")

OK_BUTTON = 201
NEW_BUTTON = 202
DISABLE_BUTTON = 210
TOGGLE_SERVICE_BUTTON = 211
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
INSTRUCTION_LABEL = 203
AUTHCODE_LABEL = 204
WARNING_LABEL = 205
CENTER_Y = 6
CENTER_X = 2

class CustomDialog(xbmcgui.WindowXMLDialog):

    def __init__(self, xmlFile, resourcePath, show, auto_triggered=False):
        self.tvshow = show
        self.auto_triggered = auto_triggered

    def onInit(self):
        instuction = ''
        self.skipValue = int(getSkip(self.tvshow))
        skipLabel = '%s: %s' % (_(32001), self.skipValue)
        skipButton = self.getControl(OK_BUTTON)
        if skipButton:
            skipButton.setLabel(skipLabel)

            newButton = self.getControl(NEW_BUTTON)
        if newButton:
            newButton.setLabel(_(32008))

            disableButton = self.getControl(DISABLE_BUTTON)
        if disableButton:
            disableButton.setLabel(_(32009))

        print("[Dialog] geöffnet – auto_triggered:", self.auto_triggered)

        if self.auto_triggered:
            for i in range(20):  # 100 x 100ms = 10 Sekunden
             xbmc.sleep(20)
            if not self.isActive():
                print("[Dialog] wurde manuell geschlossen")
                return
        if self.isActive():
            print("[Dialog] Auto-Close nach 10 Sekunden")
            self.close()
        
    def autoCloseAfterDelay(self):
        time.sleep(10)
        if self.isActive():
            self.close()

    def onAction(self, action):
        if action == ACTION_PREVIOUS_MENU or action == ACTION_BACK:
            self.close()

    def onControl(self, control):
        pass

    def onFocus(self, control):
        pass

    def onClick(self, control):
        print(('onClick: %s' % (control)))

        if control == OK_BUTTON:
            timeNow = xbmc.Player().getTime()
            skipTotal = int(self.skipValue)
            xbmc.Player().seekTime(int(skipTotal))          

        
        if control == NEW_BUTTON:
            dialog = xbmcgui.Dialog()
            d = dialog.input(_(32002), type=xbmcgui.INPUT_NUMERIC)
            d2 = dialog.input(_(32003), type=xbmcgui.INPUT_NUMERIC)
            if d2 == '' or d2 is None: d2 = 0
            toggle = dialog.yesno(_(32005), _(32004))
            self.close()

            try:
               with open(skipFile) as f:
                data = json.load(f)
            except:
                data = {}

            if not isinstance(data, dict):
                data = {}

            data[self.tvshow] = {
                'skip': int(d) if d else int(defaultSkip),
                'start': int(d2),
                'service': True,
                'auto': toggle
            }

            with open(skipFile, 'w') as f:
                json.dump(data, f, indent=2)


            xbmcgui.Dialog().notification(_(32005), f"{status_label} – {self.tvshow}", xbmcgui.NOTIFICATION_INFO, 3000)


                    
            
        if control == DISABLE_BUTTON:
            updateSkip(self.tvshow, seconds=self.skipValue, service=False)
            
        #if control == TOGGLE_SERVICE_BUTTON:
        #    try:
         #       with open(skipFile) as f:
         #           data = json.load(f)
         #   except:
         #       data = []

         #   for item in data:
         #       if cleantitle(item['title']) == cleantitle(self.tvshow):
        #            item['service'] = not item.get('service', True)
         #           status = item['service']
         #           break

        #    with open(skipFile, 'w') as f:
        #        json.dump(data, f, indent=2)

        #    xbmcgui.Dialog().notification('Service-Status', f"{'Aktiviert' if status else 'Deaktiviert'} für {self.tvshow}", xbmcgui.NOTIFICATION_INFO, 3000)
            self.close()


        if control in [OK_BUTTON, NEW_BUTTON, DISABLE_BUTTON,TOGGLE_SERVICE_BUTTON]:
            self.close()
            
Service().ServiceEntryPoint()
