# Building StratoCore_LPC Using PlatformIO

## VSCode

1. Install PlatformIO Core using the script method (put link here)
1. Enable the command line tools (by making links in .local/bin)
1. Install the PlaftormIO extension in VSCode.

## Create the PlatformIO project

I found that importing an existing Arduino project is the way to go.

1. Clone StratoCore_LPC to an arbitrary and temporary location, e.g. /tmp.
   ```sh
   cd /tmp
   git clone git@github.com:MisterMartin/StratoCore_LPC.git
   ```
1. Mash the PlatformIO alien symbol on the left toolbar. This will initialize 
   PlatformIO, open a PLATFORMIO pane, and add a Home symbol to the bottom toolbar.
   Unfortunately, the pane only has options to open a project or create a project,
   so we need to use the Home buttom to get the Arduino import option.
1. Mash the Home symbol. This will open a tab with "Welcome to PlatformIO". 
1. Select "Import Arduino Project" under "Quick Access".
  1. Select the Teensy 4.1 as the board.
  1. ***Do not*** enable *Use libraries installed by Arduino IDE*.
  1. Choose the folder containing the temporary StratoCore_LPC 
     repository.
  1. Choose Arduino as the framework.
1. Press the *Import* button to create the project.
   - The project directory will be created in a directory with the name 
   *~/Documents/PlatformIO/Projects/YYMMDD-HHMMSS-TEENSY41/*. There's no
   option to specify overide the name or location.
   - StratoCore_LPC will be recursively copied to 
   *~/Documents/PlatformIO/Projects/YYMMDD-HHMMSS-TEENSY41/src*.
   Fortunately, this includes *.git/*.
1. Exit VSCode
1. Move and rename 
   *~/Documents/PlatformIO/Projects/YYMMDD-HHMMSS-TEENSY41/*
   to something of your choice.

## Populating the project with LPC libraries

All of the LPC source code libraries will be cloned or unzipped into *lib/*. This can be done 
in a VSCode terminal:

```sh
cd lib
git clone git@github.com:MisterMartin/RS41.git
git clone git@github.com:MisterMartin/StratoCore.git
git clone git@github.com:MisterMartin/StrateoleXML.git
unzip ../src/zips/Linduino.zip
unzip ../src/zips/LTC2983.zip
unzip ../src/zips/LT_SPI.zip
unzip ../src/zips/WDT_T4.zip
```

# Add Arduino libraries

The TinyGPSPlus library is used in this project. 

From the PIO Home tab:

- Mash the Libraries button on the left toolbar. It will open a libraries
  selector.
- Search for TinyGPSPlus.
- Click on "TinyGPSPlus by Mikal Hart".
- Press "Add to Project".

# Build

- Hit the Alien button. 
- A menu will show up with PROJECT TASKS. 
- Press the Build button.
- For the initial build, and after a full clean, the build may fail and you have to run it a second time. 

# Git

VSCode may not recognize all of the repositories (look in the Source Control tool in the left border).
To get it to recognize a repo, just ```cd <dir>; git pull``` in each repo directory. 
Note that the *StratoCore_LPC* repo has been imported into the *src/* directory, so just
do a ```git pull``` in that directory. Now all of your repos will appear in the VSCode source control pane.

Git Graph may not show your repos, so for each of the repos, run the *Git Graph: Add Git Repository* command from the VSCode Command Pallette.

