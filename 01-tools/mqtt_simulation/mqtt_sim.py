import paho.mqtt.client as mqtt
import time
import json
import dotenv
import os
import random

class MQTTPublish:
    def __init__(self):
        dotenv.load_dotenv()
        self.mqtt_broker = os.environ["MQTT_BROKER"]
        self.mqtt_port = int(os.environ["MQTT_PORT"])

        self.client_id = "mqtt_publisher"
        try:
            # For paho-mqtt >= 2.0.0
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, self.client_id)
        except AttributeError:
            # For paho-mqtt < 2.0.0
            self.client = mqtt.Client(self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        self.topic_name1 = os.environ["MQTT_PUB_TOPIC1"]
        self.topic_name2 = os.environ["MQTT_PUB_TOPIC2"]
        self.topic_name3 = os.environ["MQTT_PUB_TOPIC3"]
        self.topic_name4 = os.environ["MQTT_PUB_TOPIC4"]

        self.alarm_name = ""
        self.msg_loop = 1

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        print("Disconnected from MQTT Broker")

    def pub_data(self,topic_col,qty_topic):
        message_data={}
        for i in range(1,topic_col+1):
            key = f"data{i}"
            message_data[key] = self.msg_loop 

        for j in range(1, qty_topic+1):
            topic = f"{self.topic_name1}no_{j}"
            self.client.publish(topic, json.dumps(message_data))
        self.msg_loop +=1

    def pub_status(self,qty_topic):
        for i in range(1,qty_topic+1):
            status = f"status_{random.randrange(5)}"
            message_status = {
                "status": status
            }
            topic = f"{self.topic_name2}no_{i}"
            self.client.publish(topic, json.dumps(message_status))

    def pub_alarm(self,qty_topic):
        alarm = f"alarm_{random.randrange(10)}"
        self.alarm_name = alarm
        for i in range(1,qty_topic+1):
            message_alarm = {
                "status": self.alarm_name
            }
            topic = f"{self.topic_name3}no_{i}"
            self.client.publish(topic, json.dumps(message_alarm))

    def pub_alarm_closed(self,qty_topic):
        alarm_closed = f"{self.alarm_name}_"
        for i in range(1,qty_topic+1):
            # alarm = f"alarm_{random.randrange(10)}"
            message_alarm = {
                "status": alarm_closed
            }
            topic = f"{self.topic_name3}no_{i}"
            self.client.publish(topic, json.dumps(message_alarm))

    def pub_esp32(self,qty_topic):
        for i in range(1,qty_topic+1):
            # broker = random.randrange(2)
            broker = 1
            # modbus = random.randrange(2)
            modbus = 1
            mac_id = f"mac-{random.randrange(10)}"
            message_esp32 = {
                "broker": broker,
                "modbus": modbus,
                "mac_id": mac_id
            }
            topic = f"{self.topic_name4}no_{i}"
            self.client.publish(topic, json.dumps(message_esp32))

    def run(self,msg_round):
        self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.client.loop_start()
        try:
            for i in range(1,msg_round+1):
                print(f"Publishing round {i}/{msg_round}...")
                self.pub_data(5,1000)
                time.sleep(0.1)
                self.pub_status(1000)
                time.sleep(0.1)
                self.pub_alarm(1000)
                time.sleep(0.1)
                self.pub_esp32(1000)
                time.sleep(0.1)
                self.pub_alarm_closed(1000)
                time.sleep(0.1)
            # Give a brief moment for the messages to be sent out
            time.sleep(30)
        finally:
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    publisher = MQTTPublish()
    publisher.run(10)