#ifndef SERIAL_READER_H
#define SERIAL_READER_H

#include <Arduino.h>
#include "module/motion.h"
/**
 * @file serialReader.h
 * @brief Non-blocking serial stream processor and command reader.
 * @details Handles real-time byte accumulation from the Q6A AI board, 
 *          manages internal line buffers, and extracts incoming command 
 *          packets without introducing loop latency or blocking delays.
 */

String serialHandler() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    input.toUpperCase(); // Converts to uppercase so 'm90', 'm100', 'm1' work seamlessly
    return input;
  }
  return "";
}

void cmdHandler(){
  String response = serialHandler();
  if (response.length() > 0) {
    
    if (response.startsWith("M90")) {
      
    }
    else if (response.startsWith("M100")) {
      
    }

// ============================================================================
// @section Move Backward 
// ============================================================================

    else if (response.startsWith("M1")) { //Move Forward : moveForward(millisecond)
      //Serial.println("M1 Trigger");
      int spaceIndex = response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            moveForward(targetTicks);
      }
    } 

// ============================================================================
// @section Brush Motor Continuous Control (M20 <PWM>)
// ============================================================================
    else if (response.startsWith("M20")) {
      int spaceIndex = response.indexOf(' ');
      if (spaceIndex != -1) {
          int brushSpeed = response.substring(spaceIndex + 1).toInt();
          
          // Set speed directly (0 = OFF, 255 = Full Speed)
          analogWrite(BRUSH_PIN, brushSpeed);
          
          // Acknowledge back to Python / Q6A
          Serial.println("OK BRUSH");
      }
    }
// ============================================================================
// @section Move Backward 
// ============================================================================

    else if (response.startsWith("M2 ")){//Move backward
      int spaceIndex =  response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            moveBackward(targetTicks);
      }

    }

// ============================================================================
// @section Timed Water Pump Pulse with Custom PWM (M30 <millisecond>)
// ============================================================================
    else if (response.startsWith("M30 ")) {
      int spaceIndex = response.indexOf(' ');
      if (spaceIndex != -1) {
          int durationMs = response.substring(spaceIndex + 1).toInt();
          
          // 1. Fire pump at your preset PWM speed
          analogWrite(PUMP_PIN, DEFAULT_PUMP_PWM_SPEED);
          
          // 2. Run for the requested time (e.g. 100ms or 2000ms for water travel)
          delay(durationMs);
          
          // 3. Shut pump OFF immediately
          analogWrite(PUMP_PIN, 0);
          
          // 4. Send clean ACK back to Q6A (No countdown spam)
          Serial.println("OK : PUMP_DONE");
      }
    }

// ============================================================================
// @section Move Backward 
// ============================================================================

    else if (response.startsWith("M3 ")){
      int spaceIndex =  response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            curveLeft(targetTicks);
      }

    }

// ============================================================================
// @section Move Backward 
// ============================================================================

    else if (response.startsWith("M4")){
      int spaceIndex =  response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            curveRight(targetTicks);
      }
    }

    else if (response.startsWith("M5")){
      int spaceIndex =  response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            rotateLeft(targetTicks);
      }
    }

    else if (response.startsWith("M6")){
      int spaceIndex =  response.indexOf(' ');
      if (spaceIndex != -1) {
            // Extract the number after the space and convert to integer
            int targetTicks = response.substring(spaceIndex + 1).toInt();
          
            // Trigger your non-blocking movement function
            rotateRight(targetTicks);
      }
    }
  }
}


#endif