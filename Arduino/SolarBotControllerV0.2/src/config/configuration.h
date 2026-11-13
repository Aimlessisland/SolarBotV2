#ifndef CONFIGURATION_H
#define CONFIGURATION_H

/**
 * @file configuration.h
 * @brief Non-blocking, time-sliced motion control layer for vehicle architecture.
 * @details Interfaces with hardware drivers and handshakes with the Q6A AI board.
 */

// ============================================================================
// @section Driver Types (Do not change these definitions)
// ============================================================================
#define DRIVER_BTS7960        1
#define DRIVER_CUSTOM_RELAY   2 

// --- Default Motor Speeds ---
#define DEFAULT_LEFT_PWM_SPEED   100
#define DEFAULT_RIGHT_PWM_SPEED  180  
#define DEFAULT_PUMP_PWM_SPEED 160   // Tweak this value (e.g. 120 - 200)
// ============================================================================
// @section Active Motor Driver Selection
// OPTION A DRIVER_BTS7960
// OPTION B DRIVER_CUSTOM_RELAY
// The choosen opetion will make it call either BTS7960.h or TIP42.h
// ============================================================================

// Configure what hardware is plugged into each side independently:
#define LEFT_MOTOR_DRIVER   DRIVER_BTS7960        // Surviving commercial module
#define RIGHT_MOTOR_DRIVER  DRIVER_CUSTOM_RELAY   // Your custom-built board

#endif // CONFIGURATION_H