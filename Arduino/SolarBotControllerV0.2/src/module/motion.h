#ifndef MOTION_H
#define MOTION_H

/**
 * ============================================================================
 * @file    motion.h
 * @brief   Non-blocking Differential Drive & Split Accel/Decel Controller
 * ============================================================================
 * @details Handles real-time non-blocking motor pulses driven by the 2ms
 *          time-slicing scheduler in main.cpp without blocking delays[cite: 2].
 * 
 *  INDEPENDENT LEFT vs. RIGHT ACCEL / DECEL (DRIVER MISMATCH COMPENSATION):
 *  ---------------------------------------------------------------------------
 *  - Left Track  (BTS7960 H-Bridge) : Active braking snaps hard on fast cutoff[cite: 2].
 *                                     Uses earlier, gentler deceleration to
 *                                     ease off smoothly.
 *  - Right Track (IRFB3306 + Relay) : Natural turn-off lag at stop[cite: 2].
 *                                     Uses later, faster deceleration so both
 *                                     tracks finish stopping together.
 * ============================================================================
 */

#include <Arduino.h>
#include "pins/pin_config.h"
#include "BTS7960.h"
#include "TIP42.h"

// ============================================================================
// @section Motion Tuning & Split Accel/Decel Configuration (Marlin-Style)
// ============================================================================

/**
 * Master Toggle for Conditional Acceleration & Deceleration
 * Comment out (//#define) to disable ramping and run instant full PWM.
 */
#define ENABLE_ACCEL_DECEL

#define MIN_ACCEL_TICKS     150  // Only use accel/decel when command > 150 ticks
#define PWM_STEP_TICKS      10   // Update PWM every 10 ticks (20ms at 2ms slice)[cite: 2]

// --- LEFT TRACK TUNING (BTS7960 43A - Gentle, Early Fade-Out) ---
#define LEFT_START_PWM      20   // Lower starting PWM so Left launches softer (was 30)
#define LEFT_ACCEL_STEP     8    // +8 PWM per step instead of +20 (2.5x slower wind-up)
#define LEFT_DECEL_STEP     10   // -10 PWM per step (smaller = slower, softer off)
#define LEFT_DECEL_TICKS    140  // Start slowing Left track 140 ticks (~280ms) before 0[cite: 2]

// --- RIGHT TRACK TUNING (IRFB3306 + Relay - Slightly Earlier Cutoff) ---
#define RIGHT_START_PWM     30   // Keep at 30 so your forward launch stays identical
#define RIGHT_ACCEL_STEP    20   // +20 PWM per step during acceleration
#define RIGHT_DECEL_STEP    25   // -25 PWM per step (drops PWM quickly)
#define RIGHT_DECEL_TICKS   125  // Increased from 110 -> ~30ms earlier right slowdown

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
// @section Split Left/Right Accel & Decel Helpers
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
    if      (motionMode == 1) { writeLeftPwm(true);  writeRightPwm(true);  } // M1 Forward[cite: 3]
    else if (motionMode == 2) { writeLeftPwm(false); writeRightPwm(false); } // M2 Backward[cite: 3]
    else if (motionMode == 3) { writeRightPwm(true);  }                      // M3 Curve Left[cite: 3]
    else if (motionMode == 4) { writeLeftPwm(true);   }                      // M4 Curve Right[cite: 3]
    else if (motionMode == 5) { writeLeftPwm(false); writeRightPwm(true);  } // M5 Rotate Left[cite: 3]
    else if (motionMode == 6) { writeLeftPwm(true);  writeRightPwm(false); } // M6 Rotate Right[cite: 3]
    else if (motionMode == 7) { writeRightPwm(false); }                      // Curve Left Back[cite: 3]
    else if (motionMode == 8) { writeLeftPwm(false);  }                      // Curve Right Back[cite: 3]
}

void updateAccelDecel(){
    stepTickCounter++;
    if (stepTickCounter < PWM_STEP_TICKS) return;
    stepTickCounter = 0;

    // ------------------------------------------------------------------------
    // 1. LEFT TRACK (BTS7960) Independent Accel / Decel
    // ------------------------------------------------------------------------
    if (remainingTicks > LEFT_DECEL_TICKS) {
        if (currentLeftPwm < LEFT_PWM_SPEED) {
            currentLeftPwm += LEFT_ACCEL_STEP;
            if (currentLeftPwm > LEFT_PWM_SPEED) currentLeftPwm = LEFT_PWM_SPEED;
        }
    } else {
        if (currentLeftPwm > LEFT_START_PWM) {
            currentLeftPwm -= LEFT_DECEL_STEP;
            if (currentLeftPwm < LEFT_START_PWM) currentLeftPwm = LEFT_START_PWM;
        }
    }

    // ------------------------------------------------------------------------
    // 2. RIGHT TRACK (IRFB3306) Independent Accel / Decel
    // ------------------------------------------------------------------------
    if (remainingTicks > RIGHT_DECEL_TICKS) {
        if (currentRightPwm < RIGHT_PWM_SPEED) {
            currentRightPwm += RIGHT_ACCEL_STEP;
            if (currentRightPwm > RIGHT_PWM_SPEED) currentRightPwm = RIGHT_PWM_SPEED;
        }
    } else {
        if (currentRightPwm > 0) {
            currentRightPwm -= RIGHT_DECEL_STEP;
            if (currentRightPwm < 0) currentRightPwm = 0;
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
            currentLeftPwm  = (LEFT_PWM_SPEED  > LEFT_START_PWM)  ? LEFT_START_PWM  : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentLeftPwm  = (LEFT_PWM_SPEED  > LEFT_START_PWM)  ? LEFT_START_PWM  : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentLeftPwm  = (LEFT_PWM_SPEED > LEFT_START_PWM) ? LEFT_START_PWM : LEFT_PWM_SPEED;
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
            currentLeftPwm  = (LEFT_PWM_SPEED  > LEFT_START_PWM)  ? LEFT_START_PWM  : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentLeftPwm  = (LEFT_PWM_SPEED  > LEFT_START_PWM)  ? LEFT_START_PWM  : LEFT_PWM_SPEED;
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentRightPwm = (RIGHT_PWM_SPEED > RIGHT_START_PWM) ? RIGHT_START_PWM : RIGHT_PWM_SPEED;
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
            currentLeftPwm  = (LEFT_PWM_SPEED > LEFT_START_PWM) ? LEFT_START_PWM : LEFT_PWM_SPEED;
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
            Serial.println("ok"); //OK when something is done so Q6A can get that feedback[cite: 2]
        }
    }
}

//--------------------------------------------------------------------------
// Default Pin State : Set every Pin back to 0. This will stop ghosting problem
//--------------------------------------------------------------------------
#endif