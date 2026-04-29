#include <WiFi.h>
#include <WebServer.h>

// ==========================================
// ⚠️ WiFi Configuration ⚠️
// ==========================================
const char* ssid     = "TP-Link_8054";
const char* password = "18224818";

// GPIO Pins (Active LOW for Relays/LEDs)
const int PIN_RED   = 14; // Red LED (Waiting/Idle)
const int PIN_GREEN = 13; // Green LED (Success/Gate)

// Auto-reset timer — 3 seconds duration
const unsigned long OPEN_DURATION_MS = 3000;

unsigned long openTime  = 0;
bool isOpen = false;

WebServer server(80);

// ── Helper Logic ──────────────────────────────────────────────────────────

// State: Waiting for check-in (Idle)
void setIdleState() {
  digitalWrite(PIN_RED,   LOW);  // Red ON (Active LOW)
  digitalWrite(PIN_GREEN, HIGH); // Green OFF
  isOpen = false;
  Serial.println("[STATE] Waiting for check-in - Red ON");
}

// State: Check-in Successful
void openGate() {
  digitalWrite(PIN_RED,   HIGH); // Red OFF
  digitalWrite(PIN_GREEN, LOW);  // Green ON (Active LOW)
  isOpen   = true;
  openTime = millis();
  Serial.println("[STATE] Success! - Green ON");
}

// ── Endpoints ─────────────────────────────────────────────────────────────

// POST /trigger/success — Success detected
void handleSuccess() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  openGate();
  server.send(200, "application/json", "{\"status\":\"success_acknowledged\"}");
}

// POST /trigger/fail — Recognition failed (Remain Idle or reset to Idle)
void handleFail() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  setIdleState(); // Ensure we are in Red ON state
  server.send(200, "application/json", "{\"status\":\"fail_acknowledged\"}");
}

// POST /trigger/open — Manual open
void handleOpen() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  openGate();
  server.send(200, "application/json", "{\"status\":\"door_opened\"}");
}

// POST /trigger/close — Manual close (Idle)
void handleClose() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  setIdleState();
  server.send(200, "application/json", "{\"status\":\"door_closed\"}");
}

// GET /status
void handleStatus() {
  String ip   = WiFi.localIP().toString();
  String json = "{\"online\":true,\"ip\":\"" + ip + "\",\"state\":\"" + (isOpen ? "success" : "idle") + "\"}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.send(404, "text/plain", "Endpoint Not Found");
}

// ── Setup ─────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);

  // Initialize Pins
  pinMode(PIN_RED,   OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);

  // Start in Idle State (Red ON)
  setIdleState();

  // Connect WiFi
  Serial.print("Connecting to "); Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP: "); Serial.println(WiFi.localIP());

  // Routes
  server.on("/trigger/success", handleSuccess);
  server.on("/trigger/fail",    handleFail);
  server.on("/trigger/open",    handleOpen);
  server.on("/trigger/close",   handleClose);
  server.on("/status",          handleStatus);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("HTTP server started.");
}

// ── Loop ──────────────────────────────────────────────────────────────────

void loop() {
  server.handleClient();

  // Auto-reset to Idle after 3 seconds
  if (isOpen && (millis() - openTime >= OPEN_DURATION_MS)) {
    setIdleState();
  }
}
