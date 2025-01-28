/*
 *  Flight.cpp
 *  Author:  Alex St. Clair
 *  Created: June 2019
 *  Modified: Lars Kalnajs July 2019
 *  
 *  This file implements LPC flight mode.
 */

#include "StratoLPC.h"

enum FLStates_t : uint8_t {
    FL_ENTRY = MODE_ENTRY,
    
    // add any desired states between entry and shutdown
    FL_GPS_WAIT,
    FL_IDLE,
    FL_WARMUP,
    FL_FLUSH,
    FL_MEASURE,
    FL_SEND_TELEMETRY,
    FL_ERROR,
    FL_SHUTDOWN = MODE_SHUTDOWN,
    FL_EXIT = MODE_EXIT
};

// this function is called at the defined rate
//  * when flight mode is entered, it will start in FL_ENTRY state
//  * it is then up to this function to change state as needed by updating the inst_substate variable
//  * on each loop, whichever substate is set will be perfomed
//  * when the mode is changed by the Zephyr, FL_EXIT will automatically be set
//  * it is up to the FL_EXIT logic perform any actions for leaving flight mode
void StratoLPC::FlightMode()
{
    if (inst_substate == FL_ENTRY) {
        _rs41.init();
        log_nominal((String("RS41: ")+_rs41.banner()).c_str());
        rs41Start();
    } else {
        rs41Action();
    }
    switch (inst_substate) {
    case FL_ENTRY:
        // perform setup
        log_nominal("Entering FL");
        inst_substate = FL_GPS_WAIT;
        break;
    case FL_GPS_WAIT:
        // wait for a Zephyr GPS message to set the time before moving on
        log_debug("FL Wait for GPS Time");
        if (time_valid)
        //if(true)
        {
            // On the first call for flight mode we set the nexr warmup period to occur on the next
            // hour.   After that the measurements occur every x minutes after the hour
            StartTime = Get_Next_Hour(); // Get the next whole hour
            if (!OPC_IMMEDIATE_START) {
                scheduler.AddAction(START_WARMUP, StartTime);  //start the measurement on the next whole hour
            } else {
                scheduler.AddAction(START_WARMUP, 10); //For testing start in 10 seconds
            }
            inst_substate = FL_IDLE; // automatically go to idle
            log_nominal("Entering FL_IDLE");
        }
        break;
            
    case FL_IDLE:
        // some logic here to determine when to leave idle and go to FL_WARMUP, e.g.:
        if (CheckAction(START_WARMUP))
        {
            //ZephyrLogFine("Starting warmup");
            /* Set the instrument for warm up mode */
            StartTimeSeconds = now();
            Serial.print("StartTimeSeconds Updated to: ");
            Serial.println(StartTimeSeconds);
            digitalWrite(PHA_POWER, HIGH); //turn on the optical head
            if( OPC.MeasureLTC2983(4) < PumpMinTemp || OPC.MeasureLTC2983(6) < PumpMinTemp) //check pumps are above min temp
            {
                ZephyrLogWarn("Pump Temp too low");
                Serial.println("Shutting down LPC");
                LPC_Shutdown();
                Serial.print("Last Measurement at: ");
                Serial.println(StartTimeSeconds);
                TimeElements nextMeasurement;
                breakTime(StartTimeSeconds + (time_t)Set_cycleTime * 60l,nextMeasurement);
                scheduler.AddAction(START_WARMUP, nextMeasurement);
                Serial.print("Next Measurement schedueled for: ");
                Serial.print(nextMeasurement.Hour);
                Serial.print(":");
                Serial.print(nextMeasurement.Minute);
                Serial.print(":");
                Serial.println(nextMeasurement.Second);
                inst_substate = FL_IDLE;
                log_nominal("Entering FL_IDLE");
                break;
            }
        
            TempLaser = OPC.MeasureLTC2983(8);  // Laser temp on Ch 8: Thermistor 44006 10K@25C
            if ((TempLaser > -200) && (TempLaser < Set_LaserTemp))
                digitalWrite(HEATER1, HIGH);  //Laser heater on heater channel 1
            if (TempLaser > (Set_LaserTemp + DeadBand))
                digitalWrite(HEATER1, LOW);
            scheduler.AddAction(START_FLUSH, Set_warmUpTime);
            inst_substate = FL_WARMUP;
            log_nominal("Entering FL_WARMUP");
        }
        log_debug("FL Idle");
        break;
            
    case FL_WARMUP:
        if (CheckAction(START_FLUSH))
        {
            //ZephyrLogFine("Starting flush");

            digitalWrite(HEATER1, LOW); //turn off the laser heater
            //digitalWrite(MFS_PWR, HIGH);  //Turn on Mass Flow Sensor
            //Wire2.begin();//Activate  Bus I2C
            //digitalWrite(DCDC_PWR, HIGH); //Turn on DC-DC converter for pumps
            /* Turn on pumps in sequence */
            analogWrite(PUMP1_PWR, BEMF1_pwm);
            delay(200);
            analogWrite(PUMP2_PWR, BEMF2_pwm);
            OPCSERIAL.begin(500000);  //PHA serial speed = 0.5Mb
            delay(500);
            OPCSERIAL.setTimeout(2000); //Set the serial timout to 2s
            // See if the PHA needs to be configured
            phaConfig();
            scheduler.AddAction(START_MEASUREMENT, Set_FlushingTime);
            inst_substate = FL_FLUSH;
            log_nominal("Entering FL_FLUSH");
            
        }
        log_debug("FL Warmup");
        break;
    
    case FL_FLUSH:

        if (CheckAction(START_MEASUREMENT))
        {
            //ZephyrLogFine("Starting Measurement");

            inst_substate = FL_MEASURE;
            Frame = 0;
            OPCSERIAL.flush();
            log_nominal("Entering FL_MEASURE");
            MeasurementStartTime = now(); //record the time when we start to difference subsequent times from

        }
        log_debug("FL Flush");
        break;
            
    case FL_MEASURE:
                    
        if(OPCSERIAL.available())
        {
            inByte = 0;
            int indx = 0;
            unsigned long TimeOut = millis() + 1000; //set a timeout just in case
            
            while(inByte != '\n' && indx < PHA_BUFFER_SIZE) //Read the data byte by byte until we hit an EOL or timeout
            {
                if(OPCSERIAL.available())
                {
                    inByte = OPCSERIAL.read();
                    PHAArray[indx] = inByte;
                    indx++;
                }
                if(millis() > TimeOut)
                {
                    log_error("PHA Read Timeout");
                    break;
                }
            }
            log_debug("Received PHA Bytes: ");
            Serial.println(indx);
            
            if(inByte != '\n')  //if we exited due to a timeout
            {
                ErrorCount++;
                OPCSERIAL.flush();
            }
           
            else
            {
                /* Process the PHA Data */
                PHAArray[indx+1] ='\0'; //add a null after the data to end the string
                parsePHA(indx); //Parse the PHA data to int array
                fillBins(Frame,Set_samplesToAverage); //Downsample array into defined bins

                Serial.print("Pulse Count: ");
                Serial.println(PHA_PulseCount);
                
                /*Adjust the Pump Back EMF */
                AdjustPumps();
                /* Get the HK Data once for every averaged sample */
                if(Frame%Set_samplesToAverage == 0)
                {
                    log_debug("collecting HK");

                    Flow = getFlow();  //get flow from MFS
                    Serial.print("Flow: ");
                    Serial.println(Flow);
                    ReadHK(Frame/Set_samplesToAverage);  //read the HK and put in array (note integer division)
                    Serial.print("Pump1 T: ");
                    Serial.println(TempPump1);
                    Serial.print("Pump2 T: ");
                    Serial.println(TempPump2);
                    Serial.print("Inlet T: ");
                    Serial.println(TempInlet);
                    CheckTemps();

                }
                Frame++;  //increment the measurement frame counter
            }
        }
         
        if( Frame >= Set_numberSamples)
        {
            //ZephyrLogFine("Finished measurement");
            ErrorCount = 0;
            inst_substate = FL_SEND_TELEMETRY;
            log_nominal("Entering FL_SEND_TELEMETRY");

        }
        if(ErrorCount > 100)
        {
            ZephyrLogCrit("Measurment errored out");
            ErrorCount = 0;
            inst_substate = FL_ERROR;
        }
        
        log_debug("FL Measure");
        break;
            
    case FL_SEND_TELEMETRY:
        Serial.println("Shutting down LPC");
        LPC_Shutdown();
        PackageTelemetry(Frame/Set_samplesToAverage);
        Frame = 0;
        Serial.print("Last Measurement at: ");
        Serial.println(StartTimeSeconds);
        TimeElements nextMeasurement;
        breakTime(StartTimeSeconds + (time_t)Set_cycleTime * 60l,nextMeasurement);
        scheduler.AddAction(START_WARMUP, nextMeasurement);
        Serial.print("Next Measurement schedueled for: ");
        Serial.print(nextMeasurement.Hour);
        Serial.print(":");
        Serial.print(nextMeasurement.Minute);
        Serial.print(":");
        Serial.println(nextMeasurement.Second);
        inst_substate = FL_IDLE;
        log_nominal("Entering FL_IDLE");
        break;
            
    case FL_ERROR:
        // generic error state for flight mode to go to if any error is detected
        // this state can make sure the ground is informed, and wait for ground intervention
        LPC_Shutdown();
        log_debug("In Error Sub State");
        break;
    case FL_SHUTDOWN:
        LPC_Shutdown();
        log_nominal("Shutdown warning received in FL");
        break;
    case FL_EXIT:
        LPC_Shutdown();
        _rs41.pwr_off();
        _rs41_filename = "";
        _rs41_file_n_samples = 0;
        log_nominal("Exiting FL");
        break;
    default:
        // todo: throw error
        log_error("Unknown substate in FL");
        inst_substate = FL_ENTRY; // reset
        break;
    }
}
