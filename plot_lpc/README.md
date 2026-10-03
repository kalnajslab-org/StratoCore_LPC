# plot-lpc-bins

Live plots of Strateole 2 LPC data from the instrument's serial console or from a saved console log. By default it shows the StratoLPC high-gain and low-gain size bins, with a status bar of housekeeping values. With `--pha` it shows the PHA board's raw high-gain and low-gain pulse-height spectra instead.

![plot-lpc-bins replaying an LPC debug log](plot-lpc-bins.png)

## Quickstart

Requires Python 3.8 or newer. Dependencies (`pyserial`, `matplotlib`) are installed automatically.

**Install from GitHub**

```
pip install "git+https://github.com/kalnajslab-org/StratoCore_LPC.git#subdirectory=plot_lpc"
```

The package lives in the `plot_lpc` subdirectory of the repo, hence `#subdirectory=plot_lpc`. Add `@<branch-or-tag>` after `.git` to install something other than the default branch. If you use SSH keys with GitHub, use `git+ssh://git@github.com/kalnajslab-org/StratoCore_LPC.git#subdirectory=plot_lpc` instead.

**Install from a local clone**

```
git clone git@github.com:kalnajslab-org/StratoCore_LPC.git
pip install ./StratoCore_LPC/plot_lpc
```

Use `pip install -e ./StratoCore_LPC/plot_lpc` if you want edits to the source to take effect without reinstalling.

Install into a virtual environment or with `pipx install ...` if you'd rather not touch your main Python.

**Updating**

Re-run the install command with `--upgrade`:

```
pip install --upgrade "git+https://github.com/kalnajslab-org/StratoCore_LPC.git#subdirectory=plot_lpc"
```

Pip decides what is newer from the `version` in `pyproject.toml`, so a new version has to be published with a bumped version number to be picked up. If you know the code changed but the version didn't, add `--force-reinstall` (and `--no-deps` to skip reinstalling matplotlib and pyserial). With pipx, use `pipx upgrade plot-lpc-bins`.

For a local clone, `git pull` and run `pip install --upgrade ./StratoCore_LPC/plot_lpc` again. An editable install (`-e`) needs only the `git pull`, unless the commands in `pyproject.toml` changed.

**Run it**

```
# read live from the LPC board's debug console
plot-lpc-bins --port /dev/tty.usbmodemXXXX --baud 115200

# or replay a saved console log (paced at 10x real time by default)
plot-lpc-bins --file LPC_DBG_2026-10-02T11-00-32.txt

# PHA raw spectra instead of the LPC size bins: add --pha
plot-lpc-bins --pha --port /dev/tty.usbmodemYYYY --baud 115200
```

The command is `plot-lpc-bins` (hyphens). `python -m plot_lpc_bins` works too.

## Choosing the plots

Only one pair of plots is shown at a time:

| Option | Plots |
|---|---|
| (default) | StratoLPC high-gain and low-gain size bins, plus the housekeeping status bar |
| `--pha` | PHA raw high-gain and low-gain pulse-height spectra |

Data for the plot you didn't select is recognized and silently dropped. Lines that are neither are printed to the terminal.

## Input sources

| Option | Reads from |
|---|---|
| `--port PORT [--baud N]` | A live serial port (default 115200 baud; use 500000 for the PHA's own Serial1 output, with `--pha`). |
| `--file PATH` | A saved log file, replayed. |
| `--file -` | Standard input, e.g. `cat log.txt \| plot-lpc-bins --file -`. |

Lines are auto-detected one at a time, so any mix of the formats below can appear on the same stream. A `[HH:MM:SS.mmm] ` timestamp prefix, as written by the logger, is ignored.

| Format | Where it comes from | Plot |
|---|---|---|
| `HGBINS,<record>,<16 values>` and `LGBINS,<record>,<16 values>` | LPC board console (`StratoLPC::fillBins()`) | Default (LPC) |
| `High Gain Bins: ...` / `Low Gain Bins: ...` | Older plain-text version of the same 16 bins | Default (LPC) |
| `HG_Small_Array: ...` / `LG_Small_Array: ...` | PHA board USB console, after sending `#hgprint,1` and `#lgprint,1` to it | `--pha` |
| `<timestamp>,<laserI>,<threshold>,<pulse_count>,<256 HG>,<256 LG>,E` | PHA board Serial1 line to the main board (500000 baud) | `--pha` |
| `Pulse Count:`, `Flow:`, `Pump1 T:`, `Pump2 T:`, `Inlet T:` | LPC board console | Default (LPC), status bar |

Any other line is printed to the terminal unchanged, so you can still see the instrument's log messages. The five housekeeping lines go to the status bar (default plot only) and are not echoed.

## Playback controls

These appear when you use `--file`. A live `--port` has no controls, because pausing a serial stream would lose data.

| Control | Key | What it does |
|---|---|---|
| Pause / Run | `p` or space | Freezes and resumes playback. |
| Restart | `r` | Starts again from the beginning of the file and clears the plots. Not available with `--file -`, since a pipe can't be rewound. |
| Speed box | | Type a multiple of real time and press Enter, e.g. `20` or `0.5`. Blank, `0` or `max` replays as fast as possible. |

Playback is paced from the log's own timestamps. Periods where the instrument is idle or in standby (no size-bin data is produced) are skipped rather than waited out, so you don't sit through the minutes between measurements.

`--speed N` sets the starting speed (default **10**; `--speed 0` means unpaced). It is ignored with `--port`.

## What the plots show

The size-bin panels have 16 bars each. The x-axis is the bin's lower diameter edge in nm, as in the LPC data file header (where the columns are labelled `diam >nm`). The tallest bar is annotated with its bin number, size and count.

| Panel | Bins (nm) |
|---|---|
| High gain | 275, 300, 325, 350, 375, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000 |
| Low gain | 1200, 1400, 1600, 1800, 2000, 2500, 3000, 3500, 4000, 6000, 8000, 10000, 13000, 16000, 24000, 24000 |

The last low-gain bin is always empty: its raw-array range in the firmware is 255 to 255, which is why 24000 appears twice.

With `--pha`, the two panels show the PHA's raw 256-bin spectra, drawn with the largest pulse on the right and the bin nearest the trigger threshold on the left. They stay empty ("no data yet") until a spectrum arrives; for the PHA's USB console, send `#hgprint,1` and `#lgprint,1` to it first. When the spectra come from the Serial1 line, each panel's title also shows the timestamp, pulse count, threshold and laser current.

## Testing without hardware

`lpc-fake-port` creates a pseudo-terminal and feeds a saved log into it, so you can exercise the real `--port` path with no device attached:

```
# terminal 1: prints a port such as /dev/ttys012 and waits
lpc-fake-port LPC_DBG_2026-10-02T11-00-32.txt --speed 20

# terminal 2
plot-lpc-bins --port /dev/ttys012 --baud 115200

# then press Enter in terminal 1 to start sending
```

Options: `--speed N` (multiple of real time, default 1), `--loop` (repeat forever), `--no-wait` (don't wait for Enter).
