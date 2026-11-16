#ifndef MOTION_H
#define MOTION_H

/**
 * ============================================================================
 * @file    motion.h
 * @brief   Non-blocking Differential Drive & Smooth Ramp Motion Controller
 * ============================================================================
 * @details Handles real-time byte accumulation from the Q6A AI board, 
 *          manages internal line buffers, and executes non-blocking motion
 *          pulses without introducing loop latency or blocking delays.
 * 
 *  TRAPEZOID RAMP PROFILE (SMOOTH_RAMP):
 *  ---------------------------------------------------------------------------
 *  - Start at MIN_PWM_SPEED : Overcomes worm-gear static friction immediately.
 *  - Accel (+RAMP_STEP)     : Climbs smoothly up to LEFT/RIGHT_PWM_SPEED.
 *  - Decel (-RAMP_STEP)     : Slows down during the last DECEL_TICKS before 0.
 * ============================================================================
 */

#include <Arduino.h>
#include "pins/pin_config.h"
#include "BTS7960.h"
#include "TIP42.h"

// ============================================================================
// @section Motion Tuning & Smooth Ramp Options (Marlin-Style)
// ============================================================================

/**
 * Smooth Acceleration & Deceleration
 * Comment out (//#define) to disable ramping and run your exact original code.
 */
#define SMOOTH_RAMP

#define MIN_PWM_SPEED   40   // Lowest PWM that still moves the worm-gear wheels
#define RAMP_STEP       2    // PWM change per tick (higher = faster ramp)
#define DECEL_TICKS     45   // Start slowing down 15 ticks (~30ms) before stop

// ============================================================================
// @section State Variables & Timers
// ============================================================================

int remainingTicks = 0;

static int LEFT_PWM_SPEED = DEFAULT_LEFT_PWM_SPEED;
static int RIGHT_PWM_SPEED = DEFAULT_RIGHT_PWM_SPEED; 

#ifdef SMOOTH_RAMP
    static int motionMode      = 0;
    static int currentLeftPwm  = 0;
    static int currentRightPwm = 0;
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
 * @param amount Number of time slices (ticks) to execute the movement.
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
// @section Internal Smooth Ramp Helpers (Active Only When SMOOTH_RAMP Enabled)
// ============================================================================

#ifdef SMOOTH_RAMP
void writeLeftRampPwm(bool forward){
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

void writeRightRampPwm(bool forward){
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

void applyRampPwm(){
    if      (motionMode == 1) { writeLeftRampPwm(true);  writeRightRampPwm(true);  } // M1 Forward
    else if (motionMode == 2) { writeLeftRampPwm(false); writeRightRampPwm(false); } // M2 Backward
    else if (motionMode == 3) { writeRightRampPwm(true);  }                          // M3 Curve Left
    else if (motionMode == 4) { writeLeftRampPwm(true);   }                          // M4 Curve Right
    else if (motionMode == 5) { writeLeftRampPwm(false); writeRightRampPwm(true);  } // M5 Rotate Left
    else if (motionMode == 6) { writeLeftRampPwm(true);  writeRightRampPwm(false); } // M6 Rotate Right
    else if (motionMode == 7) { writeRightRampPwm(false); }                          // Curve Left Back
    else if (motionMode == 8) { writeLeftRampPwm(false);  }                          // Curve Right Back
}

void startRamp(int mode){
    motionMode      = mode;
    currentLeftPwm  = (LEFT_PWM_SPEED  > MIN_PWM_SPEED) ? MIN_PWM_SPEED : LEFT_PWM_SPEED;
    currentRightPwm = (RIGHT_PWM_SPEED > MIN_PWM_SPEED) ? MIN_PWM_SPEED : RIGHT_PWM_SPEED;
    applyRampPwm();
}

void updateRampPwm(){
    if (remainingTicks > DECEL_TICKS) {
        if (currentLeftPwm < LEFT_PWM_SPEED) {
            currentLeftPwm += RAMP_STEP;
            if (currentLeftPwm > LEFT_PWM_SPEED) currentLeftPwm = LEFT_PWM_SPEED;
        }
        if (currentRightPwm < RIGHT_PWM_SPEED) {
            currentRightPwm += RAMP_STEP;
            if (currentRightPwm > RIGHT_PWM_SPEED) currentRightPwm = RIGHT_PWM_SPEED;
        }
    } else {
        if (currentLeftPwm > 0) {
            currentLeftPwm -= RAMP_STEP;
            if (currentLeftPwm < 0) currentLeftPwm = 0;
        }
        if (currentRightPwm > 0) {
            currentRightPwm -= RAMP_STEP;
            if (currentRightPwm < 0) currentRightPwm = 0;
        }
    }
    applyRampPwm();
}
#endif

// ============================================================================
// @section High-Level Motion Primitives (M1 - M6)
// ============================================================================

void moveForward(int amount){
    Serial.println("Move Forward");
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(1);
    #else
        moveLeftTrackForward();
        moveRightTrackForward();
    #endif
}

void moveBackward(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(2);
    #else
        moveLeftTrackBackward();
        moveRightTrackBackward();
    #endif
}

void curveLeft(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(3);
    #else
        moveRightTrackForward();
    #endif
}

void curveRight(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(4);
    #else
        moveLeftTrackForward();
    #endif
}

void rotateLeft(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(5);
    #else
        moveLeftTrackBackward();
        moveRightTrackForward();
    #endif
}

void rotateRight(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(6);
    #else
        moveLeftTrackForward();
        moveRightTrackBackward();
    #endif
}

void curveLeftBack(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(7);
    #else
        moveRightTrackBackward();
    #endif
}

void curveRightBack(int amount){
    remainingTicks = amount;
    #ifdef SMOOTH_RAMP
        startRamp(8);
    #else
        moveLeftTrackBackward();
    #endif
}

// ============================================================================
// @section Emergency Stop & Hard Brake
// ============================================================================

void halt(){
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);
    #ifdef SMOOTH_RAMP
        motionMode      = 0;
        currentLeftPwm  = 0;
        currentRightPwm = 0;
    #endif
}

//--------------------------------------------------------------------------
// Execution Phase: Fire up motor outputs and initialize tick counter
//--------------------------------------------------------------------------
void updateMotion(){
    if (remainingTicks > 0) {
        remainingTicks--; // Decrement by 1 every 1ms tick
        //Serial.println(remainingTicks);

        #ifdef SMOOTH_RAMP
            if (remainingTicks > 0) {
                updateRampPwm();
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
