#ifndef TIP42_H
#define TIP42_H

/**
 * ============================================================================
 * @file    TIP42.h
 * @brief   PNP Power BJT Actuator Driver Module
 * ============================================================================
 * 
 *  COMPONENT SPECIFICATIONS (TIP42 / TIP42C PNP Power Transistor):
 *  ---------------------------------------------------------------------------
 *  - Transistor Type:       PNP Epitaxial-Base Silicon Power Transistor
 *  - Package:               TO-220
 *  - Max Collector-Emitter: V_CEO = -40V (TIP42), -60V (TIP42A), -100V (TIP42C)
 *  - Continuous Collector:  I_C   = -6.0 A
 *  - Peak Collector Curr:   I_CM  = -10.0 A
 *  - Base Current Max:      I_B   = -2.0 A
 *  - Total Power Diss:      P_D   = 65 W @ Case Temp 25°C
 *  - DC Current Gain (hFE): 15 to 75 (typically ~30 @ 3A)
 * 
 *  PIN CONFIGURATION (TO-220 Facing Front Label):
 *  ---------------------------------------------------------------------------
 *       +-------------------+
 *       |     [ TAB / C ]   |  Metal tab is internally tied to COLLECTOR (Pin 2)
 *       +-------------------+
 *       |     TIP42C        |
 *       |                   |
 *       +-------------------+
 *         |     |     |
 *         1     2     3
 *       BASE  COLLECTOR EMITTER
 *        (B)     (C)      (E)
 * 
 *  WHY AN NPN PRE-DRIVER IS NEEDED (NPN + PNP HIGH-SIDE DRIVE):
 *  ---------------------------------------------------------------------------
 *  1. TIP42 is a PNP transistor. It turns ON when Base voltage is pulled LOWER
 *     than Emitter (V_BE < -0.7V).
 *  2. If the motor/load runs on 12V or 24V, the TIP42 Emitter is at 12V/24V.
 *     An Arduino pin only outputs 0V or 5V. Even at 5V, the Base is 7V lower than
 *     12V, so the PNP would NEVER turn off and would fry the Arduino pin!
 *  3. Solution: Use a small NPN transistor (2N2222, 2N3904, or BC547) as the driver:
 *
 *     [Arduino Pin] ---> [1kΩ Resistor] ---> [NPN Base]
 *     [NPN Emitter] ---> GND
 *     [NPN Collector] -> Connected to [TIP42 Base] through a 470Ω - 1kΩ resistor
 *     [TIP42 Emitter] -> +12V / Battery Power
 *     [TIP42 Collector] -> To Motor / Load Positive (+)
 *     [10kΩ Pull-Up]  -> Between TIP42 Base and +12V (keeps PNP off when idling)
 * 
 *  LOGIC BEHAVIOR WITH NPN IN PLACE:
 *  ---------------------------------------------------------------------------
 *  - Arduino Pin HIGH (5V) -> NPN turns ON -> Pulls TIP42 Base LOW -> Motor ON
 *  - Arduino Pin LOW  (0V) -> NPN turns OFF -> 10k pull-up holds Base at 12V -> Motor OFF
 * ============================================================================
 */

#include <Arduino.h>
#include "config/configuration.h"

// ============================================================================
// @section Move Forward
// ============================================================================

void moveTIP42forward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 0);
}

// ============================================================================
// @section Move Backward
// ============================================================================

void moveTIP42backward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 255);
}

#endif