# StratoCore_LPC Development Using PlatformIO

You can have it both ways! 

Compared to the the ArduinoIDE, PlatformIO provides a 
real software development environment. It includes the
standard IDE features that software engineers expect, such
as code completion, edit->build->run->clean workflows,
IntelliSense, static analysis, git integration, and much more.

This document describes how to work in the
VSCode PlatformIO environment, using the identical code base,
and still allows you to use the ArduinoIDE.

## Install PlatfromIO in VSCode

1. Run VSCode.
1. Install the Platform IDE extension.
1. Restart VSCode.

## Create the PlatfromIO project

1. Mash the PlatformIO alien symbol on the left toolbar. This will initialize
   PlatformIO, create a PLATFORMIO pane, and add a ***Home*** button to the 
   bottom toolbar.
1. Mash the Home button.
1. Select "New Project".
1. Give it a name.
1. Select the Teensy 4.1 as the board (_hint: just type 4.1_).
1. Uncheck "Location", and choose where you want it to go.
1. Hit "Finish", and wait while it builds the project.

Use the VSCode file explore to take a look at the created directory structure.
The ones which we care about are:
```sh
ProjectName/
          |
          |---lib/
          |---src/
```

## Import StratoCore_LPC

1. Open a VSCode terminal, and clone StratoCore_LPC into the *src/* directory:
```sh
cd src
git clone https://github.com/MisterMartin/StratoCore_LPC.git
cd ..
```
2. Remove the default *main.cpp* (created by PlatformIO), and link 
our main program (which contains _setup()_). We are fooling PlatfromIO
into recognizing the ArduinoIDE _.ino_ file:
```sh
cd src
rm -f main.cpp
cd StratoCore_LPC
rm -f main.cpp
ln -s StratoCore_LPC.ino main.cpp
cd ../..
```

## Import our libraries

All of the LPC source code libraries will be cloned or unzipped into _lib/_. 
This can be done in a VSCode terminal:
```sh
cd lib
git clone https://github.com/MisterMartin/RS41.git
git clone https://github.com/MisterMartin/StratoCore.git
git clone https://github.com/MisterMartin/StrateoleXML.git
unzip ../src/StratoCore_LPC/zips/Linduino.zip
unzip ../src/StratoCore_LPC/zips/LTC2983.zip
unzip ../src/StratoCore_LPC/zips/LT_SPI.zip
unzip ../src/StratoCore_LPC/zips/WDT_T4.zip
```

# Add Arduino libraries from the Internet

Add the following line to platformio.ini:
```sh
lib_deps = mikalhart/TinyGPSPlus@^1.1.0
```

# Build

- Hit the Alien button. 
- A menu will show up with PROJECT TASKS. 
- Press the Build button.

# Upload and Monitor
- Use the _Upload_ and _Monitor_ buttons in the PlatformIO pane.
- You can add the serial devices to *ProjectName/platformio.ini*
  (substitute your device):
```sh
upload_port = /dev/ttyACM0
monitor_port = /dev/ttyACM0
```

# Git

VSCode may not recognize all of the repositories (look in the Source 
Control tool in the left border).
To get it to recognize a repo, just ```cd <repo_dir>; git pull``` in each 
repo directory. 

Now all of your repos should appear in the VSCode source control pane.

If Git Graph doesn't show a repo, run  *Git Graph: Add Git Repository* 
from the VSCode Command Pallette.

