# StratoCore_LPC

LASP Optical Particle Counter for Strateole 2

This is the main Teensy application for the LPC main board.
It depends on several other source code repositories and 
Arduino libraries.

In order to play well with Arduino IDE, we have put all of the application
code, including the main board program, in the same `libraries/`
directory where the Arduino IDE keeps its libraries. This will simplify
the build environment.

*Note: The original GitHub repository was kalnajslab/LPC. 
The original checkin was 22-Aug-2019. A bit of code development continued
after that, but was not submitted to the repo. The repo was
updated with those modifications on 01-Jun-2024. The repo was 
forked to MisterMartin/LPC for the development work prior to the Kiruna
campaign. After the Kiruna campaign MisterMartin/LPC was transferred 
to kalnajslab-org/LPC. It was finally renamed kalnajslab-org/StratoCore_LPC.*


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
git clone https://github.com/kalnajslab-org/StratoCore_LPC   # Mainboard application
git clone https://github.com/kalnajslab-org/StratoCore       # StratoCore framework
git clone https://github.com/kalnajslab-org/StrateoleXML     # Strateole message parsing 
                                                             # and comms support
git clone https://github.com/kalnajslab-org/RS41             # RS41 support library

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

- Open *StratoCore_LPC/StratoCore_LPC.ino* in the ArduinoIDE.
- Mash the compile button in the Arduino IDE.

## Arduino notes

- *Rebuilding:* It's a widely complained problem that the ArduinoIDE does not have a way to do a clean
  build. This is a big hassle when you want to work on cleaning up warnings in our user libraries.
  There are several convoluted methods proposed for forcing a build. But the simplest one seems to be:
    - Select a different board type and try to build with that. It doesn't matter which
      one; it will most likely fail.
    - Go back to the Teensy 4.1 type, and do a new build. This will rebuild the
      sketych _and_ all of the user libraries. It will not rebuild the core, but
      we really don't care about that.
- Make sure that you have the _Sketchbook location_ set properly in the preferences. It
  normally is _~/Documents/Arduino_, and contains the directory _libraries/_, which
  all of our repositories are in. If it is set wrong, you can open a sketch in 
  a repository, but when you try to build it, the Arduino IDE will not find header files.
  You need to restart arduinoIDE after you change the preference.
- The Arduino IDE serial monitor seems to have a limit to the number of lines
  it will display. After a few hours of displaying the output from the instrument, 
  it just stops receiving/displaying anything new.
- If you use the MacOS `screen` command to capture data, don't resize
  the terminal window. It will clear the display buffer.
- Discovered that if a non-void function does not include a return 
  statement, it will crash the Arduino! It produces a compile
  warning, when really it should produce a compile error.
  This [thread](https://github.com/espressif/arduino-esp32/issues/5867),
  and [this one also](https://stackoverflow.com/questions/57163022/c-crash-on-a-non-void-function-doesnt-have-return-statement)
  report the same issue.
