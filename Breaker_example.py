import board
import busio
import time
import math
import json
from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_blinka.microcontroller.bcm283x.pin import Pin

# --- Custom I2C Pins ---
ALT_SCL = Pin(29)  # GPIO 29
ALT_SDA = Pin(7)   # GPIO 7

# --- Initialize I2C buses ---
i2c1 = busio.I2C(board.SCL, board.SDA)           # Default I2C bus
i2c2 = busio.I2C(ALT_SCL, ALT_SDA)               # Alternate I2C bus

# --- Initialize ADS1115s ---
ads1 = ADS.ADS1115(i2c1)
ads2 = ADS.ADS1115(i2c2)
ads1.gain = 1
ads2.gain = 1

chan1 = AnalogIn(ads1, ADS.P0, ADS.P1)
chan2 = AnalogIn(ads2, ADS.P0, ADS.P1)

# Constants
Resistor = 33.0
Max_amp = 100.0
Max_output = 0.050
Max_v = Max_output * Resistor
RMS = Max_v / math.sqrt(2)
V_per_amp = RMS / Max_amp
SAMPLES = 1000
Delay = 0.0005

def rms_voltage(channel):
    readings = []
    for _ in range(SAMPLES):
        voltage = channel.voltage
        readings.append(voltage)
        time.sleep(Delay)
    avg = sum(readings) / len(readings)
    centered = [(v - avg) for v in readings]
    squared = [v**2 for v in centered]
    mean_square = sum(squared) / len(squared)
    vrms = math.sqrt(mean_square)
    return vrms

def rms_current(vrms):
    return vrms / V_per_amp

# --- AWS IoT Setup ---
host = "a133l554m35t36-ats.iot.us-east-2.amazonaws.com"
certPath = "/home/ethy/Breaker_sensor/cert/"
clientId = "Breaker_sensor"
topic = "Breaker_data"

myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(
    f"{certPath}RootCA1.pem",
    f"{certPath}Breaker_sensor-private.pem.key",
    f"{certPath}Breaker_sensor-cert.pem.crt"
)

myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 32, 20)
myAWSIoTMQTTClient.configureOfflinePublishQueueing(-1)
myAWSIoTMQTTClient.configureDrainingFrequency(2)
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(10)
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5)
myAWSIoTMQTTClient.connect()

# --- Publish Loop ---
loopCount = 0

while True:
    vrms1 = rms_voltage(chan1)
    irms1 = rms_current(vrms1)

    vrms2 = rms_voltage(chan2)
    irms2 = rms_current(vrms2)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "sequence": loopCount,
        "timestamp": timestamp,
        "sensor1": {
            "vrms_voltage": round(vrms1, 4),
            "irms_current": round(irms1, 2)
        },
        "sensor2": {
            "vrms_voltage": round(vrms2, 4),
            "irms_current": round(irms2, 2)
        }
    }

    messageJson = json.dumps(payload)
    myAWSIoTMQTTClient.publish(topic, messageJson, 1)
    print('Published topic %s: %s\n' % (topic, messageJson))
    loopCount += 1
    time.sleep(10)
