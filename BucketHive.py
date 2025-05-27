import os
import time
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import telebot
import ssl
import requests
import threading

# Configuration of OpenWeather
openweather_api_key = "621605f6709e4b872bf078e388b90547"
openweather_city = "Bologna"
openweather_url = f"http://api.openweathermap.org/data/2.5/weather?q={openweather_city}&appid={openweather_api_key}&units=metric"

# Configuration of InfluxDB
token = "BhKGw3O66v8SiOhqqwSCiGI4QMNtZisnIDW-U8d11jujIvAHjenjSY6McOX5Hsa1DyqAVLNqDQNV4Wkvq1ba4Q=="
org = "Pruebaiot"
bucket = "smarthome"
url = "https://us-east-1-1.aws.cloud2.influxdata.com"

# Configuration of MQTT
mqtt_broker = "f04812ae159847afb246837bded936cc.s1.eu.hivemq.cloud"
mqtt_port = 8883
mqtt_topic_temp = "casa/temperatura"
mqtt_topic_hum = "casa/humedad"
mqtt_topic_dist = "casa/distancia"
mqtt_topic_commands = "casa/comandos"
mqtt_topic_openweather = "casa/openweather"
mqtt_username = "emiomar"
mqtt_password = "C27emiliano$"

# Configuration of Telegram
telegram_bot_token = "7432674241:AAGRQdwSZgS9kvSUvzH7NNpWFdwUnyNroqc"
telegram_chat_id = "1129937563"
alert_sent = None ##use to know the last alert sent

# Initialization of InfluxDB Client
client_influx = InfluxDBClient(url=url, token=token, org=org)
write_api = client_influx.write_api(write_options=SYNCHRONOUS)

# Initialization of Telegram Bot
bot = telebot.TeleBot(telegram_bot_token)

def get_openweather_temperature():
    response = requests.get(openweather_url)
    data = response.json()
    return data['main']['temp'], data['main']['humidity']

def write_data(point):
    write_api.write(bucket=bucket, org=org, record=point)

def on_connect(client, userdata, flags, rc):
    client.subscribe([(mqtt_topic_temp, 0), (mqtt_topic_hum, 0), (mqtt_topic_dist, 0), (mqtt_topic_openweather, 0)])

def on_message(client, userdata, msg):
    global alert_sent
    print(msg.topic + " " + str(msg.payload.decode()))
    value = float(msg.payload.decode())
    point = Point(msg.topic.split('/')[-1]).tag("ubicacion", "casa").field("value", value).time(time.time_ns(), WritePrecision.NS)
    write_data(point)

    if msg.topic == mqtt_topic_temp:
        openweather_temp, _ = get_openweather_temperature()
        print(f"Temperatura Sensor: {value} °C, Temperatura OpenWeather: {openweather_temp} °C")
        if value < 20 and alert_sent != "Window Close":
            send_telegram_alert_temperature("Window Close")
            alert_sent = "Window Close"
        elif value > 20 and alert_sent != "Window Open":
            send_telegram_alert_temperature("Window Open")
            alert_sent = "Window Open"
    elif msg.topic == mqtt_topic_dist and value < 50:
        send_telegram_alert("¡Someone is in front of your Door!")

def send_telegram_alert(message):
    bot.send_message(telegram_chat_id, message)
    print("Mensaje de alerta enviado a Telegram")

def send_telegram_alert_temperature(message):
    bot.send_message(telegram_chat_id, message)
    print("Mensaje de alerta enviado a Telegram")

def send_mqtt_command(command):
    client.publish(mqtt_topic_commands, command)
    print(f"Comando MQTT '{command}' enviado")

#@bot.message_handler(commands=['start'])
#def send_welcome(message):
 #   bot.reply_to(message, '¡Hola! Soy tu bot de Telegram.')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    command = message.text
    if command == "0":
        send_mqtt_command("0")
        bot.reply_to(message, "Door Open")
    elif command == "1":
        send_mqtt_command("1")
        bot.reply_to(message, "Door Closed")
    else:
        bot.reply_to(message, "ERROR, UNKNOWN COMMAND")

client = mqtt.Client()
client.username_pw_set(username=mqtt_username, password=mqtt_password)
client.on_connect = on_connect
client.on_message = on_message
client.tls_set(tls_version=ssl.PROTOCOL_TLS)

def publish_openweather_temperature():
    while True:
        openweather_temp, openweather_hum = get_openweather_temperature()
        client.publish(mqtt_topic_openweather, openweather_temp)

        point_temp = Point("openweather_temperature").tag("ubicacion", "casa").field("value", openweather_temp).time(time.time_ns(), WritePrecision.NS)
        point_hum = Point("openweather_humidity").tag("ubicacion", "casa").field("value", openweather_hum).time(time.time_ns(), WritePrecision.NS)
        write_data(point_temp)
        write_data(point_hum)

        time.sleep(60)

telegram_thread = threading.Thread(target=bot.polling, args=(True,))
telegram_thread.start()

openweather_thread = threading.Thread(target=publish_openweather_temperature)
openweather_thread.start()

client.connect(mqtt_broker, mqtt_port, 60)
client.loop_forever()
