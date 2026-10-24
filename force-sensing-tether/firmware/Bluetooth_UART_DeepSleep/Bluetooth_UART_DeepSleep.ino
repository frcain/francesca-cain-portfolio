// ESP32 BLE UART service for the force-sensing tether.
//
// On boot, advertises a Nordic-style UART service and waits up to 30 seconds
// for a connection. When connected, it reads the analog input on SENSOR_PIN
// and sends each reading as a text notification on the TX characteristic
// every 120 ms, up to NUM_POINTS readings. It then enters deep sleep for
// 10 seconds and wakes up to advertise again. If nothing connects within
// 30 seconds, it also goes to sleep and tries again on the next wake.

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "esp_sleep.h"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// BLE UART service and characteristic UUIDs (Nordic UART layout)
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

#define DEVICE_NAME "UART Service"              // BLE device name

const int SENSOR_PIN = 34;                      // analog input for the sensor signal
const int DEBUG_PIN = 32;                       // second analog input, printed to Serial only

const unsigned long SERIAL_BAUD = 115200;
const int NUM_POINTS = 100000;                  // max readings sent per connection
const int POINT_INTERVAL_MS = 120;              // 120 ms between readings
const unsigned long CONNECT_WINDOW_MS = 30000;  // 30 seconds to wait for a connection
const uint64_t SLEEP_US = 10ULL * 1000000ULL;   // 10 seconds of deep sleep

const int STARTUP_DELAY_MS = 200;               // let Serial settle after begin()
const int PRE_SLEEP_DELAY_MS = 100;             // let the last Serial message go out
const int IDLE_DELAY_MS = 20;                   // loop() delay while waiting to connect

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

BLEServer *bleServer = NULL;
BLECharacteristic *txCharacteristic = NULL;

bool deviceConnected = false;
unsigned long bootMs = 0;   // millis() at boot, start of the connection window

// ---------------------------------------------------------------------------
// BLE callbacks
// ---------------------------------------------------------------------------

// Tracks whether a central (the laptop) is connected
class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    deviceConnected = true;
    Serial.println("Device connected");
  }

  void onDisconnect(BLEServer *server) override {
    deviceConnected = false;
    Serial.println("Device disconnected");
  }
};

// Prints anything written to the RX characteristic to Serial
class RxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    String rxValue = characteristic->getValue();
    if (rxValue.length() > 0) {
      Serial.print("Received: ");
      Serial.println(rxValue);
    }
  }
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Create the BLE server, the UART service, and its TX (notify) and RX (write)
// characteristics, then start the service.
void setupBle() {
  BLEDevice::init(DEVICE_NAME);

  bleServer = BLEDevice::createServer();
  bleServer->setCallbacks(new ServerCallbacks());

  BLEService *service = bleServer->createService(SERVICE_UUID);

  txCharacteristic = service->createCharacteristic(
    CHARACTERISTIC_UUID_TX,
    BLECharacteristic::PROPERTY_NOTIFY
  );
  txCharacteristic->addDescriptor(new BLE2902());

  BLECharacteristic *rxCharacteristic = service->createCharacteristic(
    CHARACTERISTIC_UUID_RX,
    BLECharacteristic::PROPERTY_WRITE
  );
  rxCharacteristic->setCallbacks(new RxCallbacks());

  service->start();
}

// Start advertising so the laptop can find and connect to the board.
void startAdvertising() {
  bleServer->getAdvertising()->start();
  Serial.println("Advertising - waiting up to 30 seconds for connection...");
}

// Send NUM_POINTS sensor readings as text notifications, one every
// POINT_INTERVAL_MS.
void sendReadings() {
  for (int i = 0; i < NUM_POINTS; i++) {
    int val = analogRead(SENSOR_PIN);
    char buf[8];
    sprintf(buf, "%d", val);

    // Also print the reading on DEBUG_PIN to Serial for debugging
    int debugVal = analogRead(DEBUG_PIN);
    Serial.println(debugVal);

    txCharacteristic->setValue(buf);
    txCharacteristic->notify();

    delay(POINT_INTERVAL_MS);
  }
}

// Enter deep sleep. The timer wakes the board after SLEEP_US, and it restarts
// from setup().
void goToSleep() {
  Serial.println("Going to deep sleep...");
  delay(PRE_SLEEP_DELAY_MS);
  esp_sleep_enable_timer_wakeup(SLEEP_US);
  esp_deep_sleep_start();
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(STARTUP_DELAY_MS);

  bootMs = millis();

  setupBle();
  startAdvertising();
}

void loop() {
  // If connected, send NUM_POINTS readings, then sleep
  if (deviceConnected) {
    sendReadings();
    goToSleep();
  }

  // If not connected within 30 seconds, sleep anyway (and try again next wake)
  if (!deviceConnected && (millis() - bootMs >= CONNECT_WINDOW_MS)) {
    Serial.println("No connection within 30 seconds.");
    goToSleep();
  }

  delay(IDLE_DELAY_MS);
}
