#ifndef MOTION_H
#define MOTION_H

/**
 * ============================================================================
 * @file    motion.h
 * @brief   Non-blocking Differential Drive & Accel/Decel Motion Controller
 * ============================================================================
 * @details Handles real-time non-blocking motor pulses driven by the 2ms
 *          time-slicing scheduler in main.cpp without introducing loop
 *          latency or blocking delays.
 * 
 *  EXECUTION ORDER: RIGHT TRACK FIRST -> LEFT TRACK SECOND
 *  ---------------------------------------------------------------------------
 *  - All dual-track commands (start, PWM update, and halt) write the Right
 *    track pins first, followed immediately by the Left track pins.
 * 
 *  CONDITIONAL ACCEL / DECEL PROFILE (LONG MOVES ONLY):
 *  ---------------------------------------------------------------------------
 *  - Short Commands (<= 150 ticks) : Instant full PWM (snappy tracking steps).
 *  - Long Commands  (>  150 ticks) :
 *      1. Accelerate : Starts at START_PWM_SPEED, adds +20 PWM every 15 ticks.
 *      2. Cruise     : Holds RIGHT_PWM_SPEED / LEFT_PWM_SPEED.
 *      3. Decelerate : Subtracts -20 PWM every 15 ticks during final 120 ticks.
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

#define MIN_ACCEL_TICKS     150  // M1 100 stays instant; M1 200+ uses accel/decel
#define START_PWM_SPEED     20   // Starting & ending PWM speed during wind-up/down
#define PWM_STEP_SIZE       20   // Add or subtract 20 PWM points each step
#define PWM_STEP_TICKS      15   // Change every 15 ticks (30ms per step at 2ms slice)
#define DECEL_REMAIN_TICKS  120  // Start slowing down 120 ticks (~240ms) before stop

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
    static int  currentRightPwm  = 0;
    static int  currentLeftPwm   = 0;
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

void moveRightTrackForward(){
    #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42forward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #endif
}

/**
 * @brief Triggers non-blocking forward motion for a specified tick duration.
 * @param amount Number of 2ms time slices (ticks) to execute the movement.
 */
void moveLeftTrackForward(){
    #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42forward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #endif
}

void moveRightTrackBackward(){
    #if RIGHT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #elif RIGHT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42backward(RIGHT_LPWM_PIN, RIGHT_RPWM_PIN, RIGHT_PWM_SPEED);
    #endif
}

void moveLeftTrackBackward(){
    #if LEFT_MOTOR_DRIVER == DRIVER_BTS7960
        moveBTS7960backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #elif LEFT_MOTOR_DRIVER == DRIVER_CUSTOM_RELAY
        moveTIP42backward(LEFT_LPWM_PIN, LEFT_RPWM_PIN, LEFT_PWM_SPEED);
    #endif
}

// ============================================================================
// @section Accel/Decel Helpers (Right Track First -> Left Track Second)
// ============================================================================

#ifdef ENABLE_ACCEL_DECEL
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

void applyAccelDecelOutput(){
    if      (motionMode == 1) { writeRightPwm(true);  writeLeftPwm(true);  } // M1 Forward (Right -> Left)
    else if (motionMode == 2) { writeRightPwm(false); writeLeftPwm(false); } // M2 Backward (Right -> Left)
    else if (motionMode == 3) { writeRightPwm(true);  }                      // M3 Curve Left
    else if (motionMode == 4) { writeLeftPwm(true);   }                      // M4 Curve Right
    else if (motionMode == 5) { writeRightPwm(true);  writeLeftPwm(false); } // M5 Rotate Left (Right -> Left)
    else if (motionMode == 6) { writeRightPwm(false); writeLeftPwm(true);  } // M6 Rotate Right (Right -> Left)
    else if (motionMode == 7) { writeRightPwm(false); }                      // Curve Left Back
    else if (motionMode == 8) { writeLeftPwm(false);  }                      // Curve Right Back
}

void updateAccelDecel(){
    stepTickCounter++;
    if (stepTickCounter < PWM_STEP_TICKS) return; // Wait until PWM_STEP_TICKS pass
    stepTickCounter = 0;

    if (remainingTicks > DECEL_REMAIN_TICKS) {
        // Acceleration Phase (+20 PWM per step up to target speed: Right -> Left)
        if (currentRightPwm < RIGHT_PWM_SPEED) {
            currentRightPwm += PWM_STEP_SIZE;
            if (currentRightPwm > RIGHT_PWM_SPEED) currentRightPwm = RIGHT_PWM_SPEED;
        }
        if (currentLeftPwm < LEFT_PWM_SPEED) {
            currentLeftPwm += PWM_STEP_SIZE;
            if (currentLeftPwm > LEFT_PWM_SPEED) currentLeftPwm = LEFT_PWM_SPEED;
        }
    } else {
        // Deceleration Phase (-20 PWM per step down to START_PWM_SPEED: Right -> Left)
        if (currentRightPwm > START_PWM_SPEED) {
            currentRightPwm -= PWM_STEP_SIZE;
            if (currentRightPwm < START_PWM_SPEED) currentRightPwm = START_PWM_SPEED;
        }
        if (currentLeftPwm > START_PWM_SPEED) {
            currentLeftPwm -= PWM_STEP_SIZE;
            if (currentLeftPwm < START_PWM_SPEED) currentLeftPwm = START_PWM_SPEED;
        }
    }

    applyAccelDecelOutput();
}
#endif

// ============================================================================
// @section High-Level Motion Primitives (M1 - M6 | Right -> Left Execution)
// ============================================================================

void moveForward(int amount){
    Serial.println("Move Forward");
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 1;
            stepTickCounter = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackForward();
    moveLeftTrackForward();
}

void moveBackward(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 2;
            stepTickCounter = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackBackward();
    moveLeftTrackBackward();
}

void curveLeft(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 3;
            stepTickCounter = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = 0;
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
            currentRightPwm = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
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
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackForward();
    moveLeftTrackBackward();
}

void rotateRight(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 6;
            stepTickCounter = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = (LEFT_PWM_SPEED  > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveRightTrackBackward();
    moveLeftTrackForward();
}

void curveLeftBack(int amount){
    remainingTicks = amount;

    #ifdef ENABLE_ACCEL_DECEL
        if (amount > MIN_ACCEL_TICKS) {
            useAccelDecel   = true;
            motionMode      = 7;
            stepTickCounter = 0;
            currentRightPwm = (RIGHT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : RIGHT_PWM_SPEED;
            currentLeftPwm  = 0;
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
            currentRightPwm = 0;
            currentLeftPwm  = (LEFT_PWM_SPEED > START_PWM_SPEED) ? START_PWM_SPEED : LEFT_PWM_SPEED;
            applyAccelDecelOutput();
            return;
        }
        useAccelDecel = false;
    #endif

    moveLeftTrackBackward();
}

// ============================================================================
// @section Emergency Stop & Hard Brake (Right -> Left Cutoff)
// ============================================================================

void halt(){
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);

    #ifdef ENABLE_ACCEL_DECEL
        useAccelDecel   = false;
        motionMode      = 0;
        stepTickCounter = 0;
        currentRightPwm = 0;
        currentLeftPwm  = 0;
    #endif
}

//--------------------------------------------------------------------------
// Execution Phase: Fire up motor outputs and initialize tick counter
//--------------------------------------------------------------------------
void updateMotion(){
    if (remainingTicks > 0) {
        remainingTicks--; // Decrement by 1 every 2ms tick
        //Serial.println(remainingTicks);

        #ifdef ENABLE_ACCEL_DECEL
            if (useAccelDecel && remainingTicks > 0) {
                updateAccelDecel();
            }
        #endif

        if (remainingTicks == 0) {
            halt(); // Time's up! Stop Right first, then Left immediately.
            Serial.println("ok"); //OK when something is done so Q6A can get that feedback
        }
    }
}

//--------------------------------------------------------------------------
// Default Pin State : Set every Pin back to 0. This will stop ghosting problem
//--------------------------------------------------------------------------
#endif