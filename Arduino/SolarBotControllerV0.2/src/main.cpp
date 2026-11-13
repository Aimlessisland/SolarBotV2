#include <Arduino.h>

/**
 * @file main.cpp
 * @brief Non-blocking, time-sliced motion control layer for vehicle architecture.
 * @details Interfaces with hardware drivers and handshakes with the Q6A AI board.
 */

#include "config/configuration.h"
#include "pins/pin_config.h"
#include "module/motion.h"
#include "SerialHandler/serialReader.h"
#include "module/BTS7960.h"

unsigned long lastThread0 = 0;
const unsigned long intervalThread0 = 1;  // Run every 1ms (fast task)

unsigned long lastThread1 = 0;
const unsigned long intervalThread1 = 2; // Run every 2ms (slower task)


void thread0(){
 //Need emergency stop here
}

void thread1(){
  cmdHandler();
  updateMotion();
}

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  initPins();
}

void loop() {
unsigned long currentMillis = millis();

  // Time slice for Thread 0
  if (currentMillis - lastThread0 >= intervalThread0) {
    lastThread0 = currentMillis;
    thread0();
  }

  // Time slice for Thread
  if (currentMillis - lastThread1 >= intervalThread1) {
    lastThread1 = currentMillis;
    thread1();
  }
}
