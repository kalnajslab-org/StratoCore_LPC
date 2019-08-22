/*
 *  LowPower.cpp
 *  Author:  Alex St. Clair
 *  Created: June 2019
 *  Modified: Lars Kalnajs July 2019
 *  
 *  This file implements LPC low power mode.
 */

#include "StratoLPC.h"

enum LPStates_t : uint8_t {
    LP_ENTRY = MODE_ENTRY,
    
    // add any desired states between entry and shutdown
    LP_LOOP,
    
    LP_SHUTDOWN = MODE_SHUTDOWN,
    LP_EXIT = MODE_EXIT
};

void StratoLPC::LowPowerMode()
{
    switch (inst_substate) {
    case LP_ENTRY:
        // perform setup
        log_nominal("Entering LP");
        LPC_Shutdown();
        inst_substate = LP_LOOP;
        break;
    case LP_LOOP:
        // nominal ops
        log_debug("LP loop");
        break;
    case LP_SHUTDOWN:
        // prep for shutdown
        LPC_Shutdown();
        log_nominal("Shutdown warning received in LP");
        break;
    case LP_EXIT:
        // perform cleanup
        log_nominal("Exiting LP");
        break;
    default:
        // todo: throw error
        log_error("Unknown substate in LP");
        inst_substate = LP_ENTRY; // reset
        break;
    }
}
