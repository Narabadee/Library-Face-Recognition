#include <WiFi.h>
#include <WebServer.h>

// ==========================================
// ⚠️ CHANGE THESE VARIABLES ⚠️
// ==========================================
const char* ssid     = "TP-Link_8054";
const char* password = "18224818";

// GPIO Pins
const int LED_PIN   = 14;  // LED แจ้งเตือน (HIGH = ติด)
const int RELAY_PIN = 12;  // Relay ควบคุมประตู (HIGH = เปิด)

// ==========================================

// Auto-reset timer — ประตู + LED ปิดอัตโนมัติหลัง X วินาที
const unsigned long OPEN_DURATION_MS = 3000;  // 3 วินาที

unsigned long openTime  = 0;
bool isOpen = false;

WebServer server(80);

// ── Helper ────────────────────────────────────────────────────────────────

void openGate() {
  digitalWrite(LED_PIN,   HIGH);  // LED ติด = เปิดประตู
  digitalWrite(RELAY_PIN, HIGH);  // Relay เปิด
  isOpen   = true;
  openTime = millis();
  Serial.println("[GATE] OPEN - LED ON, Relay ON");
}

void closeGate() {
  digitalWrite(LED_PIN,   LOW);   // LED ดับ
  digitalWrite(RELAY_PIN, LOW);   // Relay ปิด
  isOpen = false;
  Serial.println("[GATE] CLOSED - LED OFF, Relay OFF");
}

// ── Endpoints ─────────────────────────────────────────────────────────────

// POST /trigger/success — จดจำใบหน้าได้ → เปิดประตู + LED ติด
void handleSuccess() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  openGate();
  server.send(200, "application/json", "{\"status\":\"success_acknowledged\"}");
}

// POST /trigger/fail — จดจำไม่ได้ → ประตูปิด (ไม่ทำอะไร)
void handleFail() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  Serial.println("[FAIL] Face not recognized - door stays closed");
  server.send(200, "application/json", "{\"status\":\"fail_acknowledged\"}");
}

// POST /trigger/open — admin บังคับเปิดประตู
void handleOpen() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  openGate();
  server.send(200, "application/json", "{\"status\":\"door_opened\"}");
}

// POST /trigger/close — admin บังคับปิดประตู
void handleClose() {
  if (server.method() != HTTP_POST) {
    server.send(405, "text/plain", "Method Not Allowed"); return;
  }
  closeGate();
  server.send(200, "application/json", "{\"status\":\"door_closed\"}");
}

// GET /status — Flask เช็คว่า ESP32 ออนไลน์อยู่ไหม
void handleStatus() {
  String ip   = WiFi.localIP().toString();
  String rssi = String(WiFi.RSSI());
  String json = "{\"online\":true,\"ip\":\"" + ip + "\",\"rssi\":" + rssi +
                ",\"relay\":" + (isOpen ? "true" : "false") + "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.send(404, "text/plain", "Endpoint Not Found");
}

// ── Setup ─────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN,   OUTPUT); digitalWrite(LED_PIN,   LOW);
  pinMode(RELAY_PIN, OUTPUT); digitalWrite(RELAY_PIN, LOW);

  // Connect WiFi
  Serial.print("Connecting to "); Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP()); // <<< ใส่ IP นี้ใน config.py

  // Routes
  server.on("/trigger/success", handleSuccess);
  server.on("/trigger/fail",    handleFail);
  server.on("/trigger/open",    handleOpen);
  server.on("/trigger/close",   handleClose);
  server.on("/status",          handleStatus);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("HTTP server started. Ready!");
}

// ── Loop ──────────────────────────────────────────────────────────────────

void loop() {
  server.handleClient();

  // Auto-close ประตู + ดับ LED หลัง OPEN_DURATION_MS
  if (isOpen && (millis() - openTime >= OPEN_DURATION_MS)) {
    closeGate();
  }
}
