#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

/**
 * @file pin_config.h
 * @brief Non-blocking, time-sliced motion control layer for vehicle architecture.
 * @details Interfaces with hardware drivers and handshakes with the Q6A AI board.
 */

#include <Arduino.h>

/*
    Pin Out Line

    A0 -> ANG ->
    A1 -> ANG ->
    A2 -> ANG ->
    A3 -> ANG ->
    A4 -> ANG ->
    A5 -> ANG ->

    1  -> PIO ->
    2  -> PIO ->
    3  -> PWM -> LEFT_LPWM
    4  -> PIO ->
    5  -> PWM -> LEFT_RPWM
    6  -> PWM -> RIGHT_LPWM
    7  -> PIO ->
    8  -> PIO ->  
    9  -> PWM -> RIGHT_LPWM_EN
    10 -> PWM -> BRUSH_PIN
    11 -> PWM -> PUMP_PIN
    12 -> PIO ->
    13 -> PIO -> 
*/

// Choose your driver
#define DRIVER_BTS7960 1
#define DRIVER_CUSTOM_RELAY 2

//For left Motor
#define LEFT_LPWM_PIN   3   // Speed PWM pin
#define LEFT_RPWM_PIN   5   // Direction pin (LPWM for BTS, Relay for TIP42)

//For right motor
#define RIGHT_LPWM_PIN  6
#define RIGHT_RPWM_PIN  9


#define BRUSH_PIN 10 // Set to whichever PWM pin connects to your TIP120 1k resistor
#define PUMP_PIN 11   // Water Pump TIP120 Base (PWM Pin 11)

void initPins(){
    pinMode(LEFT_LPWM_PIN, OUTPUT);
    pinMode(LEFT_RPWM_PIN, OUTPUT); 
    pinMode(RIGHT_LPWM_PIN, OUTPUT);
    pinMode(RIGHT_RPWM_PIN, OUTPUT); 
    pinMode(BRUSH_PIN, OUTPUT);
    pinMode(PUMP_PIN, OUTPUT);
    analogWrite(BRUSH_PIN, 0);
    analogWrite(PUMP_PIN, 0);
}

#endif