#include <WiFi.h>
#include <WebServer.h>

// ==========================================
// ⚠️ CHANGE THESE VARIABLES ⚠️
// ==========================================
const char* ssid = "Zea's Phone";
const char* password = "ppnacuh123";

// Define your GPIO pins for the LEDs
const int GREEN_LED_PIN = 14; // Example pin
const int RED_LED_PIN = 12;   // Example pin

// ==========================================

// Initialize the web server on port 80 (Standard HTTP)
WebServer server(80);

// Function to handle the Success route
void handleSuccess() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }
  
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  
  Serial.println("Action: Success - Green LED ON");
  server.send(200, "application/json", "{\"status\":\"success_acknowledged\"}");
}

// Function to handle the Fail route
void handleFail() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed");
    return;
  }
  
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  
  Serial.println("Action: Fail - Red LED ON");
  server.send(200, "application/json", "{\"status\":\"fail_acknowledged\"}");
}

// Function for 404 Not Found
void handleNotFound() {
  server.send(404, "text/plain", "Endpoint Not Found");
}

void setup() {
  Serial.begin(115200);
  
  // Configure LED pins as outputs and ensure they are OFF initially
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);

  // Connect to Wi-Fi
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500); // This blocking delay is okay ONLY in setup()
    Serial.print(".");
  }

  Serial.println("\nWiFi connected!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP()); // ⚠️ TAKE NOTE OF THIS IP ADDRESS ⚠️

  // Register the URL routes
  server.on("/trigger/success", handleSuccess);
  server.on("/trigger/fail", handleFail);
  server.onNotFound(handleNotFound);

  // Start the server
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  // Listen for incoming HTTP requests
  // Notice there are NO delay() calls here. delay() blocks the server from receiving requests!
  server.handleClient(); 
}
