# StratoCore Development Using PlatformIO

***This method of combining ArduinoIDE and PlatformIO has been obsoleted.
   See the README for [kalnajslab-org](https://github.com/kalnajslab-org#teensy-firmware-quickstart).
   However, the method for installing PlatformIO in VSCode remains the same (below).***

You can have it both ways! 

Compared to the the ArduinoIDE, PlatformIO provides a 
real software development environment. It includes the
standard IDE features that software engineers expect, such
as code completion, edit->build->run->clean workflows,
IntelliSense, static analysis, git integration, and much more.

This document describes how to work in the
VSCode PlatformIO environment, using the identical code base,
and still allows you to use the ArduinoIDE.

*You should be able to complete the following command
 line actions just by pushing the copy-to-clipboard button
 and pasting into the VSCode terminal*

## Install PlatformIO in VSCode

1. Run VSCode.
1. Install the *PlatformIO IDE* extension.
1. Mash the 'Alien' button in the left toolbar. This will install
   PlatformIO core, create a PLATFORMIO pane, and add a ***Home***
   button to the bottom toolbar.
1. Restart VSCode.

## Create the PlatfromIO project

1. Mash the alien button on the left toolbar. 
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

## Import the main project

Open a VSCode terminal, and clone StratoCore_LPC into the *src/* directory:
```sh
cd src
git clone https://github.com/kalnajslab-org/LPC.git
cd ..
```

## Finish the setup

```sh
rm platformio.ini
ln -s src/LPC/platformio/platformio.ini
cd src
rm main.cpp
```

# Build

- Hit the Alien button. 
- A menu will show up with PROJECT TASKS. 
- Press the Build button.

# Upload and Monitor
- Use the _Upload_ and _Monitor_ buttons in the PlatformIO pane.

You can add the serial devices to *ProjectName/platformio.ini*,
but usually not needed unless you are running on a VM:
```sh
upload_port = /dev/ttyACM0
monitor_port = /dev/ttyACM0
```

# Git

VSCode may not find all of the repositories (look in the Source 
Control tool in the left border). To get it to recognize a repo, 
just open a file in each repository.

Now all of your repos should appear in the VSCode source control pane.

If Git Graph doesn't show a repo, run  *Git Graph: Add Git Repository* 
from the VSCode Command Pallette.

