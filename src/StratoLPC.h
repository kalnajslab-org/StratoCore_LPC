/*
 *  StratoLPC.h
 *  Author:  Alex St. Clair
 *  Created: June 2019
 *  
 *  This file declares an Arduino library (C++ class) that inherits
 *  from the StratoCore class. It serves as both a template and test
 *  class for inheriting from the StratoCore.
 * Updated Arpil 2024 for LOPC main board rev F/G and Teensy 4.1
 */

#ifndef STRATOLPC_H
#define STRATOLPC_H

#include <time.h>
#include "StratoCore.h"
#include "LOPCLibrary_revF.h"  //updated library for Teensy 4.1
//#include "LPCBufferGuard.h"   //this is not needed for Teensy 4.1 as buffer size is set in user code
#include "RS41.h"

// for testing purposes, use LPC
#define ZEPHYR_SERIAL   Serial8 // LPC - Teensy 4.1
#define INSTRUMENT      LPC
#define ZEPHYR_SERIAL_BUFFER_SIZE 4096

/// Schedule the OPC for immediate start after entering flight mode,
/// rather than waiting for the hour.
#define OPC_IMMEDIATE_START false

// RS41 options
/// Print RS41 samples to the console.
#define RS41_DEBUG_PRINT false
/// How often to sample the RS41 during flight mode.
#define RS41_SAMPLE_PERIOD_SECS 1
/// The telemetry reporting period of RS41 samples.
/// A new local storage file is also made at the same interval.
#define RS41_N_SAMPLES_TO_REPORT 300

// number of loops before a flag becomes stale and is reset
#define FLAG_STALE      2

// hardcoded limits for LPC
#define T_PUMP_SHUTDOWN 75.0 // Max operating temperature for rotary vane pump

#define PHA_BUFFER_SIZE 4096

// todo: perhaps more creative/useful enum here by mode with separate arrays?
// WARNING: this construct assumes that NUM_ACTIONS will be equal to the number
// of actions. Never seen this coding style before; seems dangerous.
enum ScheduleAction_t : uint8_t {
    NO_ACTION = NO_SCHEDULED_ACTION,
    SEND_IMR,
    START_WARMUP,
    START_FLUSH,
    START_MEASUREMENT,
    RESEND_SAFETY,
    RS41_SAMPLE,
    NUM_ACTIONS
};

/// @brief The RS41 compressed sample for use in the RS41 TM message
struct rs41TmSample_t {
    uint8_t valid;
    uint32_t secs;
    uint16_t tdry;
    uint16_t humidity;
    uint16_t tsensor;
    uint16_t pres;
    uint16_t error;
};

class StratoLPC : public StratoCore {
public:
    StratoLPC();
    ~StratoLPC() { };

    // called before the loop begins
    void InstrumentSetup();

    // called at the end of each loop
    void InstrumentLoop();

private:
    // Mode functions (implemented in unique source files)
    void StandbyMode();
    void FlightMode();
    void LowPowerMode();
    void SafetyMode();
    void EndOfFlightMode();
    
    //LPC Functions
    void LPC_Shutdown();
    TimeElements Get_Next_Hour();
  //  time_t Next_Start_Time(time_t);
    void ReadHK(int);
    void CheckTemps();
    void AdjustPumps();
    float getFlow();
    int parsePHA(int);
    void fillBins(int,int);
    void PackageTelemetry(int);
    
    // PHA functions
    /// @brief Configure the PHA if needed
    /// If the Set_triggerPHAconfig flag is set, 
    /// configure the PHA, and clear Set_triggerPHAconfig.
    void phaConfig();

    // RS41 Functions
    /// @brief (Re)start the RS41 measurement action.
    void rs41Start();
    /// @brief See if the RS41 action has been triggered.
    /// If so, collect a sample and reset the action.
    /// If RS41_N_SAMPLES_TO_REPORT have been collected,
    /// transmit them as a TM data packet.
    /// If time is valid, save the sample to local storage.
    void rs41Action();
    /// @brief Send an RS41 telemetry package
    void rs41SendTelemetry(uint32_t sample_start_time, rs41TmSample_t* rs41_sample_array, int n_samples);
    /// @brief A header for RS41 CSV data
    /// @return The header
    String rs41CsvHeader();
    /// @brief Get a CSV version of RS41 data
    String rs41CsvData(RS41::RS41SensorData_t &rs41_data);
    /// @brief Send RS41 data to the console
    void rs41PrintCsv(RS41::RS41SensorData_t &rs41_data);

    // Local storage functions
    /// @brief Create a time based file name
    String SDFileName(String prefix, String extension, time_t timetag);
    /// @brief Formatted time respresentation
    /// @param timetag The time of interest
    /// @return Formatted as YYYYMMDDHHmmSS
    String TimeString(time_t timetag);
    /// @brief The number of LPC records in BinData
    /// @param Records 
    void writeLPCtoSD(int Records);
    /// @brief
    /// RS41 local storage processing
    /// Create a new RS41 local file every RS41_N_SAMPLES_TO_REPORT.
    /// Append the samples in CSV format.
    /// @param rs41_data One sample of RS41 data
    void rs41LocalStorage(RS41::RS41SensorData_t& rs41_data);
    
    LOPCLibrary OPC;  //Creates an instance of the OPC
    RS41 _rs41; // The RS41 sensor
    
    // Telcommand handler - returns ack/nak
    bool TCHandler(Telecommand_t telecommand);

    // Action handler for scheduled actions
    void ActionHandler(uint8_t action);

    // Safely check and clear action flags
    bool CheckAction(uint8_t action);

    // Monitor the action flags and clear old ones
    void WatchFlags();
    
    //Teensy 4.1 Serial buffer
    uint8_t OPC_serial_RX_buffer[PHA_BUFFER_SIZE];

    // Global variables used by LPC
    /* Variables with initial values that can be configured via telecommand */
    int Set_numberSamples = 80;        // Number of samples to collect for each measurement
    int Set_samplesToAverage = 1;      // Number of 2 second PHA packets to avergae per sample
    int Set_cycleTime = 10;            // Time between measurements in minutes
    int Set_warmUpTime = 10;           // Warm up time in seconds
    int Set_LaserTemp = -30;           // Target Laser Temperature
    int Set_FlushingTime = 10;         // Flushing Time in seconds
    uint16_t Set_phaHiGainThreshold;   // PHA high threshold
    uint16_t Set_phaHiGainOffset;      // PHA high gain baseline offset
    uint16_t Set_phaLoGainOffset;      // PHA low gain baseline offset
    bool Set_triggerPHAconfig = false; // Trigger the PHA configuration, which happens during FL_WARMUP
    bool Set_rs41regen = false;        // Initiate an RS41 regeneration
    /* These should be set for each instrument */
    /*These are for LPC 0007*/
    int Set_HGBinBoundaries[17] = {0,6,13,19,25,31,37,48,59,69,78,87,95,102,109,120,129}; // 16 high gain bins
    int Set_LGBinBoundaries[17] = {26,32,36,40,44,48,57,65,73,81,111,143,187,210,230,255,255}; //16 Low gain bins
    
    
    int NumberLGBins = 16;
    int NumberHGBins = 16;
    int NumberHKChannels = 16;
    
    uint16_t BinData[32][300];  //Array to store aerosol bins for a full measurement cycle
    uint16_t HKData[16][300];  //Array to store HK data
    TimeElements StartTime;
    time_t StartTimeSeconds;
    uint32_t MeasurementStartTime; //actually a time_t, set to uint32_t for overloaded TM function in XMLwriter
    
    /*Global Variables */
    
    /*HK Variables */
    float TempPump1;
    float TempPump2;
    float TempInlet;
    float TempLaser;
    float TempPCB;
    float VBat;
    float VTeensy;
    float VMotors;
    float Flow = 20000.0/30.0; //preset flow to default in case MFM doesn't work
    float IPump1;
    float IPump2;
    float IHeater1;
    float IHeater2;
    float IDetector;
    float ILaser;
    float VDetector;
    float VPHA;
    float Pressure;
    
    /*Variables Related to Pump Back EMF Control */
    int backEMF1 = 0;
    int backEMF2 = 0;
    float BEMF1_V = 0;
    float BEMF2_V = 0;
    float BEMF1_SP = 7.8; //Set point for large pumps
    float BEMF2_SP = 7.8; //Set point for large pumps
    float error1 = 0.0;
    float error2 = 0.0;
    float Kp = 30.0;
    int BEMF1_pwm = 128;
    int BEMF2_pwm = 128;
    
    /*PHA HK Variables*/
    long PHA_TimeStamp = 0;
    int PHA_Threshold = 0;
    float PHA_LaserI = 0;
    long PHA_PulseCount = 0;
    unsigned long ElapsedTime = 0;
    
    String StringBins = "";
    float DeadBand = 0.5;
    
    int Frame = 0;
    char inByte;
    int ErrorCount = 0;

    char PHAArray[PHA_BUFFER_SIZE]; //bit char array to hold data from PHA
    int LGArray[256]; //int array for data from PHA LG channel
    int HGArray[256]; //int array for data from PHA HG channel
    int HGBins[16]; //int array for downsampled data
    int LGBins[16]; // int array for downsampled data
    
    // RS41 variables
    /// The number of RS41 samples which have been collected for
    /// sending as a TM
    int _n_rs41_samples = 0;
    /// Array to hold RS41 samples for the TM
    rs41TmSample_t _rs41_samples[RS41_N_SAMPLES_TO_REPORT];
    /// The current RS41 local file. We will be opening, appending, closing
    /// to this file. When not in flight mode, the string is set to empty.
    String _rs41_filename;
    /// The number of RS41 files samples which have been written to
    /// the current _rs41_file. It is used for cycling the RS41 file.
    int _rs41_file_n_samples = 0;
    /// The start time of the current RS41 collection cycle
    uint32_t _rs41_start_time = 0;

    // Actions
    ActionFlag_t action_flags[NUM_ACTIONS] = {{0}}; // initialize all flags to false
};
#endif /* STRATOLPC_H */
