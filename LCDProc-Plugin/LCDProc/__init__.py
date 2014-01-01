"""
 Rhythmbox LCDProc plugin
 
Display information about what's playing on a display controlled by LCDProc.
 
Copyright 2013 Martin Tharby Jones martin@brasskipper.org.uk
 
"""
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# The Rhythmbox authors hereby grant permission for non-GPL compatible
# GStreamer plugins to be used and distributed together with GStreamer
# and Rhythmbox. This permission is above and beyond the permissions granted
# by the GPL license by which Rhythmbox is covered. If you modify this code
# you may extend this exception to your version of the code, but you are not
# obligated to do so. If you do not wish to do so, delete this exception
# statement from your version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
 
# ============================ Configuration Data ============================ #
 
LCDPROC_HOST = 'LiFi.local'
#LCDPROC_HOST = 'localhost'
# Where the LCD display server daemon is running, usually localhost.
 
keyUse = {
#    If your LCD has a keypad this dictionary specifies the keys of interest
#    and what to do when they are pressed.
#     
#    Use an empty dictionary if there is no keypad. Some possible actions are given in:
#     
#    http://live.gnome.org/RhythmboxPlugins/WritingGuide#Controlling_Playback
#     
#    For example to use the keys for the picoLCD in units such as the M300 
#    http://www.mini-box.com/Mini-Box-M300-LCD which has the following keys:
#    F1, F2, F3, F4, F5, Plus, Minus, Left, Right, Up, Down & Enter.
#    For IR remote control, keys specified here are only processed when the
#    plug-in screen is displayed, keys specified for the lirc plug-in are
#    processed whatever screen is displayed.
     
    # Keys for picoLCD
    "F1":"sp.do_previous()",
    "F2":"sp.playpause(True)",  # Parameter is not documented on WEB page above
    "F3":"sp.stop()",
    "F4":"sp.playpause(True)",
    # Using playpause() in place of play() which complains "Current playing source is NULL"
    "F5":"sp.do_next()",
    # Keys for picoLCD & IR remote control.
    "Plus":"sp.set_volume_relative(+0.05)",
    "Minus":"sp.set_volume_relative(-0.05)",
    "Up":"self.scroll(+1)",
    "Down":"self.scroll(-1)",
    # Keys for IR remote control.
    "Previous":"sp.do_previous()",
    "Next":"sp.do_next()",
    "Play":"sp.playpause(True)",
    "PlayPause":"sp.playpause(True)",
    "Pause":"sp.pause()",
    "Stop":"sp.stop()"
}
 
KEY_LABELS = "|<   ||  []   >   >|"
# If your display has keys these symbols indicate the functions they perform.
# The picoLCD has five keys below the display. 
SHOW_LABELS = False
# Should the labels be included in the whats playing information screen
 
ALBUM_LINE = 1
ARTIST_LINE = 2
TITLE_LINE = 3
TIME_LINE = 4
RATING_LINE = 5
LABEL_LINE = 6
# Specify where to place information on the display.
 
BOUNCE_ROLL_THRESHOLD = 5
# Number of characters larger than the screen width to switch scrolling mode.
DONT_SCROLL = False
# Do long lines scroll?
 
# ============================ Configuration End ============================ #
 
import sys
import rb
from gi.repository import GObject, Peas, RB
from gi._glib import GError
from lcdproc.server import Server
from socket import error as SocketError
 
NORMAL_ARTIST = 'artist'
NORMAL_TITLE  = 'title'
NORMAL_ALBUM  = 'album'
STREAM_ARTIST = 'rb:stream-song-artist'
STREAM_TITLE  = 'rb:stream-song-title'
STREAM_ALBUM  = 'rb:stream-song-album'

class LCDProcPlugin (GObject.Object, Peas.Activatable):
    object = GObject.property(type=GObject.Object)
 
    def __init__(self):
        super(LCDProcPlugin, self).__init__()
 
    def do_activate(self):
        print "Activating Plugin"
         
        self.entry = None
        self.duration = 0
        self.artist = " "
        self.title = " "
        self.album = " "
 
        # Initialise LCD
        try:
            self.lcd = Server(LCDPROC_HOST, debug=True)
        except SocketError:
            print "Failed to connect to LCDd"
            return False
        self.lcd.start_session()
        self.screen1 = self.lcd.add_screen("Rhythmbox")
        self.title1_widget = self.screen1.add_title_widget("Title", "Rhythmbox")
        self.label1_widget = self.screen1.add_string_widget("Label", KEY_LABELS, 1, 2)
        self.screen2 = self.lcd.add_screen("Rhythmbox-info")
        self.screen2.set_heartbeat("off")
        self.lcd.output("on")
        width = self.lcd.server_info["screen_width"]
        self.album_widget = self.screen2.add_scroller_widget("AlbumWidget", top = ALBUM_LINE, bottom = ALBUM_LINE, right = width, text = "Album")
        self.artist_widget = self.screen2.add_scroller_widget("ArtistWidget", top = ARTIST_LINE, bottom = ARTIST_LINE, right = width, text = "Artist")
        self.title_widget = self.screen2.add_scroller_widget("TitleWidget", top = TITLE_LINE, bottom = TITLE_LINE, right = width, text = "Title")
        self.progress_bar = self.screen2.add_hbar_widget("HBarWidget", x=1, y=TIME_LINE, length=0)
        self.time_widget = self.screen2.add_string_widget("TimeWidget", "", 1, TIME_LINE)
        self.displayed_lines = 4
        if SHOW_LABELS:
            self.label_widget = self.screen2.add_string_widget("LabelWidget", KEY_LABELS, 1, LABEL_LINE)
            self.displayed_lines += 1
 
        self.bounce_roll_length = width + BOUNCE_ROLL_THRESHOLD
        self.screen_width_pxl = width * self.lcd.server_info["cell_width"]
         
        for key in keyUse.keys():
            self.lcd.add_key(key)
 
        # Connect call-back functions to interesting events.
        sp = self.object.props.shell_player
        self.pc_id = sp.connect('playing-changed', self.playing_changed)
        self.psc_id = sp.connect('playing-song-changed', self.playing_song_changed)
        self.pspc_id = sp.connect('playing-song-property-changed', self.playing_song_property_changed)
        self.ec_id = sp.connect('elapsed-changed', self.elapsed_changed)
        # LCDd processes key input at 32Hz.
        self.pollcbtag = GObject.timeout_add(1000 / 32, self.poll_cb)
        
        print sp.get_playback_state()
        if sp.get_playing():
            print "Activating: playing"
            self.set_entry(sp.get_playing_entry())
            self.screen1.set_priority("background")
            self.screen2.set_priority("foreground")
        else:
            print "Activating: stopped"
            self.screen1.set_priority("info")
            self.screen2.set_priority("background")
        print "Plugin Activated"
 
    def do_deactivate(self):
        print "Deactivating Plugin"
        if not hasattr(self, 'pc_id'):
            return
        sp = self.object.props.shell_player
        sp.disconnect(self.pc_id)
        sp.disconnect(self.psc_id)
        sp.disconnect(self.pspc_id)
        sp.disconnect(self.ec_id)
        GObject.source_remove(self.pollcbtag)
 
        # Disconnect LCD
        del self.title1_widget
        del self.label1_widget
        del self.artist_widget
        del self.album_widget
        del self.title_widget
        del self.progress_bar
        del self.time_widget
        if SHOW_LABELS:
            del self.label_widget
        del self.screen1
        del self.screen2
        self.lcd.tn.close()
        del self.lcd
        print "Plugin Deactivated"
 
    def poll_cb(self):
        response = self.lcd.poll()
        if response:
            print "Poll Response: %s" % (response[:-1])
            bits = (response[:-1]).split(" ")
            if bits[0] == "key":
                action = keyUse[bits[1]]
                sp = self.object.props.shell_player    # Used by some actions.
                print action
                try:
                    exec action
                except GError as e:
                    if e.args[0] in ('Not currently playing', 'No previous song'):
                        print "%s safe to ignore." % e.args[0]
                    else:
                        print "%s unexpected." % e.args
                        raise
                except:
                    print "Blast! Unexpected error:", sys.exc_info()[0]
                    raise
        return True
 
    def playing_changed(self, player, playing):
        if playing:
            print "Playing"
            self.set_entry(player.get_playing_entry())
            self.screen1.set_priority("background")
            self.screen2.set_priority("foreground")
        else:
            print "Not playing"
            self.entry = None
            self.screen1.set_priority("info")
            self.screen2.set_priority("background")
 
    def playing_song_changed(self, player, entry):
        print "Playing song changed %s" % (entry)
        if player.get_playing():
            self.set_entry(entry)
 
    def playing_song_property_changed(self, player, uri, song_property, old, new):
        print "Playing song %s property (%s) changed (%s to %s)" % (uri, song_property, old, new)
        if player.get_playing():
            if song_property in (NORMAL_ALBUM, STREAM_ALBUM):
                self.album = new
            elif song_property in (NORMAL_ARTIST, STREAM_ARTIST):
                self.artist = new
            elif song_property in (NORMAL_TITLE):
                self.title = new
            elif song_property in (STREAM_TITLE):
                if new.count(" - ") >= 1:
                    # contains "Artist - Title"
                    fields = new.split(" - ",1)
                    self.artist = fields[0]
                    self.title = fields[1]
                else:
                    # only title
                    self.title = new
                    self.artist = ""
                self.album = uri
                self.duration = 0
            else:
                return
        else:
            return
        self.set_display()
 
    def elapsed_changed(self, player, time):
#         print "Elapsed changed %d" % time
        if (time >= 0 and self.duration > 0):
            progress = self.screen_width_pxl * time / self.duration
            self.progress_bar.set_length(progress)
            progress_str  = "%d:%02d" % (time/60, time%60)
            if (time < self.duration / 2):
                self.time_widget.set_x(self.lcd.server_info["screen_width"] - len(progress_str) + 1)
            else:
                self.time_widget.set_x(1)
            self.time_widget.set_text(progress_str)
        else:
            self.progress_bar.set_length(0)
            self.time_widget.set_text("")

    def set_entry(self, entry):
        if rb.entry_equal(entry, self.entry):
            return
        self.entry = entry
        if entry is None:
            return
        self.album = entry.get_string(RB.RhythmDBPropType.ALBUM)
        self.artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
        self.title = entry.get_string(RB.RhythmDBPropType.TITLE)
        self.duration = entry.get_ulong(RB.RhythmDBPropType.DURATION)
#         sp = self.object.props.shell_player
#         self.duration = sp.get_playing_song_duration()
        self.rating = entry.get_double(RB.RhythmDBPropType.RATING)
        print "Song rating %g" % self.rating
        db = self.object.get_property("db")
        if entry.get_entry_type().props.category == RB.RhythmDBEntryCategory.STREAM:
            if not self.album:
                self.album = db.entry_request_extra_metadata(entry, STREAM_ALBUM)
            if not self.artist:
                self.artist = db.entry_request_extra_metadata(entry, STREAM_ARTIST)
            if not self.title:
                self.title = db.entry_request_extra_metadata(entry, STREAM_TITLE)
        self.set_display()
 
    def set_display(self):
        album_text = self.album
        if DONT_SCROLL:
            album_text = album_text[0:self.lcd.server_info["screen_width"]]
        elif len(album_text) < self.bounce_roll_length:
            self.album_widget.set_direction("h")    # Bounce text to show characters that don't fit
        else:
            self.album_widget.set_direction("m")    # Roll text to show characters that don't fit
            album_text += " * "
        self.album_widget.set_text(album_text)
 
        artist_text = self.artist
        if DONT_SCROLL:
            artist_text = artist_text[0:self.lcd.server_info["screen_width"]]
        elif len(artist_text) < self.bounce_roll_length:
            self.artist_widget.set_direction("h")
        else:
            self.artist_widget.set_direction("m")
            artist_text += " * "
        self.artist_widget.set_text(artist_text)
 
        title_text = self.title
        if DONT_SCROLL:
            title_text = title_text[0:self.lcd.server_info["screen_width"]]
        elif len(title_text) < self.bounce_roll_length:
            self.title_widget.set_direction("h")
        else:
            self.title_widget.set_direction("m")
            title_text += " * "
        self.title_widget.set_text(title_text)

    def new_line(self, current, step):
        print "newline %d,%d" % (current, step)
        current += step
        if current > self.displayed_lines:
            return 1
        if current == 0:
            current = self.displayed_lines
        return current
 
    def scroll(self, step):
        self.album_widget.set_top(self.new_line(self.album_widget.top, step))
        self.album_widget.set_bottom(self.new_line(self.album_widget.bottom, step))
        self.artist_widget.set_top(self.new_line(self.artist_widget.top, step))
        self.artist_widget.set_bottom(self.new_line(self.artist_widget.bottom, step))
        self.title_widget.set_top(self.new_line(self.title_widget.top, step))
        self.title_widget.set_bottom(self.new_line(self.title_widget.bottom, step))
        self.progress_bar.set_y(self.new_line(self.progress_bar.y, step))
        self.time_widget.set_y(self.new_line(self.time_widget.y, step))
        if SHOW_LABELS:
            self.label_widget.set_y(self.new_line(self.label_widget.y, step))
