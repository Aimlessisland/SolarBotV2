#ifndef IRFB3306_H
#define IRFB3306_H

/**
 * @file irfb3306.h
 * @brief Simple MOSFET driver functions for motor/peripheral control.
 * 
 * ============================================================================
 * IRFB3306 MOSFET QUICK SPECS
 * ============================================================================
 * - Type:             N-Channel Power MOSFET
 * - Package:          TO-220AB
 * - Max Voltage (Vds): 60V
 * - Max Current (Id): 160A (Silicon limit) / 120A (Package limit)
 * - Resistance (Rds): 0.0033 Ohms (3.3 mΩ) - runs super cold
 * - Gate Trigger:     2V - 4V (Turns full ON with Arduino 5V pin)
 * 
 * PINOUT (Looking at the front label with pins pointing down):
 *      [   TAB  ] -> Metal tab is tied to DRAIN (Pin 2)
 *      +--------+
 *      |3306PbF |
 *      +--------+
 *       |  |  |
 *       1  2  3
 *      [G][D][S]
 * 
 *   - Pin 1 (GATE):   Arduino PWM/Digital Pin (use 100-220Ω resistor)
 *   - Pin 2 (DRAIN):  Connect to Motor/Load NEGATIVE (-)
 *   - Pin 3 (SOURCE): Connect to GND
 * ============================================================================
 */

#include <Arduino.h>
#include "config/configuration.h"

// ============================================================================
// @section Dual-Pin Motor Control (Matches TIP42 Base)
// ============================================================================

void moveIRFB3306forward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 0);
}

void moveIRFB3306backward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 255);
}

void stopIRFB3306(int LeftPin, int RightPin){
    analogWrite(LeftPin, 0);
    analogWrite(RightPin, 0);
}

// ============================================================================
// @section Single-Pin Peripheral Control (Brush Motor / Pump)
// ============================================================================

void setIRFB3306(int pin, int PWM){
    analogWrite(pin, PWM);
}

void turnOffIRFB3306(int pin){
    analogWrite(pin, 0);
}

#endif // IRFB3306_H