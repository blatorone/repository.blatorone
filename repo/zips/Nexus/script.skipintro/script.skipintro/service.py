# -*- coding: utf-8 -*-

"""
    TvSkipIntro Add-on — canonical year lock + auto-fill/migrate year + consolidation
    - Gleiche Schreibweise: nutze ein kanonisches Ziel (frühestes Jahr) und konsolidiere alle Varianten dahin
    - Kein Jahr erkannt -> erbe das vorhandene (früheste) Jahr
    - Eintrag ohne Jahr + jetzt Jahr -> migriere auf (YYYY)
    - Verhindert, dass für gleiche Schreibweise neue Datensätze entstehen
"""

import xbmc, xbmcvfs, xbmcaddon, json, os, xbmcgui, time, re, threading, urllib.parse

import xbmcaddon
addon = xbmcaddon.Addon()
_ = addon.getLocalizedString

KODI_VERSION = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
addonInfo = addon.getAddonInfo
settings = addon.getSetting
profilePath = xbmcvfs.translatePath(addonInfo('profile'))
addonPath = xbmcvfs.translatePath(addonInfo('path'))
skipFile = os.path.join(profilePath, 'skipintro.json')
defaultSkip = settings('default.skip')
if not os.path.exists(profilePath):
    xbmcvfs.mkdir(profilePath)

# -------------------------
# Helper
# -------------------------

def strip_decorations_from_key(key):
    if not key:
        return ''
    base = re.sub(r'\s*\[[a-zA-Z]+:[^\]]+\]\s*$', '', key)
    base = re.sub(r'\s*\(\d{4}\)\s*$', '', base)
    return base.strip()

def parse_key(key):
    base = strip_decorations_from_key(key)
    uid_type, uid = '', ''
    m_uid = re.search(r'\[([a-zA-Z]+):([^\]]+)\]\s*$', key)
    if m_uid:
        uid_type, uid = m_uid.group(1).lower(), m_uid.group(2)
    y = ''
    m_year = re.search(r'\((\d{4})\)\s*(\[[^\]]+\])?\s*$', key)
    if m_year:
        y = m_year.group(1)
    return base, y, uid_type, uid

def normalize_year(year):
    try:
        if year is None:
            return ''
        y = str(year).strip()
        if len(y) >= 4:
            digits = re.findall(r"(\d{4})", y)
            return digits[0] if digits else ''
        return y if y.isdigit() and len(y) == 4 else ''
    except Exception:
        return ''

def read_json():
    try:
        with open(skipFile, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        return data
    except Exception:
        return {}

def write_json(data):
    with open(skipFile, 'w') as f:
        json.dump(data, f, indent=2)

# --------- IDs & Jahr aus Plugins/Properties/URL ---------

TMDB_PROP_KEYS = ["tmdb_id","tmdbId","tmdbid","tmdb_show_id","themoviedb_id","tmdb"]
IMDB_PROP_KEYS = ["imdb_id","imdbId","imdbid","imdb","code"]
YEAR_PROP_KEYS = ["year","premiered","aired","firstaired","first_air_date","tvshow_year","show_year","release_date"]
YEAR_QS_KEYS = ["year","first_air_date","premiered","aired","release_date"]

def _read_videoplayer_prop(name):
    try:
        return xbmc.getInfoLabel(f"VideoPlayer.Property({name})")
    except Exception:
        return ""

def get_ids_from_player_properties():
    for k in TMDB_PROP_KEYS:
        val = _read_videoplayer_prop(k)
        if val and re.match(r"^\d+$", val):
            return ("tmdb", val)
    for k in IMDB_PROP_KEYS:
        val = _read_videoplayer_prop(k)
        if val and re.match(r"^(tt)?\d+$", val):
            if not val.startswith("tt"):
                val = "tt" + val
            return ("imdb", val)
    imdbnum = xbmc.getInfoLabel("VideoPlayer.IMDBNumber")
    if imdbnum:
        imdbnum = imdbnum.strip()
        if imdbnum and re.match(r"^(tt)?\d+$", imdbnum):
            if not imdbnum.startswith("tt"):
                imdbnum = "tt" + imdbnum
            return ("imdb", imdbnum)
    return ("","")

def get_ids_from_playing_path():
    try:
        try:
            path = xbmc.Player().getPlayingFile()
        except Exception:
            path = xbmc.getInfoLabel("Player.FilenameAndPath")
        if not path:
            return ("","")
        parsed = urllib.parse.urlparse(path)
        qs = urllib.parse.parse_qs(parsed.query)
        for key in ["tmdb_id","tmdb","tmdbId","tmdb_show_id","tmdbid","show_tmdbid","tmdb_id_tv"]:
            if key in qs and qs[key]:
                val = qs[key][0]
                if val and re.match(r"^\d+$", val):
                    return ("tmdb", val)
        for key in ["imdb_id","imdb","imdbId","imdbid","code"]:
            if key in qs and qs[key]:
                val = qs[key][0]
                if val:
                    if not val.startswith("tt"):
                        val = "tt" + re.sub(r"^tt","", val)
                    return ("imdb", val)
    except Exception:
        pass
    return ("","")

def best_year_from_props_and_path():
    for k in YEAR_PROP_KEYS:
        v = _read_videoplayer_prop(k)
        if v:
            y = normalize_year(v)
            if y:
                return y
    try:
        path = xbmc.Player().getPlayingFile()
    except Exception:
        path = xbmc.getInfoLabel("Player.FilenameAndPath")
    if path:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        for k in YEAR_QS_KEYS:
            if k in qs and qs[k]:
                y = normalize_year(qs[k][0])
                if y:
                    return y
    y = xbmc.getInfoLabel("VideoPlayer.Premiered") or xbmc.getInfoLabel("VideoPlayer.Year")
    return normalize_year(y)

def get_series_identity_via_jsonrpc_or_plugin():
    title = xbmc.getInfoLabel("VideoPlayer.TVShowTitle").strip()

    uid_type, uid = get_ids_from_player_properties()
    if not uid:
        uid_type, uid = get_ids_from_playing_path()

    year = ""
    try:
        req = {"jsonrpc":"2.0","id":1,"method":"Player.GetItem",
               "params":{"playerid":1,"properties":["tvshowid","showtitle","year","premiered"]}}
        item = json.loads(xbmc.executeJSONRPC(json.dumps(req))).get("result",{}).get("item",{})
        title = (item.get("showtitle") or title or '').strip()
        y = item.get("year") or ""
        prem = item.get("premiered") or ""
        if not y and prem:
            y = prem[:4] if len(prem) >= 4 else ""

        tvshowid = item.get("tvshowid", -1)
        if isinstance(tvshowid, int) and tvshowid >= 0:
            req2 = {"jsonrpc":"2.0","id":2,"method":"VideoLibrary.GetTVShowDetails",
                    "params":{"tvshowid":tvshowid,"properties":["title","year","premiered","uniqueid"]}}
            details = json.loads(xbmc.executeJSONRPC(json.dumps(req2))).get("result",{}).get("tvshowdetails",{})
            y2 = details.get("year") or (details.get("premiered") or "")[:4]
            year = normalize_year(y2 or y)

            if not uid:
                unique = details.get("uniqueid") or {}
                for k in ("tmdb","tvdb","imdb"):
                    if unique.get(k):
                        uid = str(unique.get(k)); uid_type = k; break
            if not uid:
                uid = str(tvshowid); uid_type = "kodi"
        else:
            year = normalize_year(y or "")
    except Exception as e:
        xbmc.log(f"[TvSkipIntro][Identity] JSON-RPC failed: {e}", xbmc.LOGERROR)
        year = ""

    if not year:
        year = best_year_from_props_and_path()

    return title, year, uid, uid_type

def build_show_key(title, year=None, uid='', uid_type=''):
    y = normalize_year(year)
    suffix = f" [{uid_type}:{uid}]" if (uid and uid_type) else ''
    return f"{title} ({y}){suffix}" if y else f"{title}{suffix}"

def ensure_identity_fields(data, key, year, uid, uid_type):
    data.setdefault(key, {})
    y = normalize_year(year)
    if not y:
        m = re.search(r'\((\d{4})\)', key or '')
        if m: y = m.group(1)
    try:
        data[key]['year'] = int(y) if y else None
    except Exception:
        data[key]['year'] = None
    if not uid or not uid_type:
        m2 = re.search(r'\[([a-zA-Z]+):([^\]]+)\]$', key or '')
        if m2:
            uid_type = m2.group(1).lower(); uid = m2.group(2)
    data[key]['uid_type'] = uid_type or ''
    data[key]['uid'] = uid or ''

# --------- Analyse & Konsolidierung gleicher Schreibweise ---------

def analyze_same_title_entries(title):
    data = read_json()
    base = (title or '').strip()
    years = []
    noyear_keys = []
    uid_list = []
    keys_same = []
    for k, v in data.items():
        base_k = strip_decorations_from_key(k)
        if base_k == base:
            keys_same.append(k)
            utype = (v.get('uid_type') or '').lower()
            uid = str(v.get('uid') or '')
            if utype and uid:
                uid_list.append((utype, uid))
            y = v.get('year')
            if isinstance(y, int):
                years.append(y)
            else:
                m = re.search(r'\((\d{4})\)', k)
                if m:
                    years.append(int(m.group(1)))
                else:
                    noyear_keys.append(k)
    return years, noyear_keys, uid_list, keys_same

def choose_canonical_year(years, incoming_year=''):
    cands = list(years)
    iy = normalize_year(incoming_year)
    if iy:
        try:
            cands.append(int(iy))
        except Exception:
            pass
    return str(min(cands)) if cands else iy

def consolidate_same_title(data, title, year, uid, uid_type):
    """Sammelt alle Keys gleicher Schreibweise ein und verschmilzt sie in einen kanonischen Ziel-Key.
       Ziel: frühestes Jahr, UID bevorzugt aus bestehenden; verhindert neue Datensätze bei gleicher Schreibweise.
    """
    years, noyear_keys, uid_list, keys_same = analyze_same_title_entries(title)
    canonical_year = choose_canonical_year(years, incoming_year=year)
    c_uid_type, c_uid = uid_type, uid
    if uid_list and not (uid and uid_type):
        c_uid_type, c_uid = uid_list[0]

    target_key = build_show_key(title, canonical_year, c_uid, c_uid_type)
    merged = data.get(target_key, {}).copy()

    # merge all same-title keys (including those with different year/none)
    for k in list(keys_same):
        if k == target_key:
            continue
        v = data.get(k, {})
        merged.update(v)  # prefer latest settings
        # keep identity fields consistent
        merged['year'] = int(canonical_year) if canonical_year else merged.get('year')
        merged['uid_type'] = c_uid_type or merged.get('uid_type','')
        merged['uid'] = c_uid or merged.get('uid','')
        del data[k]

    data[target_key] = merged
    ensure_identity_fields(data, target_key, canonical_year, c_uid, c_uid_type)
    return target_key, canonical_year, c_uid_type, c_uid

# -------------------------
# CRUD
# -------------------------

def updateSkip(title, seconds=defaultSkip, start=0, service=True, year=None):
    data = read_json()
    t, y, uid, uid_type = get_series_identity_via_jsonrpc_or_plugin()
    if title and not t:
        t = title.strip()

    # konsolidieren (gleiche Schreibweise)
    target_key, y_final, uid_type_final, uid_final = consolidate_same_title(data, t, y or year or '', uid, uid_type)

    auto_val = data.get(target_key, {}).get('auto', False)
    try:
        seconds_int = int(seconds)
    except Exception:
        seconds_int = int(defaultSkip) if str(defaultSkip).isdigit() else 0

    data[target_key] = {
        'start': int(start),
        'skip': seconds_int,
        'service': bool(service),
        'auto': bool(auto_val)
    }
    ensure_identity_fields(data, target_key, y_final, uid_final, uid_type_final)
    write_json(data)

def newskip(title, seconds, start=0, year=None):
    if not seconds:
        seconds = defaultSkip
    try:
        seconds_int = int(seconds)
    except Exception:
        seconds_int = int(defaultSkip) if str(defaultSkip).isdigit() else 0

    data = read_json()
    t, y, uid, uid_type = get_series_identity_via_jsonrpc_or_plugin()
    if title and not t:
        t = title.strip()

    target_key, y_final, uid_type_final, uid_final = consolidate_same_title(data, t, y or year or '', uid, uid_type)

    data[target_key] = {
        'start': int(start),
        'skip': seconds_int,
        'service': True,
        'auto': False
    }
    ensure_identity_fields(data, target_key, y_final, uid_final, uid_type_final)
    write_json(data)

def _lookup_record(data, title, year=None):
    t, y, uid, uid_type = get_series_identity_via_jsonrpc_or_plugin()
    if title and not t:
        t = title.strip()
    # Nach Konsolidierung sollte nur ein Key existieren
    k = None
    # exact identity first
    key = build_show_key(t, y, uid, uid_type)
    if key in data:
        k = key
    else:
        # try with provided year
        if year:
            key2 = build_show_key(t, year)
            if key2 in data:
                k = key2
    if not k:
        # any key with same base
        for kk in data.keys():
            if strip_decorations_from_key(kk) == t:
                k = kk
                break
    if k:
        return k, data.get(k)
    return None, None

def getSkip(title, year=None):
    try:
        data = read_json()
        key, value = _lookup_record(data, title, year)
        if key and value and value.get('service', True):
            return int(value.get('skip', int(defaultSkip) if str(defaultSkip).isdigit() else 0))
        raise Exception("Serie nicht gefunden oder Service deaktiviert")
    except Exception:
        newskip(title, defaultSkip, year=year)
        try:
            return int(defaultSkip)
        except Exception:
            return 0

def checkService(title, year=None):
    try:
        data = read_json()
        _k, value = _lookup_record(data, title, year)
        if value is not None:
            return bool(value.get('service', True))
    except Exception:
        pass
    return True

def checkAuto(title, year=None):
    try:
        data = read_json()
        _k, value = _lookup_record(data, title, year)
        if value is not None:
            return bool(value.get('auto', False))
    except Exception:
        pass
    return False

def checkStartTime(title, year=None):
    try:
        data = read_json()
        _k, value = _lookup_record(data, title, year)
        if value is not None:
            return int(value.get('start', 0))
    except Exception:
        pass
    return 0

# ensure file exists with a default entry for legacy behavior
if not os.path.exists(skipFile):
    with open(skipFile, 'w') as f:
        json.dump({'default': {'start': 0, 'skip': 90, 'service': True, 'auto': False}}, f, indent=2)

# -------------------------
# Service & Dialog
# -------------------------

class Service():

    WINDOW = xbmcgui.Window(10000)

    def __init__(self, *args):
        self.skipped = False
        self.currentShow = ''
        self.currentYear = ''
        self.currentUID = ''
        self.currentUIDType = ''

    def _update_current_show(self):
        title, y, uid, uid_type = get_series_identity_via_jsonrpc_or_plugin()

        # Konsolidierung direkt beim Abspielen (falls nötig)
        data = read_json()
        target_key, y_final, uid_type_final, uid_final = consolidate_same_title(data, (title or '').strip(), y, uid, uid_type)
        write_json(data)

        self.currentShow = title
        self.currentYear = y_final
        self.currentUID = uid_final
        self.currentUIDType = uid_type_final

    def ServiceEntryPoint(self):
        monitor = xbmc.Monitor()
        while not monitor.abortRequested():
            if monitor.waitForAbort(5):
                break
            if xbmc.Player().isPlaying():
                try:
                    playTime = xbmc.Player().getTime()
                    _totalTime = xbmc.Player().getTotalTime()

                    self._update_current_show()
                    if self.currentShow:
                        if playTime > 250:
                            self.skipped = True
                        if not self.skipped:
                            if checkService(self.currentShow, self.currentYear):
                                auto_enabled = checkAuto(self.currentShow, self.currentYear)
                                xbmc.log(f"[TvSkipIntro] Service aktiv: {self.currentShow} ({self.currentYear}) [{self.currentUIDType}:{self.currentUID}], Auto: {auto_enabled}", xbmc.LOGINFO)
                                if auto_enabled:
                                    self.AutoSkip(self.currentShow, self.currentYear)
                                else:
                                    self.SkipIntro(self.currentShow, self.currentYear)
                            else:
                                xbmc.log(f"[TvSkipIntro] Service deaktiviert für: {self.currentShow} ({self.currentYear}) [{self.currentUIDType}:{self.currentUID}]", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[TvSkipIntro] ServiceEntryPoint ERROR: {e}", xbmc.LOGERROR)
            else:
                self.skipped = False

    def AutoSkip(self, tvshow, year=None):
        try:
            if not xbmc.Player().isPlayingVideo():
                raise Exception("not playing video")
            timeNow = xbmc.Player().getTime()
            status = checkService(tvshow, year)
            if not status:
                self.skipped = True
                raise Exception("service off")
            startTime = checkStartTime(tvshow, year)
            skipTime = int(getSkip(tvshow, year))
            if int(timeNow) < int(startTime) + 2:
                xbmc.log(f"[TvSkipIntro] AutoSkip – Startzeit {startTime} noch nicht erreicht (aktuell {timeNow})", xbmc.LOGINFO)
                raise Exception("start not reached")
            xbmc.Player().seekTime(skipTime)
            self.skipped = True
            time.sleep(0.5)
            xbmcgui.Dialog().notification("SkipIntro", f"{_(32026)} – {tvshow}", xbmcgui.NOTIFICATION_INFO, 3000)
            Dialog = CustomDialog('script-dialog.xml', addonPath, show=tvshow, year=year, auto_triggered=True)
            Dialog.show()
            self.skipped = True
        except Exception as e:
            xbmc.log(f"[TvSkipIntro][AutoSkip] ERROR: {e}", xbmc.LOGERROR)

    def SkipIntro(self, tvshow, year=None):
        try:
            if not xbmc.Player().isPlayingVideo():
                raise Exception("not playing video")
            timeNow = xbmc.Player().getTime()
            startTime = checkStartTime(tvshow, year)
            if int(timeNow) < int(startTime):
                xbmc.log(f"[TvSkipIntro] Startzeit noch nicht erreicht: {timeNow} < {startTime}", xbmc.LOGINFO)
                raise Exception("start not reached")
            Dialog = CustomDialog('script-dialog.xml', addonPath, show=tvshow, year=year)
            Dialog.doModal()
            self.skipped = True
            del Dialog
        except Exception as e:
            xbmc.log(f"[TvSkipIntro][SkipIntro] ERROR: {e}", xbmc.LOGERROR)

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
    def __init__(self, xmlFile, resourcePath, show, year=None, auto_triggered=False):
        self.tvshow = (show or '').strip()
        t, y, uid, uid_type = get_series_identity_via_jsonrpc_or_plugin()
        if show and not t: t = self.tvshow
        data = read_json()
        target_key, y_final, uid_type_final, uid_final = consolidate_same_title(data, t, y or year or '', uid, uid_type)
        write_json(data)
        self.year = y_final
        self.uid = uid_final
        self.uid_type = uid_type_final
        self.auto_triggered = auto_triggered

    def onInit(self):
        self.skipValue = int(getSkip(self.tvshow, self.year))
        skipButton    = self.getControl(OK_BUTTON)
        newButton     = self.getControl(NEW_BUTTON)
        disableButton = self.getControl(DISABLE_BUTTON)
        if skipButton:
            skipButton.setLabel('%s: %s' % (_(32001), self.skipValue))
        if newButton:
            newButton.setLabel(_(32008))
        if disableButton:
            disableButton.setLabel(_(32009))
        if self.auto_triggered:
            threading.Thread(target=self.autoCloseAfterDelay, daemon=True).start()

    def autoCloseAfterDelay(self):
        time.sleep(10)
        if self.isActive():
            self.close()

    def onAction(self, action):
        if action == ACTION_PREVIOUS_MENU or action == ACTION_BACK:
            self.close()

    def onClick(self, control):
        if control == OK_BUTTON:
            xbmc.Player().seekTime(int(self.skipValue))
            self.close()
        if control == NEW_BUTTON:
            dialog = xbmcgui.Dialog()
            d = dialog.input(_(32002), type=xbmcgui.INPUT_NUMERIC)
            d2 = dialog.input(_(32003), type=xbmcgui.INPUT_NUMERIC)
            if d2 == '' or d2 is None:
                d2 = 0
            toggle = dialog.yesno(_(32005), _(32004))
            data = read_json()
            key = build_show_key(self.tvshow, self.year, self.uid, self.uid_type)
            try:
                skip_seconds = int(d) if d else int(defaultSkip)
            except Exception:
                skip_seconds = int(defaultSkip) if str(defaultSkip).isdigit() else 0
            data[key] = {
                'skip': skip_seconds,
                'start': int(d2),
                'service': True,
                'auto': bool(toggle)
            }
            ensure_identity_fields(data, key, self.year, self.uid, self.uid_type)
            write_json(data)
            xbmcgui.Dialog().notification('SkipIntro', f"Einstellungen gespeichert – {key}", xbmcgui.NOTIFICATION_INFO, 3000)
            self.close()
        if control == DISABLE_BUTTON:
            # reuse update to persist consolidation and disable
            updateSkip(self.tvshow, seconds=self.skipValue, service=False, year=self.year)
            xbmcgui.Dialog().notification('SkipIntro', f"Service deaktiviert – {build_show_key(self.tvshow, self.year, self.uid, self.uid_type)}", xbmcgui.NOTIFICATION_INFO, 3000)
            self.close()

Service().ServiceEntryPoint()
