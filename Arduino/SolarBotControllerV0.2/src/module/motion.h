#ifndef MOTION_H
#define MOTION_H

/**
 * ============================================================================
 * @file    motion.h
 * @brief   Non-blocking Differential Drive & Accel/Decel Motion Controller
 * ============================================================================
 * @details Handles real-time non-blocking motor pulses driven by the 2ms
 *          time-slicing scheduler in main.cpp without introducing loop
 *          latency or blocking delays[cite: 2].
 * 
 *  CONDITIONAL ACCEL / DECEL PROFILE (LONG MOVES ONLY):
 *  ---------------------------------------------------------------------------
 *  - Short Commands (<= 200 ticks) : Instant full PWM (snappy tracking steps).
 *  - Long Commands  (>  200 ticks) :
 *      1. Accelerate : Starts at START_PWM_SPEED, adds +20 PWM every 4 ticks.
 *      2. Cruise     : Holds LEFT_PWM_SPEED / RIGHT_PWM_SPEED.
 *      3. Decelerate : Subtracts -20 PWM every 4 ticks during final 32 ticks.
 * ============================================================================
 */

#include <Arduino.h>
#include "pins/pin_config.h"
#include "BTS7960.h"
#include "TIP42.h"

// ============================================================================
// @section Motion Tuning & Accel/Decel Configuration (Marlin-Style)
// ============================================================================

/**
 * Conditional Acceleration & Deceleration
 * Comment out (//#define) to disable completely and always use instant PWM.
 */
#define ENABLE_ACCEL_DECEL

#define MIN_ACCEL_TICKS     200  // Only activate accel/decel when command > 200 ticks
#define START_PWM_SPEED     60   // Starting & ending PWM speed during wind-up/down
#define PWM_STEP_SIZE       20   // Add or subtract 20 PWM points each step
#define PWM_STEP_TICKS      4    // Change PWM every 4 ticks (try 2 for faster, 4 for slower)
#define DECEL_REMAIN_TICKS  32   // Begin decelerating when 32 ticks remain

// ============================================================================
// @section State Variables & Timers
// ============================================================================

int remainingTicks = 0;

static int LEFT_PWM_SPEED  = DEFAULT_LEFT_PWM_SPEED;
static int RIGHT_PWM_SPEED = DEFAULT_RIGHT_PWM_SPEED; 

#ifdef ENABLE_ACCEL_DECEL
    static bool useAccelDecel    = false;
    static int  motionMode       = 0;
    static int  stepTickCounter  = 0;
    static int  currentLeftPwm   = 0;
    static int  currentRightPwm  = 0;
#endif

void setLeftPwmSpeed(int value) {
    LEFT_PWM_SPEED = value;
}

void setRightPwmSpeed(int value) {
    RIGHT_PWM_SPEED = value;
}

// ============================================================================
// @section Low-Level Track Hardware Wrappers (Untouched Signatures)
// ============================================================================

/**
 * @brief Triggers non-blocking forward motion for a specified tick duration.
 * @param amount Number of 2ms time slices (ticks) to execute the movement[cite: 2].
 */
void moveLeftTrackForward(){
    #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #endif
}

void moveRightTrackForward(){
    #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #endif
}

void moveLeftTrackBackward(){
    #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #endif
}

void moveRightTrackBackward(){
    #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #endif
}

// ============================================================================
// @section Accel/Decel Helpers (Active Only When Command > MIN_ACCEL_TICKS)
// ============================================================================

#ifdef ENABLE_ACCEL_DECEL
void writeLeftPwm(bool forward){
    if (forward) {
        #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
            moveBTS7960forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, currentLeftPwm);
        #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
            moveTIP42forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, currentLeftPwm);
        #endif
    } else {
        #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
            moveBTS7960backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, currentLeftPwm);
        #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
            moveTIP42backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, currentLeftPwm);
        #endif
    }
}

void writeRightPwm(bool forward){
    if (forward) {
        #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
            moveBTS7960forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, currentRightPwm);
        #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
            moveTIP42forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, currentRightPwm);
        #endif
    } else {
        #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
            moveBTS7960backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, currentRightPwm);
        #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
            moveTIP42backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, currentRightPwm);
        #endif
    }
}

void applyAccelDecelOutput(){
    if      (motionMode == 1) { writeLeftPwm(true);  writeRightPwm(true);  } // M1 Forward[cite: 2]
    else if (motionMode == 2) { writeLeftPwm(false); writeRightPwm(false); } // M2 Backward[cite: 2]
    else if (motionMode == 3) { writeRightPwm(true);  }                      // M3 Curve Left[cite: 2]
    else if (motionMode == 4) { writeLeftPwm(true);   }                      // M4 Curve Right[cite: 2]
    else if (motionMode == 5) { writeLeftPwm(false); writeRightPwm(true);  } // M5 Rotate Left[cite: 2]
    else if (motionMode == 6) { writeLeftPwm(true);  writeRightPwm(false); } // M6 Rotate Right[cite: 2]
    else if (motionMode == 7) { writeRightPwm(false); }                      // Curve Left Back
    else if (motionMode == 8) { writeLeftPwm(false);  }                      // Curve Right Back
}

void updateAccelDecel(){
    stepTickCounter++;
    if (stepTickCounter < PWM_STEP_TICKS) return; // Wait until 2 or 4 ticks pass
    stepTickCounter = 0;

    if (remainingTicks > DECEL_REMAIN_TICKS) {
        // Acceleration Phase (+20 PWM per step up to target speed)
        if (currentLeftPwm < LEFT_PWM_SPEED) {
            currentLeftPwm += PWM_STEP_SIZE;
            if (currentLeftPwm > LEFT_PWM_SPEED) currentLeftPwm = LEFT_PWM_SPEED;
        }
        if (currentRightPwm < RIGHT_PWM_SPEED) {
            currentRightPwm += PWM_STEP_SIZE;
            if (currentRightPwm > RIGHT_PWM_SPEED) currentRightPwm = RIGHT_PWM_SPEED;
        }
    } else {
        // Deceleration Phase (-20 PWM per step down to START_PWM_SPEED)
        if (currentLeftPwm > START_PWM_SPEED) {
            currentLeftPwm -= PWM_STEP_SIZE;
            if (currentLeftPwm < START_PWM_SPEED) currentLeftPwm = START_PWM_SPEED;
        }
        if (currentRightPwm > START_PWM_SPEED) {
            currentRightPwm -= PWM_STEP_SIZE;
            if (currentRightPwm < START_PWM_SPEED) currentRightPwm = START_PWM_SPEED;
        }
    }

    applyAccelDecelOutput();
}
#endif

// ============================================================================
// @section High-Level Motion Primitives (M1 - M6)
// ============================================================================

void moveForward(int amount){
    Serial.println("Move Forward");
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 1;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackForward();
    moveRightTrackForward();
}

void moveBackward(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 2;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackBackward();
    moveRightTrackBackward();
}

void curveLeft(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 3;
            stepTickCounter = 0;
            currentLeftPwm  = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackForward();
}

void curveRight(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 4;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = 0;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackForward();
}

void rotateLeft(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 5;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackBackward();
    moveRightTrackForward();
}

void rotateRight(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 6;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackForward();
    moveRightTrackBackward();
}

void curveLeftBack(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 7;
            stepTickCounter = 0;
            currentLeftPwm  = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackBackward();
}

void curveRightBack(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 8;
            stepTickCounter = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            currentRightPwm = 0;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackBackward();
}

// ============================================================================
// @section Emergency Stop & Hard Brake
// ============================================================================

void halt(){
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);

    #ifdef ENABLE_ACCEL_DECEL
        useAccelDecel   = false;
        motionMode      = 0;
        stepTickCounter = 0;
        currentLeftPwm  = 0;
        currentRightPwm = 0;
    #endif
}

//--------------------------------------------------------------------------
// Execution Phase: Fire up motor outputs and initialize tick counter
//--------------------------------------------------------------------------
void updateMotion(){
    if (remainingTicks > 0) {
        remainingTicks--; // Decrement by 1 every 2ms tick[cite: 2]
        //Serial.println(remainingTicks);

        #ifdef ENABLE_ACCEL_DECEL
            if (useAccelDecel && remainingTicks > 0) {
                updateAccelDecel();
            }
        #endif

        if (remainingTicks == 0) {
            halt(); // Time's up! Stop all motors immediately.
            Serial.println("ok"); //OK when something is done so Q6A can get that feedback
        }
    }
}

//--------------------------------------------------------------------------
// Default Pin State : Set every Pins back to 0. This will stop ghosting problem
//--------------------------------------------------------------------------
#endif