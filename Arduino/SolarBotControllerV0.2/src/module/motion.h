#ifndef MOTION_H
#define MOTION_H

/**
 * @file serialReader.h
 * @brief Non-blocking serial stream processor and command reader.
 * @details Handles real-time byte accumulation from the Q6A AI board, 
 *          manages internal line buffers, and extracts incoming command 
 *          packets without introducing loop latency or blocking delays.
 */

#include <Arduino.h>
#include "pins/pin_config.h"
#include "BTS7960.h"
#include "TIP42.h"

// ============================================================================
// @section State Variables & Timers
// ============================================================================

int remainingTicks = 0;

static int LEFT_PWM_SPEED = DEFAULT_LEFT_PWM_SPEED;
static int RIGHT_PWM_SPEED = DEFAULT_RIGHT_PWM_SPEED; 

void setLeftPwmSpeed(int value) {
    LEFT_PWM_SPEED = value;
}

void setRightPwmSpeed(int value) {
    RIGHT_PWM_SPEED = value;
}

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

void moveForward(int amount){

    Serial.println("Move Forward");
    remainingTicks = amount;

    moveLeftTrackForward();
    moveRightTrackForward();
}

void moveBackward(int amount){
    remainingTicks = amount;

    moveLeftTrackBackward();
    moveRightTrackBackward();
}

void rotateLeft(int amount){
    remainingTicks = amount;
    moveLeftTrackBackward();
    moveRightTrackForward();
}

void rotateRight(int amount){
    remainingTicks = amount;
    moveLeftTrackForward();
    moveRightTrackBackward();
}

void curveLeft(int amount){
    remainingTicks = amount;
    moveRightTrackForward();
}

void curveRight(int amount){
    remainingTicks = amount;
    moveLeftTrackForward();
}

void halt(){
    analogWrite(LEFT_LPWM_PIN, 0);
    analogWrite(LEFT_RPWM_PIN, 0);
    analogWrite(RIGHT_LPWM_PIN, 0);
    analogWrite(RIGHT_RPWM_PIN, 0);
}
//--------------------------------------------------------------------------
// Execution Phase: Fire up motor outputs and initialize tick counter
//--------------------------------------------------------------------------
void updateMotion(){
    if (remainingTicks > 0) {
        remainingTicks--; // Decrement by 1 every 1ms tick
        Serial.println(remainingTicks);
        if (remainingTicks == 0) {
            halt(); // Time's up! Stop all motors immediately.
            Serial.println("ok"); //OK when something is done so Q6A can get that feedback
        }
    }
}

//--------------------------------------------------------------------------
// Default Pin State :  Set every Pins back to 0. This will stop ghosting problem
//--------------------------------------------------------------------------
#endif 