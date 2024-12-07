/*  StratoCore_LPC.ino
 *  Author: Alex St. Clair
 *  Created: June 2019
 * 
 *  Test Arduino script for StratoCore development
 *  
 *  This test assumes LPC hardware
 */

#include "src/StratoLPC.h"
#include <TimerOne.h>

#define LOOP_TENTHS     5 // defines loop period in 0.1s

StratoLPC strato;

// timer control variables
volatile uint8_t timer_counter = 0;
volatile bool loop_flag = false;
 // Serial Buffers for T4.1
uint8_t Zephyr_serial_TX_buffer[ZEPHYR_SERIAL_BUFFER_SIZE];
uint8_t Zephyr_serial_RX_buffer[ZEPHYR_SERIAL_BUFFER_SIZE];
// ISR for Zephyr port (on LPC)
// void serialEvent2()
// {
//   if (ZEPHYR_SERIAL.available()) {
//     while (ZEPHYR_SERIAL.available()) {
//       uint8_t rx_char;
//       rx_char = ZEPHYR_SERIAL.read();
//       strato.TakeZephyrByte(rx_char);
//     }
//   }
// }

// ISR for timer
void ControlLoopTimer(void) {
  if (++timer_counter == LOOP_TENTHS) {
    timer_counter = 0;
    loop_flag = true;
  }
}

// Loop timing function
void WaitForControlTimer(void) {
  while (!loop_flag) delay(1);

  loop_flag = false;
}

// Standard Arduino setup function
void setup()
{
  Serial.begin(115200);
  Serial.print("StratoCore_LPC build ");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.println(__TIME__);

  ZEPHYR_SERIAL.begin(115200);

#if (ZEPHYR_COMMS_ON_DEBUG_PORT)
    log_error("Configured for sending Zephyr msgs to debug port\n**** WILL NOT WORK FOR FLIGHT OPERATIONS!");
#else
    //Increase serial buffer sizes for Teensy 4.1
    ZEPHYR_SERIAL.addMemoryForRead(&Zephyr_serial_RX_buffer, sizeof(Zephyr_serial_RX_buffer));
    ZEPHYR_SERIAL.addMemoryForWrite(&Zephyr_serial_TX_buffer, sizeof(Zephyr_serial_TX_buffer));
    log_nominal("Configured for standard Zephyr port");
#endif

  // Timer interrupt setup for main loop timing
  Timer1.initialize(100000); // 0.1 s
  Timer1.attachInterrupt(ControlLoopTimer);

  // Wait two cycles to align timing
  WaitForControlTimer();
  WaitForControlTimer();

  strato.InitializeCore();
  strato.InstrumentSetup();
}

// Standard Arduino loop function
void loop()
{
  // StratoCore loop functions
  strato.KickWatchdog();
  strato.RunScheduler();
  strato.RunRouter();
  strato.RunMode();
  strato.InstrumentLoop();

  // Wait for loop timer
  WaitForControlTimer();
}

