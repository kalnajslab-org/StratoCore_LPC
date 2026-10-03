#!/usr/bin/env python3
"""
plot_lpc_bins.py

Live-plots LPC/PHA bin data from a serial console or a saved log file. Four
line formats are recognized on the same stream, auto-detected line by line:

1. StratoLPC's 16 size bins, printed once per sample frame by
   StratoLPC::fillBins() (see printBinsCSV() in StratoLPC.cpp), read from the
   LPC main board's DEBUG_SERIAL console:
       HGBINS,<record>,<bin0>,<bin1>,...,<bin15>
       LGBINS,<record>,<bin0>,<bin1>,...,<bin15>

   The same 16 size bins may also show up in the older, plain-text debug
   format (no record number) some builds of fillBins() still print instead:
       High Gain Bins: <bin0>, <bin1>, ..., <bin15>,
       Low Gain Bins: <bin0>, <bin1>, ..., <bin15>,

2. The PHA's raw 256-element downsampled pulse-height spectra, printed to its
   own USB DEBUG_SERIAL console (PlatformIO PHA_V5_1.ino, V5.1a+) once per
   CYCLE_TIME when enabled with the '#hgprint,1' / '#lgprint,1' interactive
   commands:
       HG_Small_Array: <b0>,<b1>,...,<b255>,
       LG_Small_Array: <b0>,<b1>,...,<b255>,

3. The same raw 256-element spectra, but read from the PHA's OUTPUT_SERIAL
   (Serial1, 500000 baud) line to the main board instead of its USB console
   (e.g. tapping Serial1 TX with a USB-TTL adapter for bench testing):
       <timestamp>,<laserI>,<threshold>,<pulse_count>,<256 HG values>,<256 LG values>,E

All other lines are ignored for plotting but echoed to stdout so you can
still see log messages / other console output.

Usage:
    # LPC main board console (16 size bins)
    python3 plot_lpc_bins.py --port /dev/tty.usbmodemXXXX --baud 115200

    # PHA board's own USB console (256-element raw spectra); once connected,
    # send '#hgprint,1' and '#lgprint,1' to the PHA to turn printing on
    python3 plot_lpc_bins.py --port /dev/tty.usbmodemYYYY --baud 115200

    # PHA board's Serial1 line to the main board instead (256-element raw spectra)
    python3 plot_lpc_bins.py --port /dev/tty.usbserialXXXX --baud 500000

    # replay a saved log instead of a live port (format is auto-detected either way)
    python3 plot_lpc_bins.py --file console_log.txt

    # read from stdin (simulates a device; --speed and Pause/Run still apply)
    cat console_log.txt | python3 plot_lpc_bins.py --file -

    # replay a timestamped log at 10x real time (1 = real time, 0.5 = half speed)
    python3 plot_lpc_bins.py --file LPC_DBG_log.txt --speed 10

Requires: pyserial, matplotlib
    pip install pyserial matplotlib
"""

import argparse
import math
import queue
import re
import sys
import threading
import time

import matplotlib.pyplot as plt
from matplotlib.widgets import Button

try:
    import serial
except ImportError:
    serial = None

N_SIZE_BINS = 16  # StratoLPC's downsampled size bins (HGBins/LGBins)

# --speed replay skips the waiting time while the log says the instrument is in
# one of these states (or before any state is seen): no bins are produced then,
# and SB is entered silently from FL_IDLE so it looks like a long FL_IDLE.
ENTERING_RE = re.compile(r"NOM: Entering (\w+)")
IDLE_STATES = {None, "FL", "FL_IDLE"}

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
                if args.speed:
                    ts = parse_log_timestamp(line)
                    if ts is not None:
                        if prev_ts is not None:
                            # the gap belongs to the state we were in on the previous
                            # line; skip it while idle/standby since nothing is plotted
                            if state not in IDLE_STATES:
                                dt = (ts - prev_ts) % 86400  # tolerate midnight wrap
                                wait = dt / args.speed - (time.monotonic() - t_prev_wall)
                                if wait > 0:
                                    time.sleep(wait)
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


class BinPlotter:
    """Owns the figure and knows how to redraw whichever bin arrays have new data."""

    def __init__(self):
        self.fig, ((self.ax_hg, self.ax_lg), (self.ax_pha_hg, self.ax_pha_lg)) = plt.subplots(
            2, 2, figsize=(13, 8)
        )

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
        self.hg_peak_annotation = None
        self.lg_peak_annotation = None
        for ax, title in ((self.ax_hg, "StratoLPC High Gain Size Bins"), (self.ax_lg, "StratoLPC Low Gain Size Bins")):
            ax.set_title(title)
            ax.set_xlabel("Size bin")
            ax.set_ylabel("Counts")
            ax.set_ylim(0.5, 10)  # placeholder range so switching to log scale below has something positive to work with
            ax.set_yscale("log")

        # PHA raw spectra: created lazily once we know how many elements they have
        self.pha_hg_line = None
        self.pha_lg_line = None
        self.pha_hg_peak_annotation = None
        self.pha_lg_peak_annotation = None
        for ax, title in ((self.ax_pha_hg, "PHA Raw High Gain Spectrum"), (self.ax_pha_lg, "PHA Raw Low Gain Spectrum")):
            ax.set_title(title + " (no data yet)")
            ax.set_xlabel("Raw ADC bin (reversed)")
            ax.set_ylabel("Counts")

        self.dirty = False
        self.fig.tight_layout(rect=(0, 0.07, 1, 1))  # bottom strip: button + status bar
        # status bar: latest value of each housekeeping line (STATUS_FIELDS)
        self.status = {key: "--" for key in STATUS_FIELDS.values()}
        self.status_text = self.fig.text(
            0.99, 0.03, "", ha="right", va="center", fontsize=9, family="monospace"
        )
        self._render_status()

    def update_size_bins(self, tag, record, bins):
        if tag == "HGBINS":
            self.hg_frame_count += 1
            record = record if record is not None else self.hg_frame_count
            self.hg_record, self.hg_bins = record, bins
            bars, ax, label, peak_attr = self.hg_bars, self.ax_hg, "StratoLPC High Gain Size Bins", "hg_peak_annotation"
        else:
            self.lg_frame_count += 1
            record = record if record is not None else self.lg_frame_count
            self.lg_record, self.lg_bins = record, bins
            bars, ax, label, peak_attr = self.lg_bars, self.ax_lg, "StratoLPC Low Gain Size Bins", "lg_peak_annotation"

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

        self._update_peak_label(ax, xs, bins, original_indices, peak_attr)
        self._flush()

    def update_pha(self, sample):
        """Update both PHA channels at once from a raw-CSV sample dict (parse_pha_line())."""
        extra = (
            f"t={sample['timestamp']}, pulses={sample['pulse_count']}, "
            f"thresh={sample['threshold']}, laserI={sample['laser_i']:.3f}"
        )
        self.update_pha_channel("hg", sample["hg"], extra)
        self.update_pha_channel("lg", sample["lg"], extra)

    def _update_peak_label(self, ax, xs, ys, original_indices, attr_name):
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
        # Label sits just above the peak with an arrow pointing down to it; the
        # callers leave headroom in the y-limits so it stays inside the axes.
        # Near either edge, anchor the text to that side so it doesn't spill out.
        frac = peak_x / max(len(ys) - 1, 1)
        ha = "left" if frac < 0.1 else "right" if frac > 0.9 else "center"
        annotation = ax.annotate(
            f"peak: bin {peak_bin}\n({peak_y} counts)",
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
            title += f" ({extra_title})"
        ax.set_title(title)

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
    """Parse one console line and update the plot; echo it if it isn't plottable."""
    raw = line
    # logger-saved files prefix each line with '[HH:MM:SS.mmm] '; drop it
    if line.startswith("["):
        end = line.find("] ")
        if 0 < end <= 16:
            line = line[end + 2:]
    label, sep, value = line.partition(":")
    if sep and label in STATUS_FIELDS and value.strip():
        return plotter.update_status(STATUS_FIELDS[label], value.strip())
    # cheap prefix checks first so ordinary log lines skip all the parsers
    if line.startswith("HGBINS,"):
        result = parse_size_bins_line(line, "HGBINS")
        if result is not None:
            return plotter.update_size_bins("HGBINS", *result)
    elif line.startswith("LGBINS,"):
        result = parse_size_bins_line(line, "LGBINS")
        if result is not None:
            return plotter.update_size_bins("LGBINS", *result)
    elif line.startswith("High Gain Bins:"):
        result = parse_labeled_bins_line(line, "High Gain Bins")
        if result is not None:
            return plotter.update_size_bins("HGBINS", None, result)
    elif line.startswith("Low Gain Bins:"):
        result = parse_labeled_bins_line(line, "Low Gain Bins")
        if result is not None:
            return plotter.update_size_bins("LGBINS", None, result)
    elif line.startswith("HG_Small_Array:"):
        result = parse_pha_debug_array_line(line, "HG_Small_Array")
        if result is not None:
            return plotter.update_pha_channel("hg", result)
    elif line.startswith("LG_Small_Array:"):
        result = parse_pha_debug_array_line(line, "LG_Small_Array")
        if result is not None:
            return plotter.update_pha_channel("lg", result)
    else:
        result = parse_pha_line(line)
        if result is not None:
            return plotter.update_pha(result)
    # pass through anything else so you can still see instrument logs
    print(raw.rstrip())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="Serial port (e.g. /dev/tty.usbmodem1234 or COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate (default: 115200; use 500000 when reading the PHA's own Serial1 output)")
    parser.add_argument("--file", help="Replay lines from a saved log file instead of a live serial port; use - to read from stdin")
    parser.add_argument("--speed", type=float, help="With --file, replay at this multiple of the log's real-time pace using its [HH:MM:SS.mmm] timestamps, skipping idle/standby periods (1 = real time, 10 = 10x faster, 0.5 = half speed). Default: as fast as possible")
    args = parser.parse_args()

    if not args.file and not args.port:
        parser.error("either --port or --file is required")
    if args.speed is not None:
        if not args.file:
            parser.error("--speed only applies with --file")
        if args.speed <= 0:
            parser.error("--speed must be greater than 0")

    plotter = BinPlotter()

    # Read the port/file on a background thread so the GUI never blocks on I/O.
    # The bounded queue throttles file replay (reader blocks when it's full)
    # while a live port just keeps filling it.
    lines = queue.Queue(maxsize=2000)
    stop = threading.Event()
    running = threading.Event()  # cleared while a file playback is paused
    running.set()

    def reader():
        try:
            for line in make_line_source(args):
                while not running.wait(0.2):  # hold here while paused
                    if stop.is_set():
                        return
                while not stop.is_set():
                    try:
                        lines.put(line, timeout=0.2)
                        break
                    except queue.Full:
                        pass
                if stop.is_set():
                    return
        except Exception as e:  # e.g. serial port unplugged
            lines.put(f"[reader stopped: {e}]\n")

    threading.Thread(target=reader, daemon=True).start()

    def on_timer():
        if not running.is_set():
            return
        # process whatever has arrived, within a time budget, then redraw once
        deadline = time.monotonic() + 0.03
        while time.monotonic() < deadline:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                break
            dispatch_line(plotter, line)
        plotter.redraw_if_dirty()

    # Pause/Run control: only meaningful (and only shown) when replaying a file;
    # a live port can't be paused without losing data
    if args.file:
        button = Button(plotter.fig.add_axes([0.01, 0.01, 0.08, 0.045]), "Pause")

        def toggle(_event=None):
            if running.is_set():
                running.clear()
                button.label.set_text("Run")
            else:
                running.set()
                button.label.set_text("Pause")
            plotter.fig.canvas.draw_idle()

        button.on_clicked(toggle)
        plotter.fig.canvas.mpl_connect(
            "key_press_event", lambda e: toggle() if e.key == " " else None
        )

    timer = plotter.fig.canvas.new_timer(interval=50)
    timer.add_callback(on_timer)
    timer.start()

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == "__main__":
    main()
