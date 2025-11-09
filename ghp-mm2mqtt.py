#!/usr/bin/env python3

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import os
import paho.mqtt.client as mqtt
import struct
import json
import time
import logging

from ghp_config import *








# Настройка логирования
# logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.ERROR)
_logger = logging.getLogger(__name__)

# Импорт и инициализация Serial
from serial_setup import init_serial
ser = init_serial()

# modbus message to write, it's emptied upon writing and can be set
# by mqtt MQTT_TOPIC_PREFIX/set topic in on_message()
writemsg = ''

print("🚀 Скрипт стартует...")



# Function to calculate Modbus CRC16
def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

# Function to verify the CRC of a Modbus message
def verify_modbus_crc(data: bytes) -> bool:
    if len(data) < 4:  # Minimal Modbus frame size with CRC
        return False
    received_crc = struct.unpack('<H', data[-2:])[0]  # Last 2 bytes are the CRC
    calculated_crc = modbus_crc16(data[:-2])  # CRC of the data without the last 2 CRC bytes
    _logger.debug(f"received crc: {received_crc} = calculated_crc {calculated_crc}");
    return received_crc == calculated_crc

def publish(slave, op, addr, data):
    data_json = json.dumps(data)
    retain = 2100 <= addr < 2200
    MQTT_TOPIC = f"{MQTT_TOPIC_PREFIX}/{op}/{slave}/{addr}"

    print(f"📤 MQTT: topic={MQTT_TOPIC}, payload={data_json}, retain={retain}")  # ← отладочный вывод

    _logger.info(f"{MQTT_TOPIC}: {data_json}")
    mqtt_client.publish(MQTT_TOPIC, data_json, retain=retain)


def decodeModbus():
    global buffer, readAddr, writemsg, ser

    while True:
        buflen = len(buffer)
        if buflen < 8:
            break

        index = buffer.find(240)  # ищем slave 240
        if index < 0 or buflen - index < 8:
            break

        buffer = buffer[index:]
        _logger.debug(f"found on position {index}\nbuffer={buffer}\n")

        if buffer[1] == 3:  # 0x03 read command
            if verify_modbus_crc(buffer[0:8]):  # Read Request
                readAddr = struct.unpack('>h', buffer[2:4])[0]
                buffer = buffer[8:]
            else:  # Read Response
                psize = buffer[2] + 5
                if buflen < psize:
                    break  # ждём, пока придёт весь пакет
                if verify_modbus_crc(buffer[0:psize]):
                    numshorts = int((psize - 5) / 2)
                    publish(buffer[0], 3, readAddr, struct.unpack(f'>{numshorts}h', buffer[3:psize-2]))
                    if len(writemsg) > 5:
                        writemsg += modbus_crc16(writemsg).to_bytes(2, 'little')
                        _logger.info(f"WRITE {writemsg}\n")
                        ser.write(writemsg)
                        writemsg = ''
                    buffer = buffer[psize:]
                else:
                    buffer = buffer[1:]

        elif buffer[1] == 16:  # 0x10 write command
            if buflen < 7:
                break
            psize = buffer[6] + 9
            if buflen < psize:
                break
            _logger.debug(f"psize={psize} packet={buffer[0:psize]}")
            if verify_modbus_crc(buffer[0:psize]):
                readAddr = struct.unpack('>h', buffer[2:4])[0]
                numshorts = int((psize - 9) / 2)
                publish(buffer[0], 10, readAddr, struct.unpack(f">{numshorts}h", buffer[7:psize-2]))
                buffer = buffer[psize:]
            else:
                buffer = buffer[1:]

        else:
            buffer = buffer[1:]


def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC_PREFIX+"/set/#")

def on_message(client, userdata, msg):
    global writemsg
    _logger.info(f"MQTT received msg.topic={msg.topic} msg.payload={msg.payload}")
    addr= msg.topic.split('/')
    if ( int(addr[3]) >= 2000 and int(addr[3]) <= 2006 ):
        newm=struct.pack(">BBhh",int(addr[2]),6,int(addr[3]),int(msg.payload))
        writemsg=newm
    else:
        _logger.error(f"Write request outside safe range(0x2000-0x2006) msg.topic={msg.topic} msg.payload={msg.payload}")

# Initialize and connect to the MQTT broker with authentication
from mqtt_setup import init_mqtt

mqtt_client = init_mqtt()



# 🔽 Вставь сюда ↓↓↓
import os
import json
import re

def sanitize_topic(topic):
    return topic.replace("/", "_").replace("+", "_").replace("#", "_")

def is_valid_sensor_line(parts):
    if len(parts) < 4:
        return False
    topic, name, unit, device_class = parts[:4]
    if "+" in topic or "#" in topic:
        print(f"⚠️ Пропущено: недопустимый символ в topic → {topic}")
        return False
    if not topic or not name or not unit or not device_class:
        print(f"⚠️ Пропущено: неполная строка → {' '.join(parts)}")
        return False
    return True

def publish_discovery(client, topic, name, unit, device_class):
    sensor_id = sanitize_topic(topic)
    discovery_topic = f"homeassistant/sensor/{sensor_id}/config"
    payload = {
        "name": name,
        "state_topic": topic,
        "unit_of_measurement": unit,
        "value_template": "{{ value_json[0] }}",
        "unique_id": sensor_id,
        "device_class": device_class,
        "device": {
            "identifiers": ["ghp_device"],
            "name": "GHP System"
        }
    }
    client.publish(discovery_topic, json.dumps(payload), retain=True)
    print(f"📤 Discovery опубликован: {discovery_topic}")

import yaml
import os
import json
import paho.mqtt.client as mqtt

import os
import yaml
from mqtt_setup import init_mqtt

BASE_DIR = os.path.dirname(__file__)
yaml_path = os.path.join(BASE_DIR, "hass-sensors.yaml")

try:
    with open(yaml_path, "r") as f:
        sensors = yaml.safe_load(f)
except FileNotFoundError:
    print(f"❌ YAML-файл не найден: {yaml_path}")
    sensors = {}

#mqtt_client = init_mqtt()

# Обработка всех сенсоров по доменам
for domain in ["sensor", "binary_sensor", "select", "number", "switch"]:
    items = sensors.get(domain, [])
    if not isinstance(items, list):
        print(f"⚠️ Пропускаю {domain}: не список → {type(items)}")
        continue
    for i, sensor in enumerate(items):
        if not isinstance(sensor, dict):
            print(f"⚠️ Пропускаю элемент #{i} в {domain}: не словарь → {sensor} ({type(sensor)})")
            continue

        try:
            platform = domain
            name = sensor["name"]
            topic = sensor["state_topic"]
            unique_id = sensor.get("unique_id", name.replace(" ", "_"))
            device = sensor.get("device", {})
            device_name = device.get("name", "GHP-MM08")
            device_id = device.get("identifiers", "ghp-mm08")

            config_topic = f"homeassistant/{platform}/{unique_id}/config"

            config_payload = {
                "name": name,
                "state_topic": topic,
                "unique_id": unique_id,
                "device": {
                    "name": device_name,
                    "identifiers": [device_id]
                }
            }

            # Дополнительные поля по типу сенсора
            if platform == "sensor":
                config_payload.update({
                    "unit_of_measurement": sensor.get("unit_of_measurement", ""),
                    "device_class": sensor.get("device_class", ""),
                    "value_template": sensor.get("value_template", "{{ value }}")
                })

            elif platform == "binary_sensor":
                config_payload.update({
                    "device_class": sensor.get("device_class", ""),
                    "payload_on": sensor.get("payload_on", "ON"),
                    "payload_off": sensor.get("payload_off", "OFF")
                })

            elif platform == "switch":
                config_payload.update({
                    "command_topic": sensor.get("command_topic"),
                    "payload_on": sensor.get("payload_on", "ON"),
                    "payload_off": sensor.get("payload_off", "OFF"),
                    "state_on": sensor.get("state_on", "ON"),
                    "state_off": sensor.get("state_off", "OFF")
                })

            elif platform == "number":
                config_payload.update({
                    "command_topic": sensor.get("command_topic"),
                    "min": sensor.get("min", 0),
                    "max": sensor.get("max", 100),
                    "step": sensor.get("step", 1),
                    "unit_of_measurement": sensor.get("unit_of_measurement", "")
                })

            elif platform == "select":
                config_payload.update({
                    "command_topic": sensor.get("command_topic"),
                    "options": sensor.get("options", [])
                })

            mqtt_client.publish(config_topic, json.dumps(config_payload), retain=True)
            print(f"✅ Discovery опубликован: {platform} → {name}")

        except Exception as e:
            print(f"❌ Ошибка при обработке {domain} → {sensor.get('name', 'без имени')}: {e}")



# Далее — основной цикл обработки данных

buffer=bytearray(0)
readAddr=0


# Check if the port is open
if ser.is_open:
    _logger.info(f"Serial port {ser.port} opened successfully!")
    ser.reset_input_buffer()
#print(f"✅ Последовательный порт {ser.port} открыт успешно!")
print("🚀 Скрипт запущен. Ожидаю данные от порта...")

mqtt_client.loop_start()

try:
    while True:
        data = ser.read(1)
        data += ser.read(ser.inWaiting())
        if data:
            print(f"📥 Принято: {data.hex()}")
            buffer += data
            decodeModbus()
        else:
            print("⏳ Нет данных.")
            _logger.warning("No data received.")
        time.sleep(0.3)

except KeyboardInterrupt:
    print("🛑 Прерывание: выход из программы...")
    _logger.info("Exiting program...")

finally:
    print("🔌 Порт и MQTT-соединение закрыты.")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    ser.close()
    _logger.info("Serial port and MQTT connection closed.")