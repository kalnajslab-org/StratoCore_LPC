#!/usr/bin/env python3
"""
plot_lpc_bins.py

Live-plots LPC or PHA bin data from a serial console or a saved log file.
One pair of plots is shown at a time:

  (default) the StratoLPC high/low gain size bins
  --pha     the PHA board's raw high/low gain pulse-height spectra

Data for the other plot is recognized but ignored. Line formats, auto-detected
line by line:

1. StratoLPC's 16 size bins, printed once per sample frame by
   StratoLPC::fillBins() (see printBinsCSV() in StratoLPC.cpp), read from the
   LPC main board's DEBUG_SERIAL console (default plot):
       HGBINS,<record>,<bin0>,<bin1>,...,<bin15>
       LGBINS,<record>,<bin0>,<bin1>,...,<bin15>

   The same 16 size bins may also show up in the older, plain-text debug
   format (no record number) some builds of fillBins() still print instead:
       High Gain Bins: <bin0>, <bin1>, ..., <bin15>,
       Low Gain Bins: <bin0>, <bin1>, ..., <bin15>,

   The LPC console's housekeeping lines (Pulse Count, Flow, Pump1 T, Pump2 T,
   Inlet T) are shown in a status bar on the default plot.

2. The PHA's raw 256-element downsampled pulse-height spectra (--pha), printed
   to its own USB DEBUG_SERIAL console (PlatformIO PHA_V5_1.ino, V5.1a+) once
   per CYCLE_TIME when enabled with the '#hgprint,1' / '#lgprint,1'
   interactive commands:
       HG_Small_Array: <b0>,<b1>,...,<b255>,
       LG_Small_Array: <b0>,<b1>,...,<b255>,

3. The same raw 256-element spectra (--pha), but read from the PHA's
   OUTPUT_SERIAL (Serial1, 500000 baud) line to the main board instead of its
   USB console (e.g. tapping Serial1 TX with a USB-TTL adapter for bench
   testing):
       <timestamp>,<laserI>,<threshold>,<pulse_count>,<256 HG values>,<256 LG values>,E

All other lines are ignored for plotting but echoed to stdout so you can
still see log messages / other console output.

Usage:
    # LPC main board console (16 size bins)
    python3 plot_lpc_bins.py --port /dev/tty.usbmodemXXXX --baud 115200

    # PHA board's own USB console (256-element raw spectra); once connected,
    # send '#hgprint,1' and '#lgprint,1' to the PHA to turn printing on
    python3 plot_lpc_bins.py --pha --port /dev/tty.usbmodemYYYY --baud 115200

    # PHA board's Serial1 line to the main board instead (256-element raw spectra)
    python3 plot_lpc_bins.py --pha --port /dev/tty.usbserialXXXX --baud 500000

    # replay a saved log instead of a live port (add --pha for PHA data)
    python3 plot_lpc_bins.py --file console_log.txt

    # read from stdin (simulates a device; --speed and Pause/Run still apply)
    cat console_log.txt | python3 plot_lpc_bins.py --file -

    # replay a timestamped log at 10x real time (1 = real time, 0.5 = half speed)
    python3 plot_lpc_bins.py --file LPC_DBG_log.txt --speed 10

A live --port is also recorded to LPC_capture_<timestamp>.txt (PHA_capture_<timestamp>.txt with
--pha) in the current directory; the path is shown at the bottom of the window
with a Copy button.

Requires: pyserial, matplotlib
    pip install pyserial matplotlib
"""

import argparse
import datetime
import importlib.metadata
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox

try:
    import serial
except ImportError:
    serial = None

N_SIZE_BINS = 16  # StratoLPC's downsampled size bins (HGBins/LGBins)

# --speed replay skips the waiting time while the log says the instrument is in
# one of these states: no bins are produced then, and SB is entered silently
# from FL_IDLE so it looks like a long FL_IDLE. Logs with no 'Entering <state>'
# lines at all (e.g. PHA data) never match, so they are paced throughout.
ENTERING_RE = re.compile(r"NOM: Entering (\w+)")
IDLE_STATES = {"FL", "FL_IDLE"}

# Size (nm) of each StratoLPC size bin, as in the LPC data file's column header
# (HG bins 0-15, then LG bins 0-15). Bin 15 of the LG set is always empty in
# firmware (its raw-array range is 255..255), hence the repeated 24000.
HG_BIN_SIZES = [275, 300, 325, 350, 375, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000]
LG_BIN_SIZES = [1200, 1400, 1600, 1800, 2000, 2500, 3000, 3500, 4000, 6000, 8000, 10000, 13000, 16000, 24000, 24000]

# housekeeping lines shown in the status bar: console label -> status key
STATUS_FIELDS = {
    "Pulse Count": "pulses",
    "Flow": "flow",
    "Pump1 T": "pump1",
    "Pump2 T": "pump2",
    "Inlet T": "inlet",
}


def parse_size_bins_line(line, tag):
    """Return (record, [bin counts]) for a StratoLPC '<tag>,record,b0,b1,...' line, else None."""
    line = line.strip()
    if not line.startswith(tag + ","):
        return None
    fields = line.split(",")
    try:
        record = int(fields[1])
        bins = [int(x) for x in fields[2:]]
    except (ValueError, IndexError):
        return None
    return record, bins


def parse_labeled_bins_line(line, label):
    """
    Return [bin counts] for a plain labeled debug line of the form:
        <label>: b0, b1, b2, ...,
    e.g. StratoLPC.cpp's legacy fillBins() debug prints:
        High Gain Bins: 0, 5481, 3037, ...,
        Low Gain Bins: 72, 30, 21, ...,
    or None if it doesn't match. There's no record/frame number on this line,
    unlike the tagged 'HGBINS,<record>,...' CSV format.
    """
    line = line.strip()
    prefix = label + ":"
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    if not rest:
        return None
    parts = [p.strip() for p in rest.split(",") if p.strip() != ""]
    try:
        values = [int(x) for x in parts]
    except ValueError:
        return None
    return values or None


def parse_pha_line(line):
    """
    Return a dict for a raw PHA output line:
        timestamp,laserI,threshold,pulse_count,<HG values...>,<LG values...>,E
    or None if the line doesn't match. The HG/LG arrays are assumed equal
    length (256 each on current firmware, 255 each on the older, buggy PHA_V5_1
    unpack loop) and are split evenly, so either firmware version parses fine.
    """
    line = line.strip()
    if not line.endswith(",E") or line.count(",") < 5:
        return None
    fields = line.split(",")
    if fields[-1] != "E":
        return None
    try:
        timestamp = int(fields[0])
        laser_i = float(fields[1])
        threshold = int(fields[2])
        pulse_count = int(fields[3])
        values = [int(x) for x in fields[4:-1]]
    except ValueError:
        return None
    if len(values) < 2 or len(values) % 2 != 0:
        return None
    half = len(values) // 2
    return {
        "timestamp": timestamp,
        "laser_i": laser_i,
        "threshold": threshold,
        "pulse_count": pulse_count,
        "hg": values[:half],
        "lg": values[half:],
    }


def parse_pha_debug_array_line(line, label):
    """
    Return [bin counts] for a PHA USB-console debug line of the form:
        <label>: b0,b1,...,bN,
    (as printed by PHA_V5_1.ino when Print_HG_Small_Array/Print_LG_Small_Array
    is enabled via '#hgprint,1' / '#lgprint,1'), or None if it doesn't match.
    """
    line = line.strip()
    prefix = label + ":"
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    if not rest:
        return None
    # the firmware's sprintf("%d,", ...) loop leaves a trailing comma, so drop
    # the empty field it produces
    parts = [p for p in rest.split(",") if p != ""]
    try:
        values = [int(x) for x in parts]
    except ValueError:
        return None
    return values or None


def parse_log_timestamp(line):
    """Return seconds since midnight for a '[HH:MM:SS.mmm] ...' log line, else None."""
    if len(line) < 14 or line[0] != "[" or line[13] != "]":
        return None
    try:
        return int(line[1:3]) * 3600 + int(line[4:6]) * 60 + float(line[7:13])
    except ValueError:
        return None


def make_line_source(args):
    """Yield successive decoded lines from either a live serial port or a log file."""
    if args.file:
        prev_ts = None  # previous line's log timestamp, in seconds
        t_prev_wall = None
        state = None  # instrument state from the log's 'Entering <state>' lines
        # '-' means read from stdin, e.g.  cat log.txt | plot_lpc_bins.py --file -
        f = sys.stdin if args.file == "-" else open(args.file, "r", errors="replace")
        with f:
            for line in f:
                # args.speed can be changed at any time from the GUI speed box;
                # None/0 means unpaced
                if args.speed:
                    ts = parse_log_timestamp(line)
                    if ts is not None:
                        if prev_ts is not None and state not in IDLE_STATES:
                            # the gap belongs to the state we were in on the previous
                            # line; skip it while idle/standby since nothing is plotted
                            dt = (ts - prev_ts) % 86400  # tolerate midnight wrap
                            # sleep in short slices so a speed change takes effect promptly
                            while args.speed:
                                wait = dt / args.speed - (time.monotonic() - t_prev_wall)
                                if wait <= 0:
                                    break
                                time.sleep(min(wait, 0.1))
                        prev_ts = ts
                        t_prev_wall = time.monotonic()
                m = ENTERING_RE.search(line)
                if m:
                    state = m.group(1)
                yield line
    else:
        if serial is None:
            sys.exit("pyserial is required for live serial reads: pip install pyserial")
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            while True:
                raw = ser.readline()
                if not raw:
                    continue
                yield raw.decode(errors="replace")


def window_title():
    """'plot-lpc-bins v<version>' from the installed package metadata (no version when run from a bare checkout)."""
    try:
        return f"plot-lpc-bins v{importlib.metadata.version('plot-lpc-bins')}"
    except importlib.metadata.PackageNotFoundError:
        return "plot-lpc-bins"


class Capture:
    """
    Records everything arriving on a live port to <PREFIX>_capture_<YYYY-MM-DDTHH-MM-SS>.txt in
    the current directory (PREFIX is LPC or PHA, mirroring the LPC_DBG_<timestamp>.txt
    debug logs). Each line gets the same '[HH:MM:SS.mmm] ' prefix those logs use, so a
    capture can be replayed later with --file (and --speed).
    """

    def __init__(self, prefix, args):
        now = datetime.datetime.now()
        self.path = os.path.abspath(f"{prefix}_capture_{now.strftime('%Y-%m-%dT%H-%M-%S')}.txt")
        self._lock = threading.Lock()
        self._f = open(self.path, "w", buffering=1)  # line buffered: always current on disk
        self._f.write(f"{prefix} Capture: {now.strftime('%Y-%m-%d at %H:%M:%S')} ({args.port}, {args.baud} baud)\n\n")

    def write(self, line):
        stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with self._lock:
            if self._f is not None:
                self._f.write(f"[{stamp}] {line.rstrip(chr(13) + chr(10))}\n")

    def close(self):
        with self._lock:
            if self._f is not None:
                self._f.close()
                self._f = None


def add_text_box(fig, rect, text):
    """
    Add a bordered, read-only text box to the bottom strip. If the text doesn't fit
    the box (at the window's initial size) its start is trimmed to "..." so the end
    -- the file name -- stays visible.
    """
    ax = fig.add_axes(rect)
    ax.set_xticks([])
    ax.set_yticks([])
    # clip_on so the text can never spill out of the box if the window is shrunk
    label = ax.text(0.01, 0.5, text, va="center", ha="left", fontsize=8, family="monospace", clip_on=True)
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:  # backends without get_renderer()
        renderer = fig._get_renderer()
    room = ax.get_window_extent(renderer).width * 0.98 - 8  # pixels, minus the left inset
    shown = text
    while label.get_window_extent(renderer).width > room and len(shown) > 8:
        shown = shown[1:]
        label.set_text("..." + shown)
    return ax


def copy_to_clipboard(text):
    """Put text on the system clipboard using the platform's tool; return True on success."""
    if sys.platform == "darwin":
        candidates = [["pbcopy"]]
    elif sys.platform.startswith("win"):
        candidates = [["clip"]]
    else:
        candidates = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in candidates:
        try:
            subprocess.run(cmd, input=text.encode(), check=True, timeout=5)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


class BinPlotter:
    """Owns the figure and knows how to redraw whichever bin arrays have new data."""

    def __init__(self, mode="lpc"):
        """mode 'lpc' plots StratoLPC's 16 HG/LG size bins; 'pha' plots the PHA's raw spectra."""
        self.mode = mode
        self.fig, axes = plt.subplots(1, 2, figsize=(13, 8))
        self.fig.canvas.manager.set_window_title(window_title())
        self.dirty = False

        # only the selected mode's attributes are populated; the others stay None
        self.ax_hg = self.ax_lg = self.ax_pha_hg = self.ax_pha_lg = None
        self.hg_bars = self.lg_bars = None
        self.hg_peak_annotation = self.lg_peak_annotation = None
        self.pha_hg_line = self.pha_lg_line = None
        self.pha_hg_peak_annotation = self.pha_lg_peak_annotation = None
        self.status_text = None

        if mode == "lpc":
            self.ax_hg, self.ax_lg = axes
            self.hg_bins = [0] * N_SIZE_BINS
            self.lg_bins = [0] * N_SIZE_BINS
            self.hg_record = None
            self.lg_record = None
            # fallback frame counters, used when a line format doesn't carry its own
            # record number (e.g. the legacy 'High Gain Bins: ...' text format)
            self.hg_frame_count = 0
            self.lg_frame_count = 0
            self.hg_bars = self.ax_hg.bar(range(N_SIZE_BINS), self.hg_bins, color="tab:blue")
            self.lg_bars = self.ax_lg.bar(range(N_SIZE_BINS), self.lg_bins, color="tab:orange")
            for ax, title, sizes in (
                (self.ax_hg, "StratoLPC High Gain Size Bins", HG_BIN_SIZES),
                (self.ax_lg, "StratoLPC Low Gain Size Bins", LG_BIN_SIZES),
            ):
                ax.set_title(title)
                ax.set_xlabel("Size bin (nm)")
                ax.set_xticks(range(N_SIZE_BINS))
                ax.set_xticklabels([str(v) for v in sizes], rotation=90, fontsize=7)
                ax.set_ylabel("Counts")
                ax.set_ylim(0.5, 10)  # placeholder range so switching to log scale below has something positive to work with
                ax.set_yscale("log")
        else:
            # PHA raw spectra: lines are created lazily once we know how many elements they have
            self.ax_pha_hg, self.ax_pha_lg = axes
            for ax, title in ((self.ax_pha_hg, "PHA Raw High Gain Spectrum"), (self.ax_pha_lg, "PHA Raw Low Gain Spectrum")):
                ax.set_title(title + " (no data yet)")
                ax.set_xlabel("Raw ADC bin (reversed)")
                ax.set_ylabel("Counts")

        # bottom strip: a row of buttons + file path (y 0.01-0.055), with the
        # status bar in a row above it in lpc mode; pha mode also leaves room at
        # the top for its two-line titles
        self.fig.tight_layout(rect=(0, 0.115 if mode == "lpc" else 0.07, 1, 1 if mode == "lpc" else 0.94))
        if mode == "lpc":
            # status bar: latest value of each housekeeping line (STATUS_FIELDS);
            # these lines only exist on the LPC console, so it's not shown for pha
            self.status = {key: "--" for key in STATUS_FIELDS.values()}
            self.status_text = self.fig.text(
                0.99, 0.085, "", ha="right", va="center", fontsize=9, family="monospace"
            )
            self._render_status()

    def reset(self):
        """Return the figure to its start-up (no data yet) state, e.g. for a playback restart."""
        if self.mode == "lpc":
            for bars, ax, title in (
                (self.hg_bars, self.ax_hg, "StratoLPC High Gain Size Bins"),
                (self.lg_bars, self.ax_lg, "StratoLPC Low Gain Size Bins"),
            ):
                for bar in bars:
                    bar.set_height(0)
                ax.set_ylim(0.5, 10)
                ax.set_title(title)
            self.hg_bins = [0] * N_SIZE_BINS
            self.lg_bins = [0] * N_SIZE_BINS
            self.hg_record = self.lg_record = None
            self.hg_frame_count = self.lg_frame_count = 0
            for attr in ("hg_peak_annotation", "lg_peak_annotation"):
                old = getattr(self, attr)
                if old is not None:
                    try:
                        old.remove()
                    except (ValueError, NotImplementedError):
                        pass
                    setattr(self, attr, None)
            self.status = {key: "--" for key in STATUS_FIELDS.values()}
            self._render_status()
        else:
            # ax.clear() also discards the PHA lines and annotations
            for ax, title in ((self.ax_pha_hg, "PHA Raw High Gain Spectrum"), (self.ax_pha_lg, "PHA Raw Low Gain Spectrum")):
                ax.clear()
                ax.set_title(title + " (no data yet)")
                ax.set_xlabel("Raw ADC bin (reversed)")
                ax.set_ylabel("Counts")
            self.pha_hg_line = self.pha_lg_line = None
            self.pha_hg_peak_annotation = self.pha_lg_peak_annotation = None
        self.dirty = True

    def update_size_bins(self, tag, record, bins):
        if tag == "HGBINS":
            self.hg_frame_count += 1
            record = record if record is not None else self.hg_frame_count
            self.hg_record, self.hg_bins = record, bins
            bars, ax, label, peak_attr = self.hg_bars, self.ax_hg, "StratoLPC High Gain Size Bins", "hg_peak_annotation"
            sizes = HG_BIN_SIZES
        else:
            self.lg_frame_count += 1
            record = record if record is not None else self.lg_frame_count
            self.lg_record, self.lg_bins = record, bins
            bars, ax, label, peak_attr = self.lg_bars, self.ax_lg, "StratoLPC Low Gain Size Bins", "lg_peak_annotation"
            sizes = LG_BIN_SIZES

        n = len(bins)
        original_indices = list(range(n))
        xs = list(range(n))

        for bar, value in zip(bars, bins):
            bar.set_height(value)
        # log scale can't show 0, so give it a small positive floor; zero-count
        # bins just render as a sliver at the bottom, which is fine
        # top margin sized so the peak label takes ~15% of the axes height: on a log
        # axis that means solving log(top) - log(peak) = 0.15 * (log(top) - log(0.5))
        log_peak = math.log10(max(bins + [1]))
        ax.set_ylim(0.5, 10 ** ((log_peak + 0.15 * math.log10(0.5) * -1) / 0.85))
        ax.set_title(f"{label}, total counts: {sum(bins)} (frame {record})")

        self._update_peak_label(ax, xs, bins, original_indices, peak_attr, sizes)
        self._flush()

    def update_pha(self, sample):
        """Update both PHA channels at once from a raw-CSV sample dict (parse_pha_line())."""
        extra = (
            f"t={sample['timestamp']}, pulses={sample['pulse_count']}, "
            f"thresh={sample['threshold']}, laserI={sample['laser_i']:.3f}"
        )
        self.update_pha_channel("hg", sample["hg"], extra)
        self.update_pha_channel("lg", sample["lg"], extra)

    def _update_peak_label(self, ax, xs, ys, original_indices, attr_name, bin_sizes=None):
        """(Re)draw a 'peak: bin N (count)' annotation at the tallest point, removing any prior one."""
        old = getattr(self, attr_name, None)
        if old is not None:
            try:
                old.remove()
            except (ValueError, NotImplementedError):
                pass  # already gone, e.g. the axis was cleared out from under it
            setattr(self, attr_name, None)

        if not ys:
            return

        peak_pos = max(range(len(ys)), key=lambda i: ys[i])
        peak_x, peak_y, peak_bin = xs[peak_pos], ys[peak_pos], original_indices[peak_pos]
        size_note = ""
        if bin_sizes is not None and peak_bin < len(bin_sizes):
            size_note = f" ({bin_sizes[peak_bin]} nm)"
        # Label sits just above the peak with an arrow pointing down to it; the
        # callers leave headroom in the y-limits so it stays inside the axes.
        # Near either edge, anchor the text to that side so it doesn't spill out.
        frac = peak_x / max(len(ys) - 1, 1)
        ha = "left" if frac < 0.1 else "right" if frac > 0.9 else "center"
        annotation = ax.annotate(
            f"peak: bin {peak_bin}{size_note}\n({peak_y} counts)",
            xy=(peak_x, peak_y),
            xytext=(0, 8),
            textcoords="offset points",
            ha=ha,
            va="bottom",
            fontsize=8,
            arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
        )
        setattr(self, attr_name, annotation)

    def update_pha_channel(self, which, values, extra_title=""):
        """Update a single PHA channel ('hg' or 'lg') from a plain list of bin counts."""
        if which == "hg":
            ax_attr, line_attr, peak_attr, color, label = (
                "ax_pha_hg", "pha_hg_line", "pha_hg_peak_annotation", "tab:blue", "PHA Raw High Gain Spectrum",
            )
        else:
            ax_attr, line_attr, peak_attr, color, label = (
                "ax_pha_lg", "pha_lg_line", "pha_lg_peak_annotation", "tab:orange", "PHA Raw Low Gain Spectrum",
            )

        # Reverse bin order for display, same convention as the size bins above:
        # raw index 0 (the biggest pulse dip) plots rightmost, raw index N-1
        # (closest to the trigger threshold) plots leftmost.
        n = len(values)
        reversed_values = values[::-1]
        original_indices = list(range(n - 1, -1, -1))
        xs = list(range(n))

        ax = getattr(self, ax_attr)
        line = getattr(self, line_attr)
        if line is None or len(line.get_xdata()) != n:
            ax.clear()
            (line,) = ax.plot(xs, reversed_values, color=color, drawstyle="steps-mid")
            ax.set_xlabel("Raw ADC bin (reversed)")
            ax.set_ylabel("Counts")
            setattr(self, line_attr, line)
            setattr(self, peak_attr, None)  # ax.clear() already destroyed any old annotation
        else:
            line.set_ydata(reversed_values)
        ax.set_ylim(0, max(values + [1]) * 1.18)  # headroom for the peak label
        title = f"{label}, total counts: {sum(values)}"
        if extra_title:
            title += f"\n{extra_title}"  # second line: too long to fit beside the other panel
        ax.set_title(title, fontsize=10)

        self._update_peak_label(ax, xs, reversed_values, original_indices, peak_attr)
        self._flush()

    def update_status(self, key, value):
        self.status[key] = value
        self._render_status()
        self.dirty = True

    def _render_status(self):
        st = self.status
        self.status_text.set_text(
            f"Pulses: {st['pulses']}   Flow: {st['flow']}   "
            f"Pump1 T: {st['pump1']}   Pump2 T: {st['pump2']}   Inlet T: {st['inlet']}"
        )

    def _flush(self):
        # just mark dirty; the GUI timer redraws once per tick regardless of
        # how many lines arrived since the last one
        self.dirty = True

    def redraw_if_dirty(self):
        if self.dirty:
            self.dirty = False
            self.fig.canvas.draw_idle()


def dispatch_line(plotter, line):
    """
    Parse one console line and update the plot; echo it if it isn't plottable.
    Data that belongs to the other plot mode (LPC bins/housekeeping on a --pha
    plot, PHA spectra on an LPC plot) is recognized but silently dropped, since
    the PHA lines in particular are huge.
    """
    raw = line
    # logger-saved files prefix each line with '[HH:MM:SS.mmm] '; drop it
    if line.startswith("["):
        end = line.find("] ")
        if 0 < end <= 16:
            line = line[end + 2:]
    lpc = plotter.mode == "lpc"
    label, sep, value = line.partition(":")
    if sep and label in STATUS_FIELDS and value.strip():
        if lpc:
            plotter.update_status(STATUS_FIELDS[label], value.strip())
        return
    # cheap prefix checks first so ordinary log lines skip all the parsers
    if line.startswith("HGBINS,"):
        result = parse_size_bins_line(line, "HGBINS")
        if result is not None:
            return plotter.update_size_bins("HGBINS", *result) if lpc else None
    elif line.startswith("LGBINS,"):
        result = parse_size_bins_line(line, "LGBINS")
        if result is not None:
            return plotter.update_size_bins("LGBINS", *result) if lpc else None
    elif line.startswith("High Gain Bins:"):
        result = parse_labeled_bins_line(line, "High Gain Bins")
        if result is not None:
            return plotter.update_size_bins("HGBINS", None, result) if lpc else None
    elif line.startswith("Low Gain Bins:"):
        result = parse_labeled_bins_line(line, "Low Gain Bins")
        if result is not None:
            return plotter.update_size_bins("LGBINS", None, result) if lpc else None
    elif line.startswith("HG_Small_Array:"):
        result = parse_pha_debug_array_line(line, "HG_Small_Array")
        if result is not None:
            return None if lpc else plotter.update_pha_channel("hg", result)
    elif line.startswith("LG_Small_Array:"):
        result = parse_pha_debug_array_line(line, "LG_Small_Array")
        if result is not None:
            return None if lpc else plotter.update_pha_channel("lg", result)
    else:
        result = parse_pha_line(line)
        if result is not None:
            return None if lpc else plotter.update_pha(result)
    # pass through anything else so you can still see instrument logs
    print(raw.rstrip())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="Serial port (e.g. /dev/tty.usbmodem1234 or COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate (default: 115200; use 500000 when reading the PHA's own Serial1 output with --pha)")
    parser.add_argument("--file", help="Replay lines from a saved log file instead of a live serial port; use - to read from stdin")
    parser.add_argument("--speed", type=float, default=10.0, help="With --file, replay at this multiple of the log's real-time pace using its [HH:MM:SS.mmm] timestamps, skipping idle/standby periods (1 = real time, 10 = 10x faster, 0.5 = half speed). Use 0 for as fast as possible. Default: 10. Can also be changed during playback with the Speed box")
    parser.add_argument("--pha", action="store_true", help="Plot the PHA board's raw high/low gain spectra instead of the default StratoLPC size bins")
    args = parser.parse_args()

    if not args.file and not args.port:
        parser.error("either --port or --file is required")
    # --speed only means something for file playback; silently ignored otherwise
    if args.file and args.speed < 0:
        parser.error("--speed must not be negative (0 = unpaced)")

    plotter = BinPlotter("pha" if args.pha else "lpc")

    # Live ports are recorded to a file in the current directory; replays aren't
    capture = None
    capture_error = None
    if not args.file:
        try:
            capture = Capture("PHA" if args.pha else "LPC", args)
        except OSError as e:
            capture_error = str(e)
            print(f"warning: not capturing data: {e}", file=sys.stderr)

    # Read the port/file on a background thread so the GUI never blocks on I/O.
    # The bounded queue throttles file replay (reader blocks when it's full)
    # while a live port just keeps filling it.
    lines = queue.Queue(maxsize=2000)  # items are (reader generation, line)
    stop = threading.Event()
    running = threading.Event()  # cleared while a file playback is paused
    running.set()
    generation = [0]  # bumped on playback restart; superseded readers exit quietly

    def reader(my_gen):
        def superseded():
            return stop.is_set() or generation[0] != my_gen

        try:
            for line in make_line_source(args):
                if capture is not None:
                    capture.write(line)  # on the reader thread, so a slow GUI never loses data
                while not running.wait(0.2):  # hold here while paused
                    if superseded():
                        return
                while not superseded():
                    try:
                        lines.put((my_gen, line), timeout=0.2)
                        break
                    except queue.Full:
                        pass
                if superseded():
                    return
        except Exception as e:  # e.g. serial port unplugged
            if not superseded():
                lines.put((my_gen, f"[reader stopped: {e}]\n"))

    def start_reader():
        generation[0] += 1
        threading.Thread(target=reader, args=(generation[0],), daemon=True).start()

    start_reader()

    def on_timer():
        if not running.is_set():
            return
        # process whatever has arrived, within a time budget, then redraw once
        deadline = time.monotonic() + 0.03
        while time.monotonic() < deadline:
            try:
                gen, line = lines.get_nowait()
            except queue.Empty:
                break
            if gen == generation[0]:  # drop stragglers from a superseded reader
                dispatch_line(plotter, line)
        plotter.redraw_if_dirty()

    # Pause/Run and Restart controls: only meaningful (and only shown) when
    # replaying a file; a live port can't be paused without losing data
    if args.file:
        button = Button(plotter.fig.add_axes([0.01, 0.01, 0.09, 0.045]), "Pause (p)")

        def toggle(_event=None):
            if running.is_set():
                running.clear()
                button.label.set_text("Run (p)")
            else:
                running.set()
                button.label.set_text("Pause (p)")
            plotter.fig.canvas.draw_idle()

        button.on_clicked(toggle)

        # stdin can't be rewound, so Restart is only offered for a real file
        restart_button = None
        if args.file != "-":
            restart_button = Button(plotter.fig.add_axes([0.11, 0.01, 0.09, 0.045]), "Restart (r)")

            def restart(_event=None):
                start_reader()  # bumps the generation, which retires the old reader
                while True:  # discard anything the old reader queued
                    try:
                        lines.get_nowait()
                    except queue.Empty:
                        break
                plotter.reset()
                running.set()
                button.label.set_text("Pause (p)")
                plotter.fig.canvas.draw_idle()

            restart_button.on_clicked(restart)

        # matplotlib binds p to the pan tool and r to "home view"; free them up
        for param, key in (("keymap.pan", "p"), ("keymap.home", "r")):
            plt.rcParams[param] = [k for k in plt.rcParams[param] if k != key]

        # Speed box: type a multiple of real time (blank, 0 or "max" = unpaced);
        # takes effect immediately because the reader re-reads args.speed
        def speed_text():
            return "max" if not args.speed else f"{args.speed:g}"

        speed_box = TextBox(
            plotter.fig.add_axes([0.27, 0.01, 0.06, 0.045]), "Speed ", initial=speed_text()
        )

        def on_speed(text):
            text = text.strip().lower()
            if text in ("", "0", "max"):
                args.speed = None
            else:
                try:
                    value = float(text)
                    if value > 0:
                        args.speed = value
                except ValueError:
                    pass  # bad entry: keep the current speed
            # echo back the value actually in effect, without re-triggering on_submit
            speed_box.eventson = False
            try:
                speed_box.set_val(speed_text())
            finally:
                speed_box.eventson = True
            plotter.fig.canvas.draw_idle()

        speed_box.on_submit(on_speed)

        def on_key(e):
            if speed_box.capturekeystrokes:
                return  # typing in the speed box, not using shortcuts
            if e.key in (" ", "p"):
                toggle()
            elif e.key == "r" and restart_button is not None:
                restart()

        plotter.fig.canvas.mpl_connect("key_press_event", on_key)

        # full path of the file being replayed, where a live port shows its
        # capture path (after the Speed box, out to the right edge)
        add_text_box(
            plotter.fig, [0.35, 0.01, 0.64, 0.045],
            "stdin" if args.file == "-" else os.path.abspath(args.file),
        )

    # Capture file path box + Copy button (live ports only), in the bottom strip
    if not args.file:
        shown = capture.path if capture is not None else f"not capturing: {capture_error}"
        add_text_box(plotter.fig, [0.08, 0.01, 0.91, 0.045], shown)

        copy_button = Button(plotter.fig.add_axes([0.01, 0.01, 0.06, 0.045]), "Copy")

        def reset_copy_label():
            copy_button.label.set_text("Copy")
            plotter.fig.canvas.draw_idle()

        def on_copy(_event=None):
            if capture is None:
                return
            copy_button.label.set_text("Copied!" if copy_to_clipboard(capture.path) else "Failed")
            plotter.fig.canvas.draw_idle()
            revert = plotter.fig.canvas.new_timer(interval=1500)
            revert.single_shot = True
            revert.add_callback(reset_copy_label)
            revert.start()
            copy_timers.append(revert)  # keep a reference so it isn't collected before firing

        copy_timers = []
        copy_button.on_clicked(on_copy)

    timer = plotter.fig.canvas.new_timer(interval=50)
    timer.add_callback(on_timer)
    timer.start()

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if capture is not None:
            capture.close()
            print(f"Captured data saved to {capture.path}")


if __name__ == "__main__":
    main()
