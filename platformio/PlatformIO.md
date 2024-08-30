# Building StratoCore_LPC Using PlatformIO

## Install PlatfromIO in VSCode

1. Run VSCode.
1. Install the PlatformIDE extension.
1. Restart VSCode.

## Create the PlatfromIO project

1. Mash the PlatformIO alien symbol on the left toolbar. This will initialize
   PlatformIO, create a PLATFORMIO pane, and add a Home symbol to the 
   bottom toolbar.
1. Mash the Home button.
1. Select "New Project".
1. Give it a name.
1. Select the Teensy 4.1 as the board.
1. Uncheck "Use default location", and choose where you want it to go.
1. Hit Finish, and wait while it builds the project.

Use the VSCode file explore to take a look at the created directory structure.
The ones we care about are:
```sh
ProjectName/
          |
          |---lib/
          |---src/
```

## Import StratoCore_LPC

1. Open a VSCode terminal, and clone StratoCore_LPC into the *src* directory:
```sh
cd src
git clone git@github.com:MisterMartin/StratoCore_LPC.git
```
2. Remove the default *main.cpp* (created by PlatformIO), and link 
our main program (contains setup())::
```sh
rm main.cpp
cd StratoCore_LPC
ln -s StraoCoreLPC.ino main.cpp
cd ../..
```

## Import our libraries

All of the LPC source code libraries will be cloned or unzipped into *lib/*. 
This can be done in a VSCode terminal:
```sh
cd lib
git clone git@github.com:MisterMartin/RS41.git
git clone git@github.com:MisterMartin/StratoCore.git
git clone git@github.com:MisterMartin/StrateoleXML.git
unzip ../src/StratoCore_LPC/zips/Linduino.zip
unzip ../src/StratoCore_LPC/zips/LTC2983.zip
unzip ../src/StratoCore_LPC/zips/LT_SPI.zip
unzip ../src/StratoCore_LPC/zips/WDT_T4.zip
```

# Add Arduino libraries from the Internet

The *TinyGPSPlus* library is used in this project. 

1. Hit the Home button
1. Push the Libraries button on the left toolbar. It will open a 
   library selector.
1. Search for TinyGPSPlus.
1. Click the download button for "TinyGPSPlus by Mikal Hart".
1. Press "Add to Project".
1. Select your project.
1. Hit Add

# Build

- Hit the Alien button. 
- A menu will show up with PROJECT TASKS. 
- Press the Build button.
- For the initial build, and after a full clean, the build may fail 
  and you may have to run it a second time. 

# Upload and Monitor
- Use the *Upload* and *Monitor* buttons in the PlatformIO pane.
- You can add the serial devices to *ProjectName/platformio.ini*
  (substitue your device):
```sh
upload_device=/dev/ttyACM0
monitor_device=/dev/ttyACM0
```

# Git

VSCode may not recognize all of the repositories (look in the Source 
Control tool in the left border).
To get it to recognize a repo, just ```cd <repo_dir>; git pull``` in each 
repo directory. 

Now all of your repos should appear in the VSCode source control pane.

If Git Graph doesn't show a repo, run  *Git Graph: Add Git Repository* 
from the VSCode Command Pallette.
