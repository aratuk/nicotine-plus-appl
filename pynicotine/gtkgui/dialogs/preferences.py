# COPYRIGHT (C) 2020-2021 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2016 Mutnick <muhing@yahoo.com>
# COPYRIGHT (C) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2008 Gallows <g4ll0ws@gmail.com>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import socket
import sys
import time

import gi
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from pynicotine.config import config
from pynicotine.gtkgui.widgets.filechooser import FileChooserButton
from pynicotine.gtkgui.widgets.filechooser import choose_dir
from pynicotine.gtkgui.widgets.filechooser import save_file
from pynicotine.gtkgui.widgets.dialogs import dialog_hide
from pynicotine.gtkgui.widgets.dialogs import dialog_show
from pynicotine.gtkgui.widgets.dialogs import entry_dialog
from pynicotine.gtkgui.widgets.dialogs import generic_dialog
from pynicotine.gtkgui.widgets.dialogs import message_dialog
from pynicotine.gtkgui.widgets.dialogs import set_dialog_properties
from pynicotine.gtkgui.widgets.textview import TextView
from pynicotine.gtkgui.widgets.theme import get_icon
from pynicotine.gtkgui.widgets.theme import set_dark_mode
from pynicotine.gtkgui.widgets.theme import set_global_font
from pynicotine.gtkgui.widgets.theme import update_widget_visuals
from pynicotine.gtkgui.widgets.treeview import initialise_columns
from pynicotine.gtkgui.widgets.ui import UserInterface
from pynicotine.logfacility import log
from pynicotine.utils import open_file_path
from pynicotine.utils import open_uri
from pynicotine.utils import unescape


class NetworkFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/network.ui")

        self.p = parent
        self.frame = self.p.frame

        self.needportmap = False

        self.options = {
            "server": {
                "server": None,
                "login": self.Login,
                "portrange": None,
                "autoaway": self.AutoAway,
                "autoreply": self.AutoReply,
                "interface": self.Interface,
                "upnp": self.UseUPnP,
                "upnp_interval": self.UPnPInterval,
                "auto_connect_startup": self.AutoConnectStartup,
                "ctcpmsgs": self.ctcptogglebutton
            }
        }

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        server = config.sections["server"]

        if server["server"] is not None:
            self.Server.set_text("%s:%i" % (server["server"][0], server["server"][1]))

        if self.frame.np.protothread.listenport is None:
            self.CurrentPort.set_text(_("Listening port is not set"))
        else:
            text = _("Public IP address is <b>%(ip)s</b> and active listening port is <b>%(port)s</b>") % {
                "ip": self.frame.np.user_ip_address or _("unknown"),
                "port": self.frame.np.protothread.listenport
            }
            self.CurrentPort.set_markup(text)

        url = config.portchecker_url % str(self.frame.np.protothread.listenport)
        text = "<a href='" + url + "' title='" + url + "'>" + _("Check Port Status") + "</a>"
        self.CheckPortLabel.set_markup(text)
        self.CheckPortLabel.connect("activate-link", lambda x, url: open_uri(url))

        if server["portrange"] is not None:
            self.FirstPort.set_value(server["portrange"][0])
            self.LastPort.set_value(server["portrange"][1])

        if server["ctcpmsgs"] is not None:
            self.ctcptogglebutton.set_active(not server["ctcpmsgs"])

        self.needportmap = False
        self.on_toggle_upnp(self.UseUPnP)

        if sys.platform not in ("linux", "darwin"):
            for widget in (self.InterfaceLabel, self.Interface):
                widget.get_parent().hide()

            return

        self.Interface.remove_all()
        self.Interface.append_text("")

        try:
            for _i, interface in socket.if_nameindex():
                self.Interface.append_text(interface)

        except (AttributeError, OSError):
            pass

    def get_settings(self):

        try:
            server = self.Server.get_text().split(":")
            server[1] = int(server[1])
            server = tuple(server)

        except Exception:
            server = config.defaults["server"]["server"]

        firstport = min(self.FirstPort.get_value_as_int(), self.LastPort.get_value_as_int())
        lastport = max(self.FirstPort.get_value_as_int(), self.LastPort.get_value_as_int())
        portrange = (firstport, lastport)

        return {
            "server": {
                "server": server,
                "login": self.Login.get_text(),
                "portrange": portrange,
                "autoaway": self.AutoAway.get_value_as_int(),
                "autoreply": self.AutoReply.get_text(),
                "interface": self.Interface.get_active_text(),
                "upnp": self.UseUPnP.get_active(),
                "upnp_interval": self.UPnPInterval.get_value_as_int(),
                "auto_connect_startup": self.AutoConnectStartup.get_active(),
                "ctcpmsgs": not self.ctcptogglebutton.get_active()
            }
        }

    def on_change_password_response(self, dialog, response_id, logged_in):

        password = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if logged_in != self.p.frame.np.logged_in:
            message_dialog(
                parent=self.p.dialog,
                title=_("Password Change Rejected"),
                message=("Since your login status changed, your password has not been changed. Please try again.")
            )
            return

        if not password:
            self.on_change_password()
            return

        if not self.p.frame.np.logged_in:
            config.sections["server"]["passw"] = password
            config.write_configuration()
            return

        self.frame.np.request_change_password(password)

    def on_change_password(self, *args):

        if self.p.frame.np.logged_in:
            message = _("Enter a new password for your Soulseek account:")
        else:
            message = (_("You are currently logged out of the Soulseek network. If you want to change "
                         "the password of an existing Soulseek account, you need to be logged into that account.")
                       + "\n\n"
                       + _("Enter password to use when logging in:"))

        entry_dialog(
            parent=self.p.dialog,
            title=_("Change Password"),
            message=message,
            visibility=False,
            callback=self.on_change_password_response,
            callback_data=self.p.frame.np.logged_in
        )

    def on_toggle_upnp(self, widget, *args):

        active = widget.get_active()
        self.needportmap = active

        self.UPnPInterval.get_parent().set_sensitive(active)

    def on_modify_upnp_interval(self, widget, *args):
        self.needportmap = True


class DownloadsFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/downloads.ui")

        self.p = parent
        self.frame = self.p.frame
        self.needrescan = False

        self.IncompleteDir = FileChooserButton(self.IncompleteDir, parent.dialog, "folder")
        self.DownloadDir = FileChooserButton(self.DownloadDir, parent.dialog, "folder")
        self.UploadDir = FileChooserButton(self.UploadDir, parent.dialog, "folder")

        self.options = {
            "transfers": {
                "autoclear_downloads": self.AutoclearFinished,
                "lock": self.LockIncoming,
                "reverseorder": self.DownloadReverseOrder,
                "remotedownloads": self.RemoteDownloads,
                "uploadallowed": self.UploadsAllowed,
                "incompletedir": self.IncompleteDir,
                "downloaddir": self.DownloadDir,
                "uploaddir": self.UploadDir,
                "downloadfilters": self.FilterView,
                "enablefilters": self.DownloadFilter,
                "downloadlimit": self.DownloadSpeed,
                "downloadlimitalt": self.DownloadSpeedAlternative,
                "usernamesubfolders": self.UsernameSubfolders,
                "afterfinish": self.AfterDownload,
                "afterfolder": self.AfterFolder,
                "download_doubleclick": self.DownloadDoubleClick
            }
        }

        self.filterlist = Gtk.ListStore(
            str,
            bool
        )

        self.downloadfilters = []

        self.column_numbers = list(range(self.filterlist.get_n_columns()))
        cols = initialise_columns(
            None, self.FilterView,
            ["filter", _("Filter"), -1, "text", None],
            ["escaped", _("Escaped"), 40, "toggle", None]
        )

        cols["filter"].set_sort_column_id(0)
        cols["escaped"].set_sort_column_id(1)
        renderers = cols["escaped"].get_cells()

        for render in renderers:
            render.connect('toggled', self.cell_toggle_callback, self.filterlist, 1)

        self.FilterView.set_model(self.filterlist)

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        self.UploadsAllowed.get_parent().set_sensitive(self.RemoteDownloads.get_active())

        self.filtersiters = {}
        self.filterlist.clear()

        if config.sections["transfers"]["downloadfilters"]:
            for dfilter in config.sections["transfers"]["downloadfilters"]:
                dfilter, escaped = dfilter
                self.filtersiters[dfilter] = self.filterlist.insert_with_valuesv(
                    -1, self.column_numbers, [str(dfilter), bool(escaped)]
                )

        self.needrescan = False

    def get_settings(self):

        try:
            uploadallowed = self.UploadsAllowed.get_active()
        except Exception:
            uploadallowed = 0

        if not self.RemoteDownloads.get_active():
            uploadallowed = 0

        return {
            "transfers": {
                "autoclear_downloads": self.AutoclearFinished.get_active(),
                "lock": self.LockIncoming.get_active(),
                "reverseorder": self.DownloadReverseOrder.get_active(),
                "remotedownloads": self.RemoteDownloads.get_active(),
                "uploadallowed": uploadallowed,
                "incompletedir": self.IncompleteDir.get_path(),
                "downloaddir": self.DownloadDir.get_path(),
                "uploaddir": self.UploadDir.get_path(),
                "downloadfilters": self.get_filter_list(),
                "enablefilters": self.DownloadFilter.get_active(),
                "downloadlimit": self.DownloadSpeed.get_value_as_int(),
                "downloadlimitalt": self.DownloadSpeedAlternative.get_value_as_int(),
                "usernamesubfolders": self.UsernameSubfolders.get_active(),
                "afterfinish": self.AfterDownload.get_text(),
                "afterfolder": self.AfterFolder.get_text(),
                "download_doubleclick": self.DownloadDoubleClick.get_active()
            }
        }

    def on_remote_downloads(self, widget):
        sensitive = widget.get_active()
        self.UploadsAllowed.get_parent().set_sensitive(sensitive)

    def on_add_filter_response(self, dialog, response_id, data):

        dfilter = dialog.get_response_value()
        escaped = dialog.get_second_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if dfilter in self.filtersiters:
            self.filterlist.set(self.filtersiters[dfilter], 0, dfilter, 1, escaped)
        else:
            self.filtersiters[dfilter] = self.filterlist.insert_with_valuesv(
                -1, self.column_numbers, [dfilter, escaped]
            )

        self.on_verify_filter(self.VerifyFilters)

    def on_add_filter(self, *args):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Add Download Filter"),
            message=_("Enter a new download filter:"),
            callback=self.on_add_filter_response,
            option=True,
            optionvalue=True,
            optionmessage="Escape this filter?",
            droplist=list(self.filtersiters.keys())
        )

    def get_filter_list(self):

        self.downloadfilters = []

        df = sorted(self.filtersiters.keys())

        for dfilter in df:
            iterator = self.filtersiters[dfilter]
            dfilter = self.filterlist.get_value(iterator, 0)
            escaped = self.filterlist.get_value(iterator, 1)
            self.downloadfilters.append([dfilter, int(escaped)])

        return self.downloadfilters

    def on_edit_filter_response(self, dialog, response_id, data):

        new_dfilter = dialog.get_response_value()
        escaped = dialog.get_second_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        dfilter = self.get_selected_filter()

        if not dfilter:
            return

        iterator = self.filtersiters[dfilter]

        if new_dfilter in self.filtersiters:
            self.filterlist.set(self.filtersiters[new_dfilter], 0, new_dfilter, 1, escaped)
        else:
            self.filtersiters[new_dfilter] = self.filterlist.insert_with_valuesv(
                -1, self.column_numbers, [new_dfilter, escaped]
            )
            del self.filtersiters[dfilter]
            self.filterlist.remove(iterator)

        self.on_verify_filter(self.VerifyFilters)

    def on_edit_filter(self, *args):

        dfilter = self.get_selected_filter()

        if not dfilter:
            return

        iterator = self.filtersiters[dfilter]
        escapedvalue = self.filterlist.get_value(iterator, 1)

        entry_dialog(
            parent=self.p.dialog,
            title=_("Edit Download Filter"),
            message=_("Modify the following download filter:"),
            callback=self.on_edit_filter_response,
            default=dfilter,
            option=True,
            optionvalue=escapedvalue,
            optionmessage="Escape this filter?",
            droplist=list(self.filtersiters.keys())
        )

    def get_selected_filter(self):

        model, paths = self.FilterView.get_selection().get_selected_rows()

        for path in paths:
            iterator = model.get_iter(path)
            return model.get_value(iterator, 0)

        return None

    def on_remove_filter(self, *args):

        dfilter = self.get_selected_filter()

        if not dfilter:
            return

        iterator = self.filtersiters[dfilter]
        self.filterlist.remove(iterator)

        del self.filtersiters[dfilter]

        self.on_verify_filter(self.VerifyFilters)

    def on_default_filters(self, *args):

        self.filtersiters = {}
        self.filterlist.clear()

        for dfilter in config.defaults["transfers"]["downloadfilters"]:
            dfilter, escaped = dfilter
            self.filtersiters[dfilter] = self.filterlist.insert_with_valuesv(
                -1, self.column_numbers, [dfilter, escaped]
            )

        self.on_verify_filter(self.VerifyFilters)

    def on_verify_filter(self, widget):

        outfilter = "(\\\\("

        df = sorted(self.filtersiters.keys())

        proccessedfilters = []
        failed = {}

        for dfilter in df:

            iterator = self.filtersiters[dfilter]
            dfilter = self.filterlist.get_value(iterator, 0)
            escaped = self.filterlist.get_value(iterator, 1)

            if escaped:
                dfilter = re.escape(dfilter)
                dfilter = dfilter.replace("\\*", ".*")
            else:
                # Avoid "Nothing to repeat" error
                dfilter = dfilter.replace("*", "\\*").replace("+", "\\+")

            try:
                re.compile("(" + dfilter + ")")
                outfilter += dfilter
                proccessedfilters.append(dfilter)
            except Exception as e:
                failed[dfilter] = e

            if filter is not df[-1]:
                outfilter += "|"

        outfilter += ")$)"

        try:
            re.compile(outfilter)

        except Exception as e:
            failed[outfilter] = e

        if failed:
            errors = ""

            for dfilter, error in failed.items():
                errors += "Filter: %(filter)s Error: %(error)s " % {
                    'filter': dfilter,
                    'error': error
                }

            error = _("%(num)d Failed! %(error)s " % {
                'num': len(failed),
                'error': errors}
            )

            self.VerifiedLabel.set_markup("<span foreground=\"#e04f5e\">%s</span>" % error)
        else:
            self.VerifiedLabel.set_text(_("Filters Successful"))

    def cell_toggle_callback(self, widget, index, treeview, pos):

        iterator = self.filterlist.get_iter(index)
        value = self.filterlist.get_value(iterator, pos)

        self.filterlist.set(iterator, pos, not value)

        self.on_verify_filter(self.VerifyFilters)


class SharesFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/shares.ui")

        self.p = parent
        self.frame = self.p.frame

        self.needrescan = False
        self.shareddirs = []
        self.bshareddirs = []

        self.shareslist = Gtk.ListStore(
            str,
            str,
            bool
        )

        self.Shares.set_model(self.shareslist)
        self.column_numbers = list(range(self.shareslist.get_n_columns()))
        cols = initialise_columns(
            None, self.Shares,
            ["virtual_folder", _("Virtual Folder"), 0, "text", None],
            ["folder", _("Folder"), -1, "text", None],
            ["buddies", _("Buddy-only"), 0, "toggle", None],
        )

        cols["virtual_folder"].set_sort_column_id(0)
        cols["folder"].set_sort_column_id(1)
        cols["buddies"].set_sort_column_id(2)

        for render in cols["buddies"].get_cells():
            render.connect('toggled', self.cell_toggle_callback, self.Shares)

        self.options = {
            "transfers": {
                "rescanonstartup": self.RescanOnStartup,
                "buddysharestrustedonly": self.BuddySharesTrustedOnly
            }
        }

    def set_settings(self):

        transfers = config.sections["transfers"]
        self.shareslist.clear()

        self.p.set_widgets_data(self.options)

        for (virtual, actual, *unused) in transfers["buddyshared"]:

            self.shareslist.insert_with_valuesv(-1, self.column_numbers, [
                str(virtual),
                str(actual),
                True
            ])

        for (virtual, actual, *unused) in transfers["shared"]:

            self.shareslist.insert_with_valuesv(-1, self.column_numbers, [
                str(virtual),
                str(actual),
                False
            ])

        self.shareddirs = transfers["shared"][:]
        self.bshareddirs = transfers["buddyshared"][:]

        self.needrescan = False

    def get_settings(self):

        return {
            "transfers": {
                "shared": self.shareddirs[:],
                "buddyshared": self.bshareddirs[:],
                "rescanonstartup": self.RescanOnStartup.get_active(),
                "buddysharestrustedonly": self.BuddySharesTrustedOnly.get_active()
            }
        }

    def on_share_download_dir_toggled(self, widget):
        self.needrescan = True

    def set_shared_dir_buddy_only(self, iterator, buddy_only):

        if buddy_only == self.shareslist.get_value(iterator, 2):
            return

        virtual = self.shareslist.get_value(iterator, 0)
        directory = self.shareslist.get_value(iterator, 1)
        share = (virtual, directory)
        self.needrescan = True

        self.shareslist.set_value(iterator, 2, buddy_only)

        if buddy_only:
            self.shareddirs.remove(share)
            self.bshareddirs.append(share)
            return

        self.bshareddirs.remove(share)
        self.shareddirs.append(share)

    def cell_toggle_callback(self, widget, index, treeview):

        store = treeview.get_model()
        iterator = store.get_iter(index)

        buddy_only = not self.shareslist.get_value(iterator, 2)
        self.set_shared_dir_buddy_only(iterator, buddy_only)

    def add_shared_dir(self, folder):

        if folder is None:
            return

        # If the directory is already shared
        if folder in (x[1] for x in self.shareddirs + self.bshareddirs):
            return

        virtual = os.path.basename(os.path.normpath(folder))

        # Remove slashes from share name to avoid path conflicts
        virtual = virtual.replace('/', '_').replace('\\', '_')
        virtual_final = virtual

        # If the virtual share name is not already used
        counter = 1
        while virtual_final in (x[0] for x in self.shareddirs + self.bshareddirs):
            virtual_final = virtual + str(counter)
            counter += 1

        iterator = self.shareslist.insert_with_valuesv(-1, self.column_numbers, [
            virtual_final,
            folder,
            False
        ])

        self.Shares.set_cursor(self.shareslist.get_path(iterator))
        self.Shares.grab_focus()

        self.shareddirs.append((virtual_final, folder))
        self.needrescan = True

    def on_add_shared_dir_selected(self, selected, data):

        for folder in selected:
            self.add_shared_dir(folder)

    def on_add_shared_dir(self, *args):

        choose_dir(
            parent=self.p.dialog,
            callback=self.on_add_shared_dir_selected,
            title=_("Add a Shared Folder")
        )

    def on_edit_shared_dir_response(self, dialog, response_id, path):

        virtual = dialog.get_response_value()
        buddy_only = dialog.get_second_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if not virtual:
            return

        # Remove slashes from share name to avoid path conflicts
        iterator = self.shareslist.get_iter(path)
        virtual = virtual.replace('/', '_').replace('\\', '_')
        directory = self.shareslist.get_value(iterator, 1)
        oldvirtual = self.shareslist.get_value(iterator, 0)
        oldmapping = (oldvirtual, directory)
        newmapping = (virtual, directory)

        self.set_shared_dir_buddy_only(iterator, buddy_only)
        self.shareslist.set_value(iterator, 0, virtual)

        if oldmapping in self.bshareddirs:
            shared_dirs = self.bshareddirs
        else:
            shared_dirs = self.shareddirs

        shared_dirs.remove(oldmapping)
        shared_dirs.append(newmapping)

        self.needrescan = True

    def on_edit_shared_dir(self, *args):

        model, paths = self.Shares.get_selection().get_selected_rows()

        for path in paths:
            iterator = model.get_iter(path)
            virtual_name = model.get_value(iterator, 0)
            folder = model.get_value(iterator, 1)
            buddy_only = model.get_value(iterator, 2)

            entry_dialog(
                parent=self.p.dialog,
                title=_("Edit Shared Folder"),
                message=_("Enter new virtual name for '%(dir)s':") % {'dir': folder},
                default=virtual_name,
                option=True,
                optionvalue=buddy_only,
                optionmessage="Share with buddies only?",
                callback=self.on_edit_shared_dir_response,
                callback_data=path
            )
            return

    def on_remove_shared_dir(self, *args):

        model, paths = self.Shares.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            virtual = model.get_value(iterator, 0)
            actual = model.get_value(iterator, 1)
            mapping = (virtual, actual)

            if mapping in self.bshareddirs:
                self.bshareddirs.remove(mapping)
            else:
                self.shareddirs.remove(mapping)

            model.remove(iterator)

        if paths:
            self.needrescan = True


class UploadsFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/uploads.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "transfers": {
                "autoclear_uploads": self.AutoclearFinished,
                "uploadbandwidth": self.QueueBandwidth,
                "useupslots": self.QueueUseSlots,
                "uploadslots": self.QueueSlots,
                "uselimit": self.Limit,
                "uploadlimit": self.LimitSpeed,
                "uploadlimitalt": self.LimitSpeedAlternative,
                "fifoqueue": self.FirstInFirstOut,
                "limitby": self.LimitTotalTransfers,
                "queuelimit": self.MaxUserQueue,
                "filelimit": self.MaxUserFiles,
                "friendsnolimits": self.FriendsNoLimits,
                "preferfriends": self.PreferFriends,
                "upload_doubleclick": self.UploadDoubleClick
            }
        }

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        self.on_queue_use_slots_toggled(self.QueueUseSlots)
        self.on_limit_toggled(self.Limit)

    def get_settings(self):

        return {
            "transfers": {
                "autoclear_uploads": self.AutoclearFinished.get_active(),
                "uploadbandwidth": self.QueueBandwidth.get_value_as_int(),
                "useupslots": self.QueueUseSlots.get_active(),
                "uploadslots": self.QueueSlots.get_value_as_int(),
                "uselimit": self.Limit.get_active(),
                "uploadlimit": self.LimitSpeed.get_value_as_int(),
                "uploadlimitalt": self.LimitSpeedAlternative.get_value_as_int(),
                "fifoqueue": bool(self.FirstInFirstOut.get_active()),
                "limitby": self.LimitTotalTransfers.get_active(),
                "queuelimit": self.MaxUserQueue.get_value_as_int(),
                "filelimit": self.MaxUserFiles.get_value_as_int(),
                "friendsnolimits": self.FriendsNoLimits.get_active(),
                "preferfriends": self.PreferFriends.get_active(),
                "upload_doubleclick": self.UploadDoubleClick.get_active()
            }
        }

    def on_queue_use_slots_toggled(self, widget):

        sensitive = widget.get_active()

        self.QueueSlots.get_parent().set_sensitive(sensitive)

        self.QueueBandwidth.get_parent().set_sensitive(not sensitive)
        self.QueueBandwidthText1.get_parent().set_sensitive(not sensitive)

    def on_limit_toggled(self, widget):
        sensitive = widget.get_active()
        self.LimitSpeed.get_parent().set_sensitive(sensitive)


class UserInfoFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/userinfo.ui")

        self.p = parent
        self.frame = self.p.frame

        self.ImageChooser = FileChooserButton(self.ImageChooser, parent.dialog, "image")

        self.options = {
            "userinfo": {
                "descr": None,
                "pic": self.ImageChooser
            }
        }

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        if config.sections["userinfo"]["descr"] is not None:
            descr = unescape(config.sections["userinfo"]["descr"])
            self.Description.get_buffer().set_text(descr)

    def get_settings(self):

        buffer = self.Description.get_buffer()

        start = buffer.get_start_iter()
        end = buffer.get_end_iter()

        descr = buffer.get_text(start, end, True).replace("; ", ", ").__repr__()

        return {
            "userinfo": {
                "descr": descr,
                "pic": self.ImageChooser.get_path()
            }
        }

    def on_default_image(self, widget):
        self.ImageChooser.clear()


class IgnoredUsersFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/ignore.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "server": {
                "ignorelist": self.IgnoredUsers,
                "ipignorelist": self.IgnoredIPs
            }
        }

        self.ignored_users = []
        self.ignorelist = Gtk.ListStore(str)

        self.user_column_numbers = list(range(self.ignorelist.get_n_columns()))
        cols = initialise_columns(
            None, self.IgnoredUsers,
            ["username", _("Username"), -1, "text", None]
        )
        cols["username"].set_sort_column_id(0)

        self.IgnoredUsers.set_model(self.ignorelist)

        self.ignored_ips = {}
        self.ignored_ips_list = Gtk.ListStore(str, str)

        self.ip_column_numbers = list(range(self.ignored_ips_list.get_n_columns()))
        cols = initialise_columns(
            None, self.IgnoredIPs,
            ["ip_address", _("IP Address"), -1, "text", None],
            ["user", _("User"), -1, "text", None]
        )
        cols["ip_address"].set_sort_column_id(0)
        cols["user"].set_sort_column_id(1)

        self.IgnoredIPs.set_model(self.ignored_ips_list)

    def set_settings(self):
        server = config.sections["server"]

        self.ignorelist.clear()
        self.ignored_ips_list.clear()
        self.ignored_users = []
        self.ignored_ips = {}
        self.p.set_widgets_data(self.options)

        if server["ignorelist"] is not None:
            self.ignored_users = server["ignorelist"][:]

        if server["ipignorelist"] is not None:
            self.ignored_ips = server["ipignorelist"].copy()
            for ip, user in self.ignored_ips.items():
                self.ignored_ips_list.insert_with_valuesv(-1, self.ip_column_numbers, [
                    str(ip), str(user)
                ])

    def get_settings(self):
        return {
            "server": {
                "ignorelist": self.ignored_users[:],
                "ipignorelist": self.ignored_ips.copy()
            }
        }

    def on_add_ignored_response(self, dialog, response_id, data):

        user = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if user and user not in self.ignored_users:
            self.ignored_users.append(user)
            self.ignorelist.insert_with_valuesv(-1, self.user_column_numbers, [str(user)])

    def on_add_ignored(self, widget):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Ignore User"),
            message=_("Enter the name of the user you want to ignore:"),
            callback=self.on_add_ignored_response
        )

    def on_remove_ignored(self, widget):

        model, paths = self.IgnoredUsers.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            user = model.get_value(iterator, 0)

            model.remove(iterator)
            self.ignored_users.remove(user)

    def on_add_ignored_ip_response(self, dialog, response_id, data):

        ip = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if ip is None or ip == "" or ip.count(".") != 3:
            return

        for chars in ip.split("."):

            if chars == "*":
                continue
            if not chars.isdigit():
                return

            try:
                if int(chars) > 255:
                    return
            except Exception:
                return

        if ip not in self.ignored_ips:
            self.ignored_ips[ip] = ""
            self.ignored_ips_list.insert_with_valuesv(-1, self.ip_column_numbers, [ip, ""])

    def on_add_ignored_ip(self, widget):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Ignore IP Address"),
            message=_("Enter an IP address you want to ignore:") + " " + _("* is a wildcard"),
            callback=self.on_add_ignored_ip_response
        )

    def on_remove_ignored_ip(self, widget):

        model, paths = self.IgnoredIPs.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            ip = model.get_value(iterator, 0)

            model.remove(iterator)
            del self.ignored_ips[ip]


class BannedUsersFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/ban.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "server": {
                "banlist": self.BannedList,
                "ipblocklist": self.BlockedList
            },
            "transfers": {
                "usecustomban": self.UseCustomBan,
                "customban": self.CustomBan,
                "geoblock": self.GeoBlock,
                "geoblockcc": self.GeoBlockCC,
                "usecustomgeoblock": self.UseCustomGeoBlock,
                "customgeoblock": self.CustomGeoBlock
            }
        }

        self.banlist = []
        self.banlist_model = Gtk.ListStore(str)

        self.ban_column_numbers = list(range(self.banlist_model.get_n_columns()))
        cols = initialise_columns(
            None, self.BannedList,
            ["username", _("Username"), -1, "text", None]
        )
        cols["username"].set_sort_column_id(0)

        self.BannedList.set_model(self.banlist_model)

        self.blocked_list = {}
        self.blocked_list_model = Gtk.ListStore(str, str)

        self.block_column_numbers = list(range(self.blocked_list_model.get_n_columns()))
        cols = initialise_columns(
            None, self.BlockedList,
            ["ip_address", _("IP Address"), -1, "text", None],
            ["user", _("User"), -1, "text", None]
        )
        cols["ip_address"].set_sort_column_id(0)
        cols["user"].set_sort_column_id(1)

        self.BlockedList.set_model(self.blocked_list_model)

    def set_settings(self):

        self.need_ip_block = False
        server = config.sections["server"]
        self.banlist_model.clear()
        self.blocked_list_model.clear()

        self.banlist = server["banlist"][:]
        self.p.set_widgets_data(self.options)

        self.on_country_codes_toggled(self.GeoBlock)

        if config.sections["transfers"]["geoblockcc"] is not None:
            self.GeoBlockCC.set_text(config.sections["transfers"]["geoblockcc"][0])

        self.on_use_custom_geo_block_toggled(self.UseCustomGeoBlock)
        self.on_use_custom_ban_toggled(self.UseCustomBan)

        if server["ipblocklist"] is not None:
            self.blocked_list = server["ipblocklist"].copy()
            for blocked, user in server["ipblocklist"].items():
                self.blocked_list_model.insert_with_valuesv(-1, self.block_column_numbers, [
                    str(blocked),
                    str(user)
                ])

    def get_settings(self):
        return {
            "server": {
                "banlist": self.banlist[:],
                "ipblocklist": self.blocked_list.copy()
            },
            "transfers": {
                "usecustomban": self.UseCustomBan.get_active(),
                "customban": self.CustomBan.get_text(),
                "geoblock": self.GeoBlock.get_active(),
                "geoblockcc": [self.GeoBlockCC.get_text().upper()],
                "usecustomgeoblock": self.UseCustomGeoBlock.get_active(),
                "customgeoblock": self.CustomGeoBlock.get_text()
            }
        }

    def on_country_codes_toggled(self, widget):
        self.GeoBlockCC.get_parent().set_sensitive(widget.get_active())

    def on_use_custom_geo_block_toggled(self, widget):
        self.CustomGeoBlock.get_parent().set_sensitive(widget.get_active())

    def on_use_custom_ban_toggled(self, widget):
        self.CustomBan.get_parent().set_sensitive(widget.get_active())

    def on_add_banned_response(self, dialog, response_id, data):

        user = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if user and user not in self.banlist:
            self.banlist.append(user)
            self.banlist_model.insert_with_valuesv(-1, self.ban_column_numbers, [user])

    def on_add_banned(self, widget):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Ban User"),
            message=_("Enter the name of the user you want to ban:"),
            callback=self.on_add_banned_response
        )

    def on_remove_banned(self, widget):

        model, paths = self.BannedList.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            user = model.get_value(iterator, 0)

            model.remove(iterator)
            self.banlist.remove(user)

    def on_add_blocked_response(self, dialog, response_id, data):

        ip = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if ip is None or ip == "" or ip.count(".") != 3:
            return

        for chars in ip.split("."):

            if chars == "*":
                continue
            if not chars.isdigit():
                return

            try:
                if int(chars) > 255:
                    return
            except Exception:
                return

        if ip not in self.blocked_list:
            self.blocked_list[ip] = ""
            self.blocked_list_model.insert_with_valuesv(-1, self.block_column_numbers, [ip, ""])
            self.need_ip_block = True

    def on_add_blocked(self, widget):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Block IP Address"),
            message=_("Enter an IP address you want to block:") + " " + _("* is a wildcard"),
            callback=self.on_add_blocked_response
        )

    def on_remove_blocked(self, widget):

        model, paths = self.BlockedList.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            ip = model.get_value(iterator, 0)

            self.blocked_list_model.remove(iterator)
            del self.blocked_list[ip]


class ChatsFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/chats.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "logging": {
                "readroomlines": self.RoomLogLines,
                "readprivatelines": self.PrivateLogLines,
                "readroomlogs": self.ReadRoomLogs,
                "rooms_timestamp": self.ChatRoomFormat,
                "private_timestamp": self.PrivateChatFormat
            },
            "privatechat": {
                "store": self.ReopenPrivateChats
            },
            "words": {
                "tab": self.CompletionTabCheck,
                "cycle": self.CompletionCycleCheck,
                "dropdown": self.CompletionDropdownCheck,
                "characters": self.CharactersCompletion,
                "roomnames": self.CompleteRoomNamesCheck,
                "buddies": self.CompleteBuddiesCheck,
                "roomusers": self.CompleteUsersInRoomsCheck,
                "commands": self.CompleteCommandsCheck,
                "aliases": self.CompleteAliasesCheck,
                "onematch": self.OneMatchCheck,
                "censored": self.CensorList,
                "censorwords": self.CensorCheck,
                "censorfill": self.CensorReplaceCombo,
                "autoreplaced": self.ReplacementList,
                "replacewords": self.ReplaceCheck
            },
            "ui": {
                "spellcheck": self.SpellCheck,
                "speechenabled": self.TextToSpeech,
                "speechcommand": self.TTSCommand,
                "speechrooms": self.RoomMessage,
                "speechprivate": self.PrivateMessage
            }
        }

        self.censor_list_model = Gtk.ListStore(str)

        cols = initialise_columns(
            None, self.CensorList,
            ["pattern", _("Pattern"), -1, "edit", None]
        )
        cols["pattern"].set_sort_column_id(0)

        self.CensorList.set_model(self.censor_list_model)

        renderers = cols["pattern"].get_cells()
        for render in renderers:
            render.connect('edited', self.censor_cell_edited_callback, self.CensorList, 0)

        self.replace_list_model = Gtk.ListStore(str, str)

        self.column_numbers = list(range(self.replace_list_model.get_n_columns()))
        cols = initialise_columns(
            None, self.ReplacementList,
            ["pattern", _("Pattern"), 150, "edit", None],
            ["replacement", _("Replacement"), -1, "edit", None]
        )
        cols["pattern"].set_sort_column_id(0)
        cols["replacement"].set_sort_column_id(1)

        self.ReplacementList.set_model(self.replace_list_model)

        pos = 0
        for (column_id, column) in cols.items():
            renderers = column.get_cells()
            for render in renderers:
                render.connect('edited', self.replace_cell_edited_callback, self.ReplacementList, pos)

            pos += 1

    def on_completion_changed(self, widget):
        self.needcompletion = True

    def on_default_private(self, widget):
        self.PrivateMessage.set_text(config.defaults["ui"]["speechprivate"])

    def on_default_rooms(self, widget):
        self.RoomMessage.set_text(config.defaults["ui"]["speechrooms"])

    def on_default_tts(self, widget):
        self.TTSCommand.get_child().set_text(config.defaults["ui"]["speechcommand"])

    def on_room_default_timestamp(self, widget):
        self.ChatRoomFormat.set_text(config.defaults["logging"]["rooms_timestamp"])

    def on_private_default_timestamp(self, widget):
        self.PrivateChatFormat.set_text(config.defaults["logging"]["private_timestamp"])

    def censor_cell_edited_callback(self, widget, index, value, treeview, pos):

        store = treeview.get_model()
        iterator = store.get_iter(index)

        if value != "" and not value.isspace() and len(value) > 2:
            store.set(iterator, pos, value)
        else:
            store.remove(iterator)

    def replace_cell_edited_callback(self, widget, index, value, treeview, pos):

        store = treeview.get_model()
        iterator = store.get_iter(index)
        store.set(iterator, pos, value)

    def on_add_censored_response(self, dialog, response_id, data):

        pattern = dialog.get_response_value()
        dialog.destroy()

        if response_id != Gtk.ResponseType.OK:
            return

        if pattern:
            self.censor_list_model.insert_with_valuesv(-1, [0], [pattern])

    def on_add_censored(self, widget):

        entry_dialog(
            parent=self.p.dialog,
            title=_("Censor Pattern"),
            message=_("Enter a pattern you want to censor. Add spaces around the pattern if you don't "
                      "want to match strings inside words (may fail at the beginning and end of lines)."),
            callback=self.on_add_censored_response
        )

    def on_remove_censored(self, widget):

        model, paths = self.CensorList.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            model.remove(iterator)

    def on_add_replacement(self, widget):

        iterator = self.replace_list_model.insert_with_valuesv(-1, self.column_numbers, ["", ""])
        selection = self.ReplacementList.get_selection()
        selection.select_iter(iterator)
        col = self.ReplacementList.get_column(0)

        self.ReplacementList.set_cursor(self.replace_list_model.get_path(iterator), col, True)

    def on_remove_replacement(self, widget):

        model, paths = self.ReplacementList.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            model.remove(iterator)

    def set_settings(self):

        self.censor_list_model.clear()
        self.replace_list_model.clear()

        self.p.set_widgets_data(self.options)

        self.needcompletion = False

        try:
            gi.require_version('Gspell', '1')
            from gi.repository import Gspell  # noqa: F401

        except (ImportError, ValueError):
            self.SpellCheck.hide()

        for i in ("%(user)s", "%(message)s"):
            if i not in config.sections["ui"]["speechprivate"]:
                self.default_private(None)

            if i not in config.sections["ui"]["speechrooms"]:
                self.default_rooms(None)

        for word, replacement in config.sections["words"]["autoreplaced"].items():
            self.replace_list_model.insert_with_valuesv(-1, self.column_numbers, [
                str(word),
                str(replacement)
            ])

    def get_settings(self):

        censored = []
        autoreplaced = {}

        iterator = self.censor_list_model.get_iter_first()

        while iterator is not None:
            word = self.censor_list_model.get_value(iterator, 0)
            censored.append(word)
            iterator = self.censor_list_model.iter_next(iterator)

        iterator = self.replace_list_model.get_iter_first()

        while iterator is not None:
            word = self.replace_list_model.get_value(iterator, 0)
            replacement = self.replace_list_model.get_value(iterator, 1)
            autoreplaced[word] = replacement
            iterator = self.replace_list_model.iter_next(iterator)

        return {
            "logging": {
                "readroomlogs": self.ReadRoomLogs.get_active(),
                "readroomlines": self.RoomLogLines.get_value_as_int(),
                "readprivatelines": self.PrivateLogLines.get_value_as_int(),
                "private_timestamp": self.PrivateChatFormat.get_text(),
                "rooms_timestamp": self.ChatRoomFormat.get_text()
            },
            "privatechat": {
                "store": self.ReopenPrivateChats.get_active()
            },
            "words": {
                "tab": self.CompletionTabCheck.get_active(),
                "cycle": self.CompletionCycleCheck.get_active(),
                "dropdown": self.CompletionDropdownCheck.get_active(),
                "characters": self.CharactersCompletion.get_value_as_int(),
                "roomnames": self.CompleteRoomNamesCheck.get_active(),
                "buddies": self.CompleteBuddiesCheck.get_active(),
                "roomusers": self.CompleteUsersInRoomsCheck.get_active(),
                "commands": self.CompleteCommandsCheck.get_active(),
                "aliases": self.CompleteAliasesCheck.get_active(),
                "onematch": self.OneMatchCheck.get_active(),
                "censored": censored,
                "censorwords": self.CensorCheck.get_active(),
                "censorfill": self.CensorReplaceCombo.get_active_id(),
                "autoreplaced": autoreplaced,
                "replacewords": self.ReplaceCheck.get_active()
            },
            "ui": {
                "spellcheck": self.SpellCheck.get_active(),
                "speechenabled": self.TextToSpeech.get_active(),
                "speechcommand": self.TTSCommand.get_active_text(),
                "speechrooms": self.RoomMessage.get_text(),
                "speechprivate": self.PrivateMessage.get_text()
            }
        }


class UserInterfaceFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/userinterface.ui")

        self.p = parent
        self.frame = self.p.frame
        self.needcolors = False

        self.ThemeDir = FileChooserButton(self.ThemeDir, parent.dialog, "folder")

        self.tabs = {
            "search": self.EnableSearchTab,
            "downloads": self.EnableDownloadsTab,
            "uploads": self.EnableUploadsTab,
            "userbrowse": self.EnableUserBrowseTab,
            "userinfo": self.EnableUserInfoTab,
            "private": self.EnablePrivateTab,
            "userlist": self.EnableUserListTab,
            "chatrooms": self.EnableChatroomsTab,
            "interests": self.EnableInterestsTab
        }

        # Tab positions
        for combobox in (self.MainPosition, self.ChatRoomsPosition, self.PrivateChatPosition,
                         self.SearchPosition, self.UserInfoPosition, self.UserBrowsePosition):
            combobox.append("Top", _("Top"))
            combobox.append("Bottom", _("Bottom"))
            combobox.append("Left", _("Left"))
            combobox.append("Right", _("Right"))

        # Icon preview
        icon_list = [
            (get_icon("online"), _("Connected"), 16),
            (get_icon("offline"), _("Disconnected"), 16),
            (get_icon("away"), _("Away"), 16),
            (get_icon("hilite"), _("Highlight"), 16),
            (get_icon("hilite3"), _("Highlight"), 16),
            (get_icon("n"), _("Window"), 64),
            (get_icon("notify"), _("Notification"), 64)]

        if sys.platform != "darwin" and Gtk.get_major_version() != 4:
            icon_list += [
                (get_icon("trayicon_connect"), _("Connected (Tray)"), 16),
                (get_icon("trayicon_disconnect"), _("Disconnected (Tray)"), 16),
                (get_icon("trayicon_away"), _("Away (Tray)"), 16),
                (get_icon("trayicon_msg"), _("Message (Tray)"), 16)]

        for pixbuf, label, pixel_size in icon_list:
            box = Gtk.Box()
            box.set_orientation(Gtk.Orientation.VERTICAL)
            box.set_valign(Gtk.Align.CENTER)
            box.set_spacing(6)
            box.show()

            icon = Gtk.Image.new_from_pixbuf(pixbuf)
            icon.set_pixel_size(pixel_size)
            icon.show()

            label = Gtk.Label.new(label)
            label.show()

            box.add(icon)
            box.add(label)

            self.IconView.insert(box, -1)

        self.options = {
            "notifications": {
                "notification_tab_colors": self.NotificationTabColors,
                "notification_window_title": self.NotificationWindowTitle,
                "notification_popup_sound": self.NotificationPopupSound,
                "notification_popup_file": self.NotificationPopupFile,
                "notification_popup_folder": self.NotificationPopupFolder,
                "notification_popup_private_message": self.NotificationPopupPrivateMessage,
                "notification_popup_chatroom": self.NotificationPopupChatroom,
                "notification_popup_chatroom_mention": self.NotificationPopupChatroomMention
            },
            "ui": {
                "globalfont": self.SelectGlobalFont,
                "chatfont": self.SelectChatFont,
                "listfont": self.SelectListFont,
                "searchfont": self.SelectSearchFont,
                "transfersfont": self.SelectTransfersFont,
                "browserfont": self.SelectBrowserFont,
                "usernamestyle": self.UsernameStyle,

                "file_path_tooltips": self.FilePathTooltips,
                "reverse_file_paths": self.ReverseFilePaths,

                "tabmain": self.MainPosition,
                "tabrooms": self.ChatRoomsPosition,
                "tabprivate": self.PrivateChatPosition,
                "tabsearch": self.SearchPosition,
                "tabinfo": self.UserInfoPosition,
                "tabbrowse": self.UserBrowsePosition,
                "tab_select_previous": self.TabSelectPrevious,
                "tabclosers": self.TabClosers,
                "tab_status_icons": self.TabStatusIcons,

                "icontheme": self.ThemeDir,

                "chatlocal": self.EntryLocal,
                "chatremote": self.EntryRemote,
                "chatme": self.EntryMe,
                "chathilite": self.EntryHighlight,
                "textbg": self.EntryBackground,
                "inputcolor": self.EntryInput,
                "search": self.EntryImmediate,
                "searchq": self.EntryQueue,
                "useraway": self.EntryAway,
                "useronline": self.EntryOnline,
                "useroffline": self.EntryOffline,
                "usernamehotspots": self.UsernameHotspots,
                "urlcolor": self.EntryURL,
                "tab_default": self.EntryRegularTab,
                "tab_hilite": self.EntryHighlightTab,
                "tab_changed": self.EntryChangedTab,
                "dark_mode": self.DarkMode,
                "exitdialog": self.CloseAction,
                "trayicon": self.TrayiconCheck,
                "startup_hidden": self.StartupHidden
            }
        }

        self.colorsd = {
            "ui": {
                "chatlocal": self.PickLocal,
                "chatremote": self.PickRemote,
                "chatme": self.PickMe,
                "chathilite": self.PickHighlight,
                "textbg": self.PickBackground,
                "inputcolor": self.PickInput,
                "search": self.PickImmediate,
                "searchq": self.PickQueue,
                "useraway": self.PickAway,
                "useronline": self.PickOnline,
                "useroffline": self.PickOffline,
                "urlcolor": self.PickURL,
                "tab_default": self.PickRegularTab,
                "tab_hilite": self.PickHighlightTab,
                "tab_changed": self.PickChangedTab
            }
        }

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        if sys.platform == "darwin" or Gtk.get_major_version() == 4:
            # Tray icons don't work as expected on macOS
            self.hide_tray_icon_settings()
        else:
            sensitive = self.TrayiconCheck.get_active()
            self.StartupHidden.set_sensitive(sensitive)

        for page_id, enabled in config.sections["ui"]["modes_visible"].items():
            widget = self.tabs.get(page_id)

            if widget is not None:
                widget.set_active(enabled)

        self.update_color_buttons()
        self.needcolors = False

    def get_settings(self):

        enabled_tabs = {}

        for page_id, widget in self.tabs.items():
            enabled_tabs[page_id] = widget.get_active()

        return {
            "notifications": {
                "notification_tab_colors": self.NotificationTabColors.get_active(),
                "notification_window_title": self.NotificationWindowTitle.get_active(),
                "notification_popup_sound": self.NotificationPopupSound.get_active(),
                "notification_popup_file": self.NotificationPopupFile.get_active(),
                "notification_popup_folder": self.NotificationPopupFolder.get_active(),
                "notification_popup_private_message": self.NotificationPopupPrivateMessage.get_active(),
                "notification_popup_chatroom": self.NotificationPopupChatroom.get_active(),
                "notification_popup_chatroom_mention": self.NotificationPopupChatroomMention.get_active()
            },
            "ui": {
                "globalfont": self.SelectGlobalFont.get_font(),
                "chatfont": self.SelectChatFont.get_font(),
                "listfont": self.SelectListFont.get_font(),
                "searchfont": self.SelectSearchFont.get_font(),
                "transfersfont": self.SelectTransfersFont.get_font(),
                "browserfont": self.SelectBrowserFont.get_font(),
                "usernamestyle": self.UsernameStyle.get_active_id(),

                "file_path_tooltips": self.FilePathTooltips.get_active(),
                "reverse_file_paths": self.ReverseFilePaths.get_active(),

                "tabmain": self.MainPosition.get_active_id(),
                "tabrooms": self.ChatRoomsPosition.get_active_id(),
                "tabprivate": self.PrivateChatPosition.get_active_id(),
                "tabsearch": self.SearchPosition.get_active_id(),
                "tabinfo": self.UserInfoPosition.get_active_id(),
                "tabbrowse": self.UserBrowsePosition.get_active_id(),
                "modes_visible": enabled_tabs,
                "tab_select_previous": self.TabSelectPrevious.get_active(),
                "tabclosers": self.TabClosers.get_active(),
                "tab_status_icons": self.TabStatusIcons.get_active(),

                "icontheme": self.ThemeDir.get_path(),

                "chatlocal": self.EntryLocal.get_text(),
                "chatremote": self.EntryRemote.get_text(),
                "chatme": self.EntryMe.get_text(),
                "chathilite": self.EntryHighlight.get_text(),
                "urlcolor": self.EntryURL.get_text(),
                "textbg": self.EntryBackground.get_text(),
                "inputcolor": self.EntryInput.get_text(),
                "search": self.EntryImmediate.get_text(),
                "searchq": self.EntryQueue.get_text(),
                "useraway": self.EntryAway.get_text(),
                "useronline": self.EntryOnline.get_text(),
                "useroffline": self.EntryOffline.get_text(),
                "usernamehotspots": self.UsernameHotspots.get_active(),
                "tab_hilite": self.EntryHighlightTab.get_text(),
                "tab_default": self.EntryRegularTab.get_text(),
                "tab_changed": self.EntryChangedTab.get_text(),
                "dark_mode": self.DarkMode.get_active(),
                "exitdialog": self.CloseAction.get_active(),
                "trayicon": self.TrayiconCheck.get_active(),
                "startup_hidden": self.StartupHidden.get_active()
            }
        }

    """ Tray """

    def hide_tray_icon_settings(self):

        # Hide widgets
        self.TraySettings.hide()

    def on_toggle_tray(self, widget):

        self.StartupHidden.set_sensitive(widget.get_active())

        if not widget.get_active() and self.StartupHidden.get_active():
            self.StartupHidden.set_active(widget.get_active())

    """ Icons """

    def on_default_theme(self, widget):
        self.ThemeDir.clear()

    """ Fonts """

    def on_default_font(self, widget):

        font_button = getattr(self, Gtk.Buildable.get_name(widget).replace("Default", "Select"))
        font_button.set_font_name("")

        self.needcolors = True

    def on_fonts_changed(self, widget):
        self.needcolors = True

    """ Colors """

    def update_color_button(self, config, color_id):

        for section, value in self.colorsd.items():
            if color_id in value:
                color_button = self.colorsd[section][color_id]
                rgba = Gdk.RGBA()

                rgba.parse(config[section][color_id])
                color_button.set_rgba(rgba)
                break

    def update_color_buttons(self):

        for section, color_ids in self.colorsd.items():
            for color_id in color_ids:
                self.update_color_button(config.sections, color_id)

    def set_default_color(self, section, color_id):

        defaults = config.defaults
        widget = self.options[section][color_id]

        if isinstance(widget, Gtk.Entry):
            widget.set_text(defaults[section][color_id])

        self.update_color_button(defaults, color_id)

    def clear_color(self, section, color_id):

        widget = self.options[section][color_id]

        if isinstance(widget, Gtk.Entry):
            widget.set_text("")

        color_button = self.colorsd[section][color_id]
        color_button.set_rgba(Gdk.RGBA())

    def on_color_set(self, widget):

        rgba = widget.get_rgba()
        color = "#%02X%02X%02X" % (round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))
        entry = getattr(self, Gtk.Buildable.get_name(widget).replace("Pick", "Entry"))
        entry.set_text(color)

    def on_default_color(self, widget):

        entry = getattr(self, Gtk.Buildable.get_name(widget).replace("Default", "Entry"))

        for section in self.options:
            for key, value in self.options[section].items():
                if value is entry:
                    self.set_default_color(section, key)
                    return

        entry.set_text("")

    def on_colors_changed(self, widget):

        if isinstance(widget, Gtk.Entry):
            rgba = Gdk.RGBA()
            rgba.parse(widget.get_text())

            color_button = getattr(self, Gtk.Buildable.get_name(widget).replace("Entry", "Pick"))
            color_button.set_rgba(rgba)

        self.needcolors = True


class LoggingFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/log.ui")

        self.p = parent
        self.frame = self.p.frame

        self.PrivateLogDir = FileChooserButton(self.PrivateLogDir, parent.dialog, "folder")
        self.RoomLogDir = FileChooserButton(self.RoomLogDir, parent.dialog, "folder")
        self.TransfersLogDir = FileChooserButton(self.TransfersLogDir, parent.dialog, "folder")
        self.DebugLogDir = FileChooserButton(self.DebugLogDir, parent.dialog, "folder")

        self.options = {
            "logging": {
                "privatechat": self.LogPrivate,
                "privatelogsdir": self.PrivateLogDir,
                "chatrooms": self.LogRooms,
                "roomlogsdir": self.RoomLogDir,
                "transfers": self.LogTransfers,
                "transferslogsdir": self.TransfersLogDir,
                "debug_file_output": self.LogDebug,
                "debuglogsdir": self.DebugLogDir,
                "log_timestamp": self.LogFileFormat
            }
        }

    def set_settings(self):
        self.p.set_widgets_data(self.options)

    def get_settings(self):

        return {
            "logging": {
                "privatechat": self.LogPrivate.get_active(),
                "privatelogsdir": self.PrivateLogDir.get_path(),
                "chatrooms": self.LogRooms.get_active(),
                "roomlogsdir": self.RoomLogDir.get_path(),
                "transfers": self.LogTransfers.get_active(),
                "transferslogsdir": self.TransfersLogDir.get_path(),
                "debug_file_output": self.LogDebug.get_active(),
                "debuglogsdir": self.DebugLogDir.get_path(),
                "log_timestamp": self.LogFileFormat.get_text()
            }
        }

    def on_default_timestamp(self, widget):
        self.LogFileFormat.set_text(config.defaults["logging"]["log_timestamp"])


class SearchesFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/search.ui")

        self.p = parent
        self.frame = self.p.frame

        self.filter_help = UserInterface("ui/popovers/searchfilters.ui")
        self.ShowSearchHelp.set_popover(self.filter_help.popover)

        if Gtk.get_major_version() == 4:
            button = self.ShowSearchHelp.get_first_child()
            button.set_child(self.FilterHelpLabel)
            button.get_style_context().remove_class("image-button")
        else:
            self.ShowSearchHelp.add(self.FilterHelpLabel)

        self.options = {
            "searches": {
                "maxresults": self.MaxResults,
                "enablefilters": self.EnableFilters,
                "re_filter": self.RegexpFilters,
                "defilter": None,
                "search_results": self.ToggleResults,
                "max_displayed_results": self.MaxDisplayedResults,
                "min_search_chars": self.MinSearchChars,
                "remove_special_chars": self.RemoveSpecialChars,
                "enable_history": self.EnableSearchHistory,
                "private_search_results": self.ShowPrivateSearchResults
            }
        }

    def set_settings(self):

        try:
            searches = config.sections["searches"]
        except Exception:
            searches = None

        self.p.set_widgets_data(self.options)

        if searches["defilter"] is not None:
            self.FilterIn.set_text(str(searches["defilter"][0]))
            self.FilterOut.set_text(str(searches["defilter"][1]))
            self.FilterSize.set_text(str(searches["defilter"][2]))
            self.FilterBR.set_text(str(searches["defilter"][3]))
            self.FilterFree.set_active(searches["defilter"][4])

            if len(searches["defilter"]) > 5:
                self.FilterCC.set_text(str(searches["defilter"][5]))

            if len(searches["defilter"]) > 6:
                self.FilterType.set_text(str(searches["defilter"][6]))

        self.ClearSearchHistorySuccess.hide()
        self.ClearFilterHistorySuccess.hide()

    def get_settings(self):

        return {
            "searches": {
                "maxresults": self.MaxResults.get_value_as_int(),
                "enablefilters": self.EnableFilters.get_active(),
                "re_filter": self.RegexpFilters.get_active(),
                "defilter": [
                    self.FilterIn.get_text(),
                    self.FilterOut.get_text(),
                    self.FilterSize.get_text(),
                    self.FilterBR.get_text(),
                    self.FilterFree.get_active(),
                    self.FilterCC.get_text(),
                    self.FilterType.get_text()
                ],
                "search_results": self.ToggleResults.get_active(),
                "max_displayed_results": self.MaxDisplayedResults.get_value_as_int(),
                "min_search_chars": self.MinSearchChars.get_value_as_int(),
                "remove_special_chars": self.RemoveSpecialChars.get_active(),
                "enable_history": self.EnableSearchHistory.get_active(),
                "private_search_results": self.ShowPrivateSearchResults.get_active()
            }
        }

    def on_clear_search_history(self, widget):
        self.frame.search.clear_search_history()
        self.ClearSearchHistorySuccess.show()

    def on_clear_filter_history(self, widget):
        self.frame.search.clear_filter_history()
        self.ClearFilterHistorySuccess.show()


class UrlHandlersFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/urlhandlers.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "urls": {
                "protocols": None
            },
            "ui": {
                "filemanager": self.FileManagerCombo
            },
            "players": {
                "default": self.audioPlayerCombo
            }
        }

        self.protocolmodel = Gtk.ListStore(str, str)
        self.protocols = {}

        self.column_numbers = list(range(self.protocolmodel.get_n_columns()))
        cols = initialise_columns(
            None, self.ProtocolHandlers,
            ["protocol", _("Protocol"), -1, "text", None],
            ["command", _("Command"), -1, "combo", None]
        )

        cols["protocol"].set_sort_column_id(0)
        cols["command"].set_sort_column_id(1)

        self.ProtocolHandlers.set_model(self.protocolmodel)

        renderers = cols["command"].get_cells()
        for render in renderers:
            render.connect('edited', self.cell_edited_callback, self.ProtocolHandlers, 1)

    def set_settings(self):

        self.protocolmodel.clear()
        self.protocols.clear()

        self.p.set_widgets_data(self.options)

        for key in config.sections["urls"]["protocols"].keys():
            if config.sections["urls"]["protocols"][key][-1:] == "&":
                command = config.sections["urls"]["protocols"][key][:-1].rstrip()
            else:
                command = config.sections["urls"]["protocols"][key]

            self.protocols[key] = self.protocolmodel.insert_with_valuesv(-1, self.column_numbers, [
                str(key), str(command)
            ])

    def get_settings(self):

        protocols = {}
        iterator = self.protocolmodel.get_iter_first()

        while iterator is not None:
            protocol = self.protocolmodel.get_value(iterator, 0)
            handler = self.protocolmodel.get_value(iterator, 1)
            protocols[protocol] = handler

            iterator = self.protocolmodel.iter_next(iterator)

        return {
            "urls": {
                "protocols": protocols
            },
            "ui": {
                "filemanager": self.FileManagerCombo.get_active_text()
            },
            "players": {
                "default": self.audioPlayerCombo.get_active_text()
            }
        }

    def cell_edited_callback(self, widget, index, value, treeview, pos):

        store = treeview.get_model()
        iterator = store.get_iter(index)
        store.set(iterator, pos, value)

    def on_add(self, widget):

        protocol = self.ProtocolCombo.get_active_text()
        command = self.Handler.get_active_text()

        self.ProtocolCombo.get_child().set_text("")
        self.Handler.get_child().set_text("")

        if protocol in self.protocols:
            self.protocolmodel.set(self.protocols[protocol], 1, command)
        else:
            self.protocols[protocol] = self.protocolmodel.insert_with_valuesv(
                -1, self.column_numbers, [protocol, command]
            )

    def on_remove(self, widget):

        model, paths = self.ProtocolHandlers.get_selection().get_selected_rows()

        for path in reversed(paths):
            iterator = model.get_iter(path)
            protocol = self.protocolmodel.get_value(iterator, 0)

            model.remove(iterator)
            del self.protocols[protocol]


class NowPlayingFrame(UserInterface):

    def __init__(self, parent):

        super().__init__("ui/settings/nowplaying.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "players": {
                "npothercommand": self.NPCommand
            }
        }

        self.player_replacers = []

        # Default format list
        self.default_format_list = [
            "$n",
            "$n ($f)",
            "$a - $t",
            "[$a] $t",
            "$a - $b - $t",
            "$a - $b - $t ($l/$r KBps) from $y $c"
        ]
        self.custom_format_list = []

        # Suppy the information needed for the Now Playing class to return a song
        self.test_now_playing.connect(
            "clicked",
            self.p.frame.np.now_playing.display_now_playing,
            self.set_now_playing_example,  # Callback to update the song displayed
            self.get_player,               # Callback to retrieve selected player
            self.get_command,              # Callback to retrieve command text
            self.get_format                # Callback to retrieve format text
        )

    def set_settings(self):

        self.p.set_widgets_data(self.options)

        # Save reference to format list for get_settings()
        self.custom_format_list = config.sections["players"]["npformatlist"]

        # Update UI with saved player
        self.set_player(config.sections["players"]["npplayer"])
        self.update_now_playing_info()

        # Add formats
        self.NPFormat.remove_all()

        for item in self.default_format_list:
            self.NPFormat.append_text(str(item))

        if self.custom_format_list:
            for item in self.custom_format_list:
                self.NPFormat.append_text(str(item))

        if config.sections["players"]["npformat"] == "":
            # If there's no default format in the config: set the first of the list
            self.NPFormat.set_active(0)
        else:
            # If there's is a default format in the config: select the right item
            for (i, v) in enumerate(self.NPFormat.get_model()):
                if v[0] == config.sections["players"]["npformat"]:
                    self.NPFormat.set_active(i)

    def get_player(self):

        if self.NP_lastfm.get_active():
            player = "lastfm"
        elif self.NP_mpris.get_active():
            player = "mpris"
        elif self.NP_listenbrainz.get_active():
            player = "listenbrainz"
        elif self.NP_other.get_active():
            player = "other"

        return player

    def get_command(self):
        return self.NPCommand.get_text()

    def get_format(self):
        return self.NPFormat.get_active_text()

    def set_player(self, player):

        if player == "lastfm":
            self.NP_lastfm.set_active(True)
        elif player == 'listenbrainz':
            self.NP_listenbrainz.set_active(True)
        elif player == "other":
            self.NP_other.set_active(True)
        else:
            self.NP_mpris.set_active(True)

    def update_now_playing_info(self, widget=None):

        if self.NP_lastfm.get_active():
            self.player_replacers = ["$n", "$t", "$a", "$b"]
            self.player_input.set_text(_("Username;APIKEY:"))

        elif self.NP_mpris.get_active():
            self.player_replacers = ["$n", "$p", "$a", "$b", "$t", "$y", "$c", "$r", "$k", "$l", "$f"]
            self.player_input.set_text(_("Client name (e.g. amarok, audacious, exaile) or empty for auto:"))

        elif self.NP_listenbrainz.get_active():
            self.player_replacers = ["$n", "$t", "$a", "$b"]
            self.player_input.set_text(_("Username:"))

        elif self.NP_other.get_active():
            self.player_replacers = ["$n"]
            self.player_input.set_text(_("Command:"))

        legend = ""

        for item in self.player_replacers:
            legend += item + "\t"

            if item == "$t":
                legend += _("Title")
            elif item == "$n":
                legend += _("Now Playing (typically \"%(artist)s - %(title)s\")") % {
                    'artist': _("Artist"), 'title': _("Title")}
            elif item == "$l":
                legend += _("Length")
            elif item == "$r":
                legend += _("Bitrate")
            elif item == "$c":
                legend += _("Comment")
            elif item == "$a":
                legend += _("Artist")
            elif item == "$b":
                legend += _("Album")
            elif item == "$k":
                legend += _("Track Number")
            elif item == "$y":
                legend += _("Year")
            elif item == "$f":
                legend += _("Filename (URI)")
            elif item == "$p":
                legend += _("Program")

            legend += "\n"

        self.Legend.set_text(legend[:-1])

    def set_now_playing_example(self, title):
        self.Example.set_text(title)

    def get_settings(self):

        npformat = self.get_format()

        if (npformat and not npformat.isspace()
                and npformat not in self.custom_format_list
                and npformat not in self.default_format_list):
            self.custom_format_list.append(npformat)

        return {
            "players": {
                "npplayer": self.get_player(),
                "npothercommand": self.get_command(),
                "npformat": npformat,
                "npformatlist": self.custom_format_list
            }
        }


class PluginsFrame(UserInterface):

    """ Plugin preferences dialog """

    class PluginPreferencesDialog(Gtk.Dialog):
        """ Class used to build a custom dialog for the plugins """

        def __init__(self, parent, name):

            self.settings = parent.p

            # Build the window
            Gtk.Dialog.__init__(
                self,
                title=_("%s Settings") % name,
                modal=True,
                default_width=600,
                use_header_bar=Gtk.Settings.get_default().get_property("gtk-dialogs-use-header")
            )
            set_dialog_properties(self, self.settings.dialog)
            self.get_style_context().add_class("preferences")

            self.add_buttons(
                _("Cancel"), Gtk.ResponseType.CANCEL, _("OK"), Gtk.ResponseType.OK
            )

            self.set_default_response(Gtk.ResponseType.OK)
            self.connect("response", self.on_response)

            self.primary_container = Gtk.Box()
            self.primary_container.set_orientation(Gtk.Orientation.VERTICAL)
            self.primary_container.set_margin_top(14)
            self.primary_container.set_margin_bottom(14)
            self.primary_container.set_margin_start(18)
            self.primary_container.set_margin_end(18)
            self.primary_container.set_spacing(12)

            self.get_content_area().add(self.primary_container)

            self.tw = {}
            self.options = {}
            self.plugin = None

        def generate_label(self, text):

            label = Gtk.Label.new(text)
            label.set_use_markup(True)
            label.set_hexpand(True)
            label.set_xalign(0)

            if Gtk.get_major_version() == 4:
                label.set_wrap(True)
            else:
                label.set_line_wrap(True)

            return label

        def generate_widget_container(self, description, vertical=False):

            container = Gtk.Box()
            container.set_spacing(12)

            if vertical:
                container.set_orientation(Gtk.Orientation.VERTICAL)

            label = self.generate_label(description)
            container.add(label)
            self.primary_container.add(container)

            return (container, label)

        def generate_tree_view(self, name, description, value):

            container = Gtk.Box()
            container.set_spacing(6)

            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_hexpand(True)
            scrolled_window.set_vexpand(True)
            scrolled_window.set_min_content_height(200)
            scrolled_window.set_min_content_width(350)
            scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

            self.tw[name] = Gtk.TreeView()
            self.tw[name].set_model(Gtk.ListStore(str))

            if Gtk.get_major_version() == 4:
                scrolled_window.set_has_frame(True)
                scrolled_window.set_child(self.tw[name])
            else:
                scrolled_window.set_shadow_type(Gtk.ShadowType.IN)
                scrolled_window.add(self.tw[name])

            container.add(scrolled_window)

            cols = initialise_columns(
                None, self.tw[name],
                [description, description, 150, "edit", None]
            )

            try:
                self.settings.set_widget(self.tw[name], value)
            except Exception:
                pass

            self.add_button = Gtk.Button.new_with_label(_("Add"))
            self.remove_button = Gtk.Button.new_with_label(_("Remove"))

            box = Gtk.Box()
            box.set_spacing(6)

            box.add(self.add_button)
            box.add(self.remove_button)

            self.primary_container.add(container)
            self.primary_container.add(box)

            renderers = cols[description].get_cells()
            for render in renderers:
                render.connect('edited', self.cell_edited_callback, self.tw[name])

            self.add_button.connect("clicked", self.on_add, self.tw[name])
            self.remove_button.connect("clicked", self.on_remove, self.tw[name])

        def cell_edited_callback(self, widget, index, value, treeview):
            store = treeview.get_model()
            iterator = store.get_iter(index)
            store.set(iterator, 0, value)

        def add_options(self, plugin, options=None):

            if options is None:
                options = {}

            self.options = options
            self.plugin = plugin
            config_name = plugin.lower()

            for name, data in options.items():
                if config_name not in config.sections["plugins"]:
                    continue

                if name not in config.sections["plugins"][config_name]:
                    continue

                value = config.sections["plugins"][config_name][name]

                if data["type"] in ("integer", "int", "float"):
                    container, label = self.generate_widget_container(data["description"])

                    minimum = data.get("minimum") or 0
                    maximum = data.get("maximum") or 99999
                    stepsize = data.get("stepsize") or 1
                    decimals = 2

                    if data["type"] in ("integer", "int"):
                        decimals = 0

                    self.tw[name] = button = Gtk.SpinButton.new(
                        Gtk.Adjustment.new(0, minimum, maximum, stepsize, 10, 0),
                        1, decimals)
                    button.set_valign(Gtk.Align.CENTER)
                    label.set_mnemonic_widget(button)
                    self.settings.set_widget(button, config.sections["plugins"][config_name][name])

                    container.add(self.tw[name])

                elif data["type"] in ("bool",):
                    container = Gtk.Box()

                    self.tw[name] = Gtk.CheckButton.new_with_label(data["description"])
                    self.settings.set_widget(self.tw[name], config.sections["plugins"][config_name][name])

                    self.primary_container.add(container)
                    container.add(self.tw[name])

                elif data["type"] in ("radio",):
                    container, label = self.generate_widget_container(data["description"])

                    vbox = Gtk.Box()
                    vbox.set_spacing(6)
                    vbox.set_orientation(Gtk.Orientation.VERTICAL)
                    container.add(vbox)

                    last_radio = None
                    group_radios = []

                    for label in data["options"]:
                        if Gtk.get_major_version() == 4:
                            radio = Gtk.CheckButton.new_with_label(label)
                        else:
                            radio = Gtk.RadioButton.new_with_label_from_widget(last_radio, label)

                        if not last_radio:
                            self.tw[name] = radio

                        elif Gtk.get_major_version() == 4:
                            radio.set_group(last_radio)

                        last_radio = radio
                        group_radios.append(radio)
                        vbox.add(radio)

                    label.set_mnemonic_widget(self.tw[name])
                    self.tw[name].group_radios = group_radios
                    self.settings.set_widget(self.tw[name], config.sections["plugins"][config_name][name])

                elif data["type"] in ("dropdown",):
                    container, label = self.generate_widget_container(data["description"])

                    self.tw[name] = combobox = Gtk.ComboBoxText()
                    label.set_mnemonic_widget(combobox)
                    combobox.set_valign(Gtk.Align.CENTER)

                    for text_label in data["options"]:
                        combobox.append_text(text_label)

                    self.settings.set_widget(combobox, config.sections["plugins"][config_name][name])

                    container.add(self.tw[name])

                elif data["type"] in ("str", "string"):
                    container, label = self.generate_widget_container(data["description"])

                    self.tw[name] = entry = Gtk.Entry()
                    entry.set_hexpand(True)
                    entry.set_valign(Gtk.Align.CENTER)
                    label.set_mnemonic_widget(entry)
                    self.settings.set_widget(entry, config.sections["plugins"][config_name][name])

                    container.add(entry)

                elif data["type"] in ("textview"):
                    container, label = self.generate_widget_container(data["description"], vertical=True)

                    self.tw[name] = textview = Gtk.TextView()
                    textview.set_accepts_tab(False)
                    textview.set_pixels_above_lines(1)
                    textview.set_pixels_below_lines(1)
                    textview.set_left_margin(8)
                    textview.set_right_margin(8)
                    textview.set_top_margin(5)
                    textview.set_bottom_margin(5)

                    label.set_mnemonic_widget(textview)
                    self.settings.set_widget(textview, config.sections["plugins"][config_name][name])

                    frame_container = Gtk.Frame()

                    scrolled_window = Gtk.ScrolledWindow()
                    scrolled_window.set_hexpand(True)
                    scrolled_window.set_vexpand(True)
                    scrolled_window.set_min_content_height(200)
                    scrolled_window.set_min_content_width(600)

                    if Gtk.get_major_version() == 4:
                        frame_container.set_child(textview)
                        scrolled_window.set_child(frame_container)
                        container.append(scrolled_window)

                    else:
                        frame_container.add(textview)
                        scrolled_window.add(frame_container)
                        container.add(scrolled_window)

                elif data["type"] in ("list string",):
                    self.generate_tree_view(name, data["description"], value)

                elif data["type"] in ("file",):
                    container, label = self.generate_widget_container(data["description"])

                    button_widget = Gtk.Button()
                    button_widget.set_hexpand(True)

                    try:
                        chooser = data["chooser"]
                    except KeyError:
                        chooser = None

                    self.tw[name] = FileChooserButton(button_widget, self, chooser)
                    button_widget.set_valign(Gtk.Align.CENTER)
                    label.set_mnemonic_widget(button_widget)
                    self.settings.set_widget(self.tw[name], config.sections["plugins"][config_name][name])

                    container.add(button_widget)

                else:
                    log.add_debug("Unknown setting type '%s', data '%s'", (name, data))

            if Gtk.get_major_version() == 3:
                self.show_all()

        def on_add(self, widget, treeview):

            iterator = treeview.get_model().append([""])
            col = treeview.get_column(0)

            treeview.set_cursor(treeview.get_model().get_path(iterator), col, True)

        def on_remove(self, widget, treeview):
            selection = treeview.get_selection()
            iterator = selection.get_selected()[1]
            if iterator is not None:
                treeview.get_model().remove(iterator)

        def on_response(self, dialog, response_id):

            if response_id == Gtk.ResponseType.OK:
                for name in self.options:
                    value = self.settings.get_widget_data(self.tw[name])
                    if value is not None:
                        config.sections["plugins"][self.plugin.lower()][name] = value

                self.settings.frame.np.pluginhandler.plugin_settings(
                    self.plugin, self.settings.frame.np.pluginhandler.enabled_plugins[self.plugin])

            self.destroy()

    """ Initialize plugin list """

    def __init__(self, parent):

        super().__init__("ui/settings/plugin.ui")

        self.p = parent
        self.frame = self.p.frame

        self.options = {
            "plugins": {
                "enable": self.PluginsEnable
            }
        }

        self.plugins_model = Gtk.ListStore(bool, str, str)
        self.plugins = []
        self.pluginsiters = {}
        self.selected_plugin = None
        self.descr_textview = TextView(self.PluginDescription)

        self.column_numbers = list(range(self.plugins_model.get_n_columns()))
        cols = initialise_columns(
            None, self.PluginTreeView,
            ["enabled", _("Enabled"), 0, "toggle", None],
            ["plugin", _("Plugin"), 380, "text", None]
        )

        cols["enabled"].set_sort_column_id(0)
        cols["plugin"].set_sort_column_id(1)

        renderers = cols["enabled"].get_cells()
        column_pos = 0

        for render in renderers:
            render.connect('toggled', self.cell_toggle_callback, self.PluginTreeView, column_pos)

        self.PluginTreeView.set_model(self.plugins_model)

    def on_add_plugins(self, widget):

        try:
            if not os.path.isdir(config.plugin_dir):
                os.makedirs(config.plugin_dir)

            open_file_path(config.plugin_dir)

        except Exception as e:
            log.add("Failed to open folder containing user plugins: %s", e)

    def on_plugin_properties(self, widget):

        if self.selected_plugin is None:
            return

        plugin_info = self.frame.np.pluginhandler.get_plugin_info(self.selected_plugin)
        dialog = self.PluginPreferencesDialog(self, plugin_info.get("Name", self.selected_plugin))

        dialog.add_options(
            self.selected_plugin,
            self.frame.np.pluginhandler.get_plugin_settings(self.selected_plugin)
        )

        dialog_show(dialog)

    def on_select_plugin(self, selection):

        model, iterator = selection.get_selected()

        if iterator is None:
            self.selected_plugin = _("No Plugin Selected")
            info = {}
        else:
            self.selected_plugin = model.get_value(iterator, 2)
            info = self.frame.np.pluginhandler.get_plugin_info(self.selected_plugin)

        self.PluginName.set_markup("<b>%(name)s</b>" % {"name": info.get("Name", self.selected_plugin)})
        self.PluginVersion.set_markup("<b>%(version)s</b>" % {"version": info.get("Version", '-')})
        self.PluginAuthor.set_markup("<b>%(author)s</b>" % {"author": ", ".join(info.get("Authors", '-'))})

        self.descr_textview.clear()
        self.descr_textview.append_line("%(description)s" % {
            "description": info.get("Description", '').replace(r'\n', '\n')},
            showstamp=False, scroll=False)

        self.check_properties_button(self.selected_plugin)

    def cell_toggle_callback(self, widget, index, treeview, pos):

        iterator = self.plugins_model.get_iter(index)
        plugin = self.plugins_model.get_value(iterator, 2)
        value = self.plugins_model.get_value(iterator, 0)
        self.plugins_model.set(iterator, pos, not value)

        if not value:
            self.frame.np.pluginhandler.enable_plugin(plugin)
        else:
            self.frame.np.pluginhandler.disable_plugin(plugin)

        self.check_properties_button(plugin)

    def check_properties_button(self, plugin):
        settings = self.frame.np.pluginhandler.get_plugin_settings(plugin)

        if settings is not None:
            self.PluginProperties.set_sensitive(True)
        else:
            self.PluginProperties.set_sensitive(False)

    def set_settings(self):

        self.p.set_widgets_data(self.options)
        self.on_plugins_enable(None)
        self.pluginsiters = {}
        self.plugins_model.clear()
        plugins = sorted(self.frame.np.pluginhandler.list_installed_plugins())

        for plugin in plugins:
            try:
                info = self.frame.np.pluginhandler.get_plugin_info(plugin)
            except IOError:
                continue

            enabled = (plugin in config.sections["plugins"]["enabled"])
            self.pluginsiters[filter] = self.plugins_model.insert_with_valuesv(
                -1, self.column_numbers, [enabled, info.get('Name', plugin), plugin]
            )

        return {}

    def get_enabled_plugins(self):

        enabled_plugins = []

        for plugin in self.plugins_model:
            enabled = self.plugins_model.get_value(plugin.iter, 0)

            if enabled:
                plugin_name = self.plugins_model.get_value(plugin.iter, 2)
                enabled_plugins.append(plugin_name)

        return enabled_plugins

    def on_plugins_enable(self, *args):

        active = self.PluginsEnable.get_active()

        for widget in (self.PluginTreeView, self.PluginInfo):
            widget.set_sensitive(active)

        if active:
            # Enable all selected plugins
            for plugin in self.get_enabled_plugins():
                self.frame.np.pluginhandler.enable_plugin(plugin)

            return

        # Disable all plugins
        for plugin in self.frame.np.pluginhandler.enabled_plugins.copy():
            self.frame.np.pluginhandler.disable_plugin(plugin)

    def get_settings(self):

        return {
            "plugins": {
                "enable": self.PluginsEnable.get_active(),
                "enabled": self.get_enabled_plugins()
            }
        }


class Preferences(UserInterface):

    def __init__(self, frame):

        super().__init__("ui/dialogs/preferences.ui")

        self.frame = frame
        self.dialog = dialog = generic_dialog(
            parent=frame.MainWindow,
            content_box=self.main,
            quit_callback=self.on_delete,
            title=_("Preferences"),
            width=960,
            height=650
        )

        dialog.add_buttons(
            _("Cancel"), Gtk.ResponseType.CANCEL,
            _("Export"), Gtk.ResponseType.HELP,
            _("Apply"), Gtk.ResponseType.APPLY,
            _("OK"), Gtk.ResponseType.OK
        )

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect("response", self.on_response)

        style_context = dialog.get_style_context()
        style_context.add_class("preferences")
        style_context.add_class("preferences-border")

        self.pages = {}
        self.page_ids = [
            ("Network", _("Network"), "network-wireless-symbolic"),
            ("UserInterface", _("User Interface"), "view-grid-symbolic"),
            ("Shares", _("Shares"), "folder-symbolic"),
            ("Downloads", _("Downloads"), "document-save-symbolic"),
            ("Uploads", _("Uploads"), "emblem-shared-symbolic"),
            ("Searches", _("Searches"), "system-search-symbolic"),
            ("UserInfo", _("User Info"), "avatar-default-symbolic"),
            ("Chats", _("Chats"), "mail-send-symbolic"),
            ("NowPlaying", _("Now Playing"), "folder-music-symbolic"),
            ("Logging", _("Logging"), "emblem-documents-symbolic"),
            ("BannedUsers", _("Banned Users"), "action-unavailable-symbolic"),
            ("IgnoredUsers", _("Ignored Users"), "microphone-sensitivity-muted-symbolic"),
            ("Plugins", _("Plugins"), "list-add-symbolic"),
            ("UrlHandlers", _("URL Handlers"), "insert-link-symbolic")]

        for page_id, label, icon_name in self.page_ids:
            box = Gtk.Box()
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(42)
            box.set_spacing(12)
            box.show()

            icon = Gtk.Image()
            icon.set_property("icon-name", icon_name)
            icon.show()

            label = Gtk.Label.new(label)
            label.set_xalign(0)
            label.show()

            box.add(icon)
            box.add(label)

            self.preferences_list.insert(box, -1)

        self.update_visuals()

    def update_visuals(self, scope=None):

        if not scope:
            for page in self.pages.values():
                self.update_visuals(page)

            scope = self

        for widget in list(scope.__dict__.values()):
            update_widget_visuals(widget)

    def set_active_page(self, page):

        pos = 0
        for page_id, _label, _icon_name in self.page_ids:
            if page_id == page:
                break

            pos += 1

        row = self.preferences_list.get_row_at_index(pos)
        self.preferences_list.select_row(row)

    def set_widgets_data(self, options):

        for section, keys in options.items():
            if section not in config.sections:
                continue

            for key in keys:
                widget = options[section][key]

                if widget is None:
                    continue

                if config.sections[section][key] is None:
                    self.clear_widget(widget)
                else:
                    self.set_widget(widget, config.sections[section][key])

    def get_widget_data(self, widget):

        if isinstance(widget, Gtk.SpinButton):
            if widget.get_digits() > 0:
                return widget.get_value()

            return widget.get_value_as_int()

        elif isinstance(widget, Gtk.Entry):
            return widget.get_text()

        elif isinstance(widget, Gtk.TextView):
            buffer = widget.get_buffer()
            start, end = buffer.get_bounds()

            return widget.get_buffer().get_text(start, end, True)

        elif isinstance(widget, Gtk.CheckButton):
            try:
                # Radio button
                for radio in widget.group_radios:
                    if radio.get_active():
                        return widget.group_radios.index(radio)

                return 0

            except (AttributeError, TypeError):
                # Regular check button
                return widget.get_active()

        elif isinstance(widget, Gtk.ComboBoxText):
            return widget.get_active_text()

        elif isinstance(widget, Gtk.FontButton):
            widget.get_font()

        elif isinstance(widget, Gtk.TreeView) and widget.get_model().get_n_columns() == 1:
            wlist = []
            iterator = widget.get_model().get_iter_first()

            while iterator:
                word = widget.get_model().get_value(iterator, 0)

                if word is not None:
                    wlist.append(word)

                iterator = widget.get_model().iter_next(iterator)

            return wlist

        elif isinstance(widget, FileChooserButton):
            return widget.get_path()

    def clear_widget(self, widget):

        if isinstance(widget, Gtk.SpinButton):
            widget.set_value(0)

        elif isinstance(widget, Gtk.Entry):
            widget.set_text("")

        elif isinstance(widget, Gtk.TextView):
            widget.get_buffer().set_text("")

        elif isinstance(widget, Gtk.CheckButton):
            widget.set_active(0)

        elif isinstance(widget, Gtk.ComboBoxText):
            widget.get_child().set_text("")

        elif isinstance(widget, Gtk.FontButton):
            widget.set_font("")

    def set_widget(self, widget, value):

        if isinstance(widget, Gtk.SpinButton):
            try:
                widget.set_value(value)

            except TypeError:
                # Not a numerical value
                pass

        elif isinstance(widget, Gtk.Entry):
            if isinstance(value, (str, int)):
                widget.set_text(value)

        elif isinstance(widget, Gtk.TextView):
            if isinstance(value, (str, int)):
                widget.get_buffer().set_text(value)

        elif isinstance(widget, Gtk.CheckButton):
            try:
                # Radio button
                if isinstance(value, int) and value < len(widget.group_radios):
                    widget.group_radios[value].set_active(True)

            except (AttributeError, TypeError):
                # Regular check button
                widget.set_active(value)

        elif isinstance(widget, Gtk.ComboBoxText):
            if isinstance(value, str):
                if widget.get_has_entry():
                    widget.get_child().set_text(value)
                else:
                    widget.set_active_id(value)

            elif isinstance(value, int):
                widget.set_active(value)

            # If an invalid value was provided, select first item
            if not widget.get_has_entry() and widget.get_active() < 0:
                widget.set_active(0)

        elif isinstance(widget, Gtk.FontButton):
            widget.set_font(value)

        elif isinstance(widget, Gtk.TreeView) and isinstance(value, list) and widget.get_model().get_n_columns() == 1:
            model = widget.get_model()
            column_numbers = list(range(model.get_n_columns()))

            for item in value:
                model.insert_with_valuesv(-1, column_numbers, [str(item)])

        elif isinstance(widget, FileChooserButton):
            widget.set_path(value)

    def set_settings(self):

        for page in self.pages.values():
            page.set_settings()

    def get_settings(self):

        config = {
            "server": {},
            "transfers": {},
            "userinfo": {},
            "logging": {},
            "searches": {},
            "privatechat": {},
            "ui": {},
            "urls": {},
            "players": {},
            "words": {},
            "notifications": {},
            "plugins": {}
        }

        for page in self.pages.values():
            sub = page.get_settings()
            for key, data in sub.items():
                config[key].update(data)

        try:
            need_portmap = self.pages["Network"].needportmap

        except KeyError:
            need_portmap = False

        try:
            need_rescan = self.pages["Shares"].needrescan

        except KeyError:
            need_rescan = False

        if not need_rescan:
            try:
                need_rescan = self.pages["Downloads"].needrescan

            except KeyError:
                need_rescan = False

        try:
            need_colors = self.pages["UserInterface"].needcolors

        except KeyError:
            need_colors = False

        try:
            need_completion = self.pages["Completion"].needcompletion

        except KeyError:
            need_completion = False

        try:
            need_ip_block = self.pages["BannedUsers"].need_ip_block

        except KeyError:
            need_ip_block = False

        return need_portmap, need_rescan, need_colors, need_completion, need_ip_block, config

    def update_settings(self, settings_closed=False):

        need_portmap, need_rescan, need_colors, need_completion, need_ip_block, new_config = self.get_settings()

        for key, data in new_config.items():
            config.sections[key].update(data)

        if need_portmap:
            self.frame.np.add_upnp_portmapping()

        if need_colors:
            set_global_font(config.sections["ui"]["globalfont"])

            self.frame.chatrooms.update_visuals()
            self.frame.privatechat.update_visuals()
            self.frame.search.update_visuals()
            self.frame.downloads.update_visuals()
            self.frame.uploads.update_visuals()
            self.frame.userinfo.update_visuals()
            self.frame.userbrowse.update_visuals()
            self.frame.userlist.update_visuals()
            self.frame.interests.update_visuals()

            self.frame.update_visuals()
            self.update_visuals()

        if need_completion:
            self.frame.update_completions()

        if need_ip_block:
            self.frame.np.network_filter.close_blocked_ip_connections()

        # Dark mode
        dark_mode_state = config.sections["ui"]["dark_mode"]
        set_dark_mode(dark_mode_state)
        self.frame.dark_mode_action.set_state(GLib.Variant.new_boolean(dark_mode_state))

        # UPnP
        if not config.sections["server"]["upnp"] and self.frame.np.upnp_timer:
            self.frame.np.upnp_timer.cancel()

        # Chatrooms
        self.frame.chatrooms.toggle_chat_buttons()

        # Search
        self.frame.search.populate_search_history()

        # Transfers
        self.frame.np.transfers.update_limits()
        self.frame.np.transfers.update_download_filters()
        self.frame.np.transfers.check_upload_queue()

        # Tray icon
        if not config.sections["ui"]["trayicon"] and self.frame.tray_icon.is_visible():
            self.frame.tray_icon.hide()

        elif config.sections["ui"]["trayicon"] and not self.frame.tray_icon.is_visible():
            self.frame.tray_icon.load()

        # Main notebook
        self.frame.set_tab_positions()
        self.frame.set_main_tabs_visibility()

        for i in range(self.frame.MainNotebook.get_n_pages()):
            page = self.frame.MainNotebook.get_nth_page(i)
            tab_label = self.frame.MainNotebook.get_tab_label(page)
            tab_label.set_text_color(0)
            self.frame.set_tab_expand(page)

        # Other notebooks
        for w in (self.frame.chatrooms, self.frame.privatechat, self.frame.userinfo,
                  self.frame.userbrowse, self.frame.search):
            w.set_tab_closers()
            w.set_text_colors(None)

        # Update configuration
        config.write_configuration()

        if config.need_config():
            self.frame.connect_action.set_enabled(False)
            self.frame.on_fast_configure()

        elif not self.frame.np.server_conn:
            self.frame.connect_action.set_enabled(True)

        if not settings_closed:
            return

        if need_rescan:
            self.frame.np.shares.rescan_shares()

        if not config.sections["ui"]["trayicon"]:
            self.frame.MainWindow.present_with_time(Gdk.CURRENT_TIME)

    def back_up_config_response(self, selected, data):
        config.write_config_backup(selected)

    def back_up_config(self, *args):

        save_file(
            parent=self.frame.MainWindow,
            callback=self.back_up_config_response,
            initialdir=os.path.dirname(config.filename),
            initialfile="config backup %s.tar.bz2" % (time.strftime("%Y-%m-%d %H_%M_%S")),
            title=_("Pick a File Name for Config Backup")
        )

    def on_switch_page(self, listbox, row):

        page_id, _label, _icon_name = self.page_ids[row.get_index()]
        child = self.viewport.get_child()

        if child:
            if Gtk.get_major_version() == 4:
                self.viewport.set_child(None)
            else:
                self.viewport.remove(child)

        if page_id not in self.pages:
            self.pages[page_id] = page = getattr(sys.modules[__name__], page_id + "Frame")(self)
            page.set_settings()

            for obj in page.__dict__.values():
                if isinstance(obj, Gtk.CheckButton):
                    if Gtk.get_major_version() == 4:
                        obj.get_last_child().set_wrap(True)
                    else:
                        obj.get_children()[-1].set_line_wrap(True)

            page.Main.set_margin_start(18)
            page.Main.set_margin_end(18)
            page.Main.set_margin_top(14)
            page.Main.set_margin_bottom(18)

            self.update_visuals(page)

        if Gtk.get_major_version() == 4:
            self.viewport.set_child(self.pages[page_id].Main)
        else:
            self.viewport.add(self.pages[page_id].Main)

    def on_delete(self, *args):
        dialog_hide(self.dialog)
        return True

    def on_response(self, dialog, response_id):

        if response_id == Gtk.ResponseType.OK:
            self.update_settings(settings_closed=True)

        elif response_id == Gtk.ResponseType.APPLY:
            self.update_settings()
            return True

        elif response_id == Gtk.ResponseType.HELP:
            self.back_up_config()
            return True

        dialog_hide(self.dialog)

    def show(self, *args):
        dialog_show(self.dialog)