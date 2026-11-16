#ifndef MOTION_H
#define MOTION_H

/**
 * ============================================================================
 * @file    motion.h
 * @brief   Non-blocking Differential Drive & Split-Tick Motion Controller
 * ============================================================================
 * @details Non-blocking serial stream processor and command reader helper.
 *          Handles real-time byte accumulation from the Q6A AI board, 
 *          manages internal line buffers, and executes non-blocking motion
 *          pulses without introducing loop latency or blocking delays.
 * 
 *  ASYMMETRIC STOP COMPENSATION (MARLIN-STYLE OPTIONAL FEATURE):
 *  ---------------------------------------------------------------------------
 *  - Left Track  (BTS7960 H-Bridge)  : Active dynamic braking on 0 PWM[cite: 2].
 *  - Right Track (IRFB3306 + Relay)  : Slight electrical turn-off lag on 0 PWM[cite: 2].
 *  - Solution: Split remainingTicks into leftTicks and rightTicks. When
 *    RIGHT_EARLY_STOP_TICKS is enabled, the Right track cuts power early so
 *    both sides come to a physical stop at the exact same instant.
 * ============================================================================
 */

#include <Arduino.h>
#include "pins/pin_config.h"
#include "BTS7960.h"
#include "TIP42.h"

// ============================================================================
// @section Motion Tuning & Compensation Options (Marlin-Style)
// ============================================================================

/**
 * Asymmetric Stop Compensation (Early Right Cutoff)
 *
 * Uncomment RIGHT_EARLY_STOP_TICKS to cut power to the Right track early
 * before the Left track stops, canceling out electrical turn-off delay.
 * Comment out (//#define) to disable compensation and run equal ticks.
 *
 * Tuning Guide (at 2ms per time-slice tick: 12 ticks = ~24ms)[cite: 2]:
 * - Still twists left on stop  -> Increase value (e.g. 14 or 15)
 * - Starts twisting right       -> Decrease value (e.g. 8 or 10)
 */
#define RIGHT_EARLY_STOP_TICKS 12

// ============================================================================
// @section State Variables & Timers
// ============================================================================

int leftTicks  = 0;   // Independent countdown timer for Left track
int rightTicks = 0;   // Independent countdown timer for Right track
bool isMoving  = false;

static int LEFT_PWM_SPEED  = DEFAULT_LEFT_PWM_SPEED;
static int RIGHT_PWM_SPEED = DEFAULT_RIGHT_PWM_SPEED; 

void setLeftPwmSpeed(int value) {
    LEFT_PWM_SPEED = value;
}

void setRightPwmSpeed(int value) {
    RIGHT_PWM_SPEED = value;
}

// ============================================================================
// @section Low-Level Track Hardware Wrappers
// ============================================================================

/**
 * @brief Triggers non-blocking forward motion for a specified tick duration.
 * @param amount Number of 1ms time slices (ticks) to execute the movement.
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

void stopLeftTrack(){
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);
}

void stopRightTrack(){
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);
}

// ============================================================================
// @section High-Level Motion Primitives (M1 - M6)
// ============================================================================

void moveForward(int amount){
    Serial.println("Move Forward");

    leftTicks = amount;
    #ifdef RIGHT_EARLY_STOP_TICKS
        rightTicks = (amount > RIGHT_EARLY_STOP_TICKS) ? (amount - RIGHT_EARLY_STOP_TICKS) : 0;
    #else
        rightTicks = amount;
    #endif

    isMoving = (leftTicks > 0 || rightTicks > 0);

    if (leftTicks > 0)  moveLeftTrackForward();
    if (rightTicks > 0) moveRightTrackForward();
}

void moveBackward(int amount){
    leftTicks = amount;
    #ifdef RIGHT_EARLY_STOP_TICKS
        rightTicks = (amount > RIGHT_EARLY_STOP_TICKS) ? (amount - RIGHT_EARLY_STOP_TICKS) : 0;
    #else
        rightTicks = amount;
    #endif

    isMoving = (leftTicks > 0 || rightTicks > 0);

    if (leftTicks > 0)  moveLeftTrackBackward();
    if (rightTicks > 0) moveRightTrackBackward();
}

void rotateLeft(int amount){
    leftTicks = amount;
    #ifdef RIGHT_EARLY_STOP_TICKS
        rightTicks = (amount > RIGHT_EARLY_STOP_TICKS) ? (amount - RIGHT_EARLY_STOP_TICKS) : 0;
    #else
        rightTicks = amount;
    #endif

    isMoving = (leftTicks > 0 || rightTicks > 0);

    if (leftTicks > 0)  moveLeftTrackBackward();
    if (rightTicks > 0) moveRightTrackForward();
}

void rotateRight(int amount){
    leftTicks = amount;
    #ifdef RIGHT_EARLY_STOP_TICKS
        rightTicks = (amount > RIGHT_EARLY_STOP_TICKS) ? (amount - RIGHT_EARLY_STOP_TICKS) : 0;
    #else
        rightTicks = amount;
    #endif

    isMoving = (leftTicks > 0 || rightTicks > 0);

    if (leftTicks > 0)  moveLeftTrackForward();
    if (rightTicks > 0) moveRightTrackBackward();
}

void curveLeft(int amount){
    leftTicks  = 0;
    rightTicks = amount;
    isMoving   = (rightTicks > 0);

    if (rightTicks > 0) moveRightTrackForward();
}

void curveRight(int amount){
    leftTicks  = amount;
    rightTicks = 0;
    isMoving   = (leftTicks > 0);

    if (leftTicks > 0) moveLeftTrackForward();
}

void curveLeftBack(int amount){
    leftTicks  = 0;
    rightTicks = amount;
    isMoving   = (rightTicks > 0);

    if (rightTicks > 0) moveRightTrackBackward();
}

void curveRightBack(int amount){
    leftTicks  = amount;
    rightTicks = 0;
    isMoving   = (leftTicks > 0);

    if (leftTicks > 0) moveLeftTrackBackward();
}

// ============================================================================
// @section Emergency Stop & Hard Brake
// ============================================================================

void halt(){
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);

    leftTicks  = 0;
    rightTicks = 0;
    isMoving   = false;
}

//--------------------------------------------------------------------------
// Execution Phase: Fire up motor outputs and initialize tick counter
//--------------------------------------------------------------------------
void updateMotion(){
    if (!isMoving) return;

    if (leftTicks > 0) {
        leftTicks--; // Decrement by 1 every 1ms tick
        if (leftTicks == 0) {
            stopLeftTrack(); // Left side finished -> cut Left PWM immediately
        }
    }

    if (rightTicks > 0) {
        rightTicks--; // Decrement by 1 every 1ms tick
        if (rightTicks == 0) {
            stopRightTrack(); // Right side finished -> cut Right PWM
        }
    }

    //Serial.println(leftTicks);

    if (leftTicks == 0 && rightTicks == 0) {
        halt(); // Time's up! Stop all motors immediately.
        Serial.println("ok"); //OK when something is done so Q6A can get that feedback
    }
}

//--------------------------------------------------------------------------
// Default Pin State :  Set every Pins back to 0. This will stop ghosting problem
//--------------------------------------------------------------------------
#endif
