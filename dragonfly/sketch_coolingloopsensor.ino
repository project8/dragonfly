#include <DallasTemperature.h>
#include <EtherCard.h>
#include <IPAddress.h>
#include <OneWire.h>
#include <string.h>

/* ----------------------------- CONFIGURATION ----------------------------*/

#define DEBUG 1  // 0 disabled, 1 enabled
#define DHCP 1   // 0 disabled, 1 enabled
#define MAC 0    // 0 for astro-yacht, 1 for astro-zabra, 2 for astro-aye

/* ------------------------------------------------------------------------*/

#if DEBUG
#define DEBUG_PRINTLN(x) Serial.println(x)
#define DEBUG_PRINT(x) Serial.print(x)
#define DEBUG_PRINTIP(x, y) ether.printIp(x, y)
#else
#define DEBUG_PRINTLN(x)
#define DEBUG_PRINT(x)
#define DEBUG_PRINTIP(x)
#endif

const byte pinFlowmeter = 3;    // Interrupt pin (D2)
const byte pinTemperature = 5;  // Digital pin (D6)
const byte pinPressure = 6;

volatile unsigned int pulseCount = 0;     // Stores number of pulses
const int flowMeasurementDuration = 500;  // Microsecond

OneWire oneWire(pinTemperature);
DallasTemperature temperatureSensor(&oneWire);

#if MAC == 0
static byte mymac[] = {0x5a, 0x09, 0xb5, 0xaf, 0xd8, 0x11};
#elif MAC == 1
static byte mymac[] = {0x5a, 0x09, 0xb5, 0xaf, 0xd8, 0x10};
#elif MAC == 2
static byte mymac[] = {0x5a, 0x09, 0xb5, 0xaf, 0xd8, 0x09};
#endif

#if DHCP == 0
static byte myip[] = {192, 168, 1, 10};
// Gateway IP address
static byte gwip[] = {192, 168, 0, 10};
#endif

byte Ethernet::buffer[500];  // TCP/IP send and receive buffer

void pulseISR() {
  pulseCount++;  // Interrupt service routine: Increment the pulse count on each interrupt
}

float getTemperatureC() {
  /* Returns temperature in degrees Celcius */
  temperatureSensor.requestTemperatures();
  return temperatureSensor.getTempCByIndex(0);
}

float getPressureV() {
  /* Returns the pressure in Volts */
  int sensorValue = analogRead(pinPressure);
  return sensorValue * (5.0 / 1023.0);
}

float getFlowHz() {
  /* Returns pulse frequency in Herz */
  pulseCount = 0;
  delay(flowMeasurementDuration);
  float frequency = (float)pulseCount * 1000.0 / (flowMeasurementDuration);
  return frequency;
}

void setup() {
#if DEBUG
  Serial.begin(115200);
#endif

  pinMode(pinFlowmeter, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pinFlowmeter), pulseISR, RISING);

  temperatureSensor.begin();
  if (ether.begin(sizeof Ethernet::buffer, mymac) == 0) {
    DEBUG_PRINTLN("Failed to access Ethernet controller.");
  } else {
    DEBUG_PRINTLN("Ethernet controller sucessfully accessed.");
  }

#if DHCP == 0
  ether.staticSetup(myip, gwip);
#else
  if (!ether.dhcpSetup()) {
    DEBUG_PRINTLN("DHCP failed");
  } else {
    DEBUG_PRINTIP("DHCP request successful. IP-Adress: ", ether.myip);
    DEBUG_PRINT("Lease time: ");
    DEBUG_PRINTLN(ether.getLeaseTime());
  }
#endif
}

void loop() {
  word len = ether.packetReceive();
  word pos = ether.packetLoop(len);

  if (pos) {
    char *data = (char *)Ethernet::buffer + pos;
    DEBUG_PRINT("Received data: ");
    DEBUG_PRINTLN(data);

    float sensorData = 0;
    boolean caseFound = false;

    char response[10];
    memset(response, '\n', sizeof(response));
    if (strncmp(data, "temp?", 5) == 0) {
      sensorData = getTemperatureC();
      dtostrf(sensorData, 4, 4, response);
    } else if (strncmp(data, "pres?", 5) == 0) {
      sensorData = getPressureV();
      dtostrf(sensorData, 4, 4, response);
    } else if (strncmp(data, "flow?", 5) == 0) {
      sensorData = getFlowHz();
      dtostrf(sensorData, 4, 4, response);
    } else if (strncmp(data, "test?", 5) == 0) {
      strcpy(response, "success");
    } else {
      strcpy(response, "invalid");
    }

    DEBUG_PRINT("Sending data: ");
    DEBUG_PRINTLN(response);

    memcpy(ether.tcpOffset(), response, sizeof(response));
    ether.httpServerReply(sizeof(response) - 1);
  }

  // if DHCP lease is expired or millis wrap over after 49 days
#if DHCP
  float leaseStart = ether.getLeaseStart();
  if ((millis() - leaseStart >= ether.getLeaseTime()) ||
      (millis() < leaseStart)) {
    if (!ether.dhcpSetup()) {
      DEBUG_PRINTLN("DHCP renew failed");
      delay(60000);  // wait for one minute before retrying.
    } else {
      DEBUG_PRINTIP("DHCP renewed. IP-Adress: ", ether.myip);
      DEBUG_PRINT("Lease time: ");
      DEBUG_PRINTLN(ether.getLeaseTime());
    }
  }
#endif
}
