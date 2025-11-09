import paho.mqtt.client as mqtt

# Конфигурация MQTT
MQTT_BROKER = "homeassistant"
MQTT_PORT = 1883
MQTT_USERNAME = "celiv"
MQTT_PASSWORD = "230960"

# Обработчики событий
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT: подключение успешно")
    else:
        print(f"❌ MQTT: ошибка подключения, код {rc}")

def on_disconnect(client, userdata, rc):
    print(f"⚠️ MQTT: отключено, код {rc}")

def on_message(client, userdata, msg):
    print(f"📩 MQTT сообщение: {msg.topic} → {msg.payload.decode()}")

# Функция инициализации и подключения
def init_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    return client
