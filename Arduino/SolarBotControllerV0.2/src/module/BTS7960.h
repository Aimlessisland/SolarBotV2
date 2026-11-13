#ifndef BTS7960_H
#define BTS7960_H

/**
 * @file BTS7960.h
 * @brief Non-blocking, time-sliced motion control layer for vehicle architecture.
 * @details Interfaces with hardware drivers and handshakes with the Q6A AI board.
 */

#include <Arduino.h>
#include "config/configuration.h"

// ============================================================================
// @section Move Forward
// ============================================================================

void moveBTS7960forward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, PWM);
    analogWrite(RightPin, 0);
}

// ============================================================================
// @section Move Backward 
// ============================================================================

void moveBTS7960backward(int LeftPin, int RightPin, int PWM){
    analogWrite(LeftPin, 0);
    analogWrite(RightPin, PWM);
}

#endif