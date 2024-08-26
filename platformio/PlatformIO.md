# Building StratoCore_LPC Using PlatformIO

## VSCode

1. Install PlatformIO Core using the script method (put link here)
1. Enable the command line tools (by making links in .local/bin)
1. Install the PlaftormIO extension in VSCode.

## Create a project

I found that importing an existing Arduino project is the way to go.

1. Mash the PlatformIO alien symbol on the left toolbar. This will initialize the 
   PlatformIO, and add a Home symbol to the bottom toolbar.
1. Mash the Home symbol. This will open a tab with "Welcome to PlatformIO"
1. Select "Import Arduino Project" under "Quick Access".
  1. Select the Teensy 4.1 as the board.
  1. Choose the folder containing the StratoCore_LPC repository.
  1. Choose Arduino as the framework.

The project directory will be created in a directory with the name ~/Documents/PlatformIO/Projects/YYMMDD-HHMMSS-TEENSY41/. People complain that you can't specify the project name and folder. Still 
researching this.

## Populating the project with LPC libraries

All of the LPC source code libraries will be cloned or unzipped into *lib/*. This can be done 
in a VSCode terminal:

```sh
cd lib
git clone git@github.com:MisterMartin/RS41.git
git clone git@github.com:MisterMartin/StratoCore.git
git clone git@github.com:MisterMartin/StrateoleXML.git
git clone git@github.com:MisterMartin/StratoCore_LPC.git
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
- For some reason, the build may fail and you have to run it a second time.

