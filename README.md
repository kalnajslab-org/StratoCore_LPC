# LPC
LASP Optical Particle Counter for Strateole 2

Original checkin was 22-Aug-2019. A bit of code devlopment continued
after that, but was not submitted to the repo. The repo was
updated with those modifications on 01-Jun-2024.

This is the main Teensy application for the LPC main board.
It depends on several other source code repositories and 
Arduino libraries.

For the time being, we have decided to put all of the application
code, including the main board program, in the same `libraries/`
directory where the Arduino IDE keeps its libraries. This will simplify
the build environment.

## 1. Installation

There are 3 steps for configuring the development environment:
  1. Install Teensyduino (v1.59.0 or later).
  1. Clone the relevant LPC Arduino code repositories.
  1. Install Arduino libraries.

### 2. Teensyduino

See the download and installation instructions for 
<a href="https://www.pjrc.com/teensy/td_download.html" target="_blank">Teensyduino</a>.

### 3. LPC Arduino code repositories

Cloned from GitHub:

```sh
cd Documents/arduino/libraries # Or wherever your Arduino libraries are
git clone https://github.com/MisterMartin/StratoCore_LPC   # Mainboard application
git clone https://github.com/MisterMartin/StratoCore       # StratoCore framework
git clone https://github.com/MisterMartin/StrateoleXML     # Strateole message parsing and comms support
git clone https://github.com/MisterMartin/RS41             # RS41 support library

```

### Arduino libraries

LPC uses one standard library, and several others which are either not
visible to the the Arduino IDE library manager, or are hard to find
on the Internet. We have captured zip files of these latter ones, so that
we can preserve them, and freeze the versions. These zip files are
saved in `StratoCore_LPC/zips`.

- Using the Arduino IDE library manager, find and install `TinyGPSPlus`

- Install our currated libraries, by unzipping the .zip files
  located in `StratoCore_LPC/zips/` into `Documents/arduino/libraries/`.
  This can be done manually, or by using the Arduino IDE library manager
  to install a .zip file.

Note that the zipped libraries won't appear in the Arduino IDE library
listing. It might be because they weren't installed from web
sites, and so the library manager can't track revision updates?

## Building

  Mash the compile button in the Arduino IDE.

