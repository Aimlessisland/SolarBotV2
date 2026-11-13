#ifndef TIP120_H
#define TIP120_H

/**
 * ============================================================================
 * @file    TIP120.h
 * @brief   NPN Darlington Actuator Driver (Water Pump & Brush Motor)
 * ============================================================================
 * 
 *  COMPONENT SPECIFICATIONS (TIP120 NPN Darlington Power Transistor):
 *  ---------------------------------------------------------------------------
 *  - Transistor Type:       NPN Darlington BJT (High Gain)
 *  - Package:               TO-220
 *  - Max Voltage (V_CEO):   60V
 *  - Continuous Current:    5.0 A (Peak: 8.0 A)
 *  - Base Trigger Resistor: 1kΩ (between Arduino Pin and Pin 1 Base)
 *  - Current Gain (hFE):    1000 (Turns fully ON with tiny Arduino current)
 * 
 *  PIN CONFIGURATION (TO-220 Facing Front Label):
 *  ---------------------------------------------------------------------------
 *       +-------------------+
 *       |     [ TAB / C ]   |  Metal tab is internally tied to COLLECTOR (Pin 2)
 *       +-------------------+
 *       |     TIP120        |
 *       |                   |
 *       +-------------------+
 *         |     |     |
 *         1     2     3
 *       BASE  COLLECTOR EMITTER
 *        (B)     (C)      (E)
 * 
 *  WIRING (LOW-SIDE SWITCH FOR PUMP & BRUSH):
 *  ---------------------------------------------------------------------------
 *  - Pin 1 (BASE):      Arduino Pin ---> [ 1kΩ Resistor ] ---> Base Pin 1
 *  - Pin 2 (COLLECTOR): Wire to Pump / Brush NEGATIVE (-) wire
 *  - Pin 3 (EMITTER):   Wire directly to System GND
 *  - Pump / Brush (+):  Wire directly to +12V / Battery Positive
 * 
 *  *SAFETY: Put a 1N4007 diode across pump/brush (+) and (-) terminals
 *           (Cathode stripe to +12V, Anode to Collector) to kill flyback spikes!
 * ============================================================================
 */

#include <Arduino.h>
#include "config/configuration.h"

// ============================================================================
// @section Single-Pin Actuator Controls (Water Pump / Brush Motor)
// ============================================================================

// Turn on with speed (0 = OFF, 255 = Full Speed)
void setTIP120(int pin, int PWM) {
    analogWrite(pin, PWM);
}

// Stop motor/pump immediately
void stopTIP120(int pin) {
    analogWrite(pin, 0);
}

// Full blast ON
void turnOnTIP120(int pin) {
    digitalWrite(pin, HIGH);
}

// ============================================================================
// @section Dual-Pin Motor (If using two TIP120s for direction)
// ============================================================================

void moveTIP120forward(int LeftPin, int RightPin, int PWM) {
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 0);
}

void moveTIP120backward(int LeftPin, int RightPin, int PWM) {
    analogWrite(LeftPin, 0);
    analogWrite(RightPin, PWM);
}

#endif // TIP120_H