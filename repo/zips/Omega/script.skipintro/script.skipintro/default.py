import sys
import xbmc
import xbmcgui
import xbmcaddon
_ = xbmcaddon.Addon().getLocalizedString
from resources.lib.series_manager import (
    toggle_service_dialog,
    toggle_auto_dialog,
    delete_series_dialog
)

def main():
    xbmc.log(f"[SkipIntro] sys.argv: {sys.argv}", xbmc.LOGINFO)

    if len(sys.argv) < 2:
        xbmcgui.Dialog().ok("SkipIntro", _(32014))
        return

    mode_param = sys.argv[1].lower()  # z. B. 'mode=toggle_service'

    if "toggle_service" in mode_param:
        toggle_service_dialog()
    elif "toggle_auto" in mode_param:
        toggle_auto_dialog()
    elif "delete" in mode_param:
        delete_series_dialog()
    else:
        xbmcgui.Dialog().ok("SkipIntro", _(32013))

if __name__ == "__main__":
    main()
