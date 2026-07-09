import paho.mqtt.client as mqtt
import time
import json
import dotenv
import os
import random
import concurrent.futures

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
        client_id = getattr(client, "_client_id", "mqtt_client")
        if isinstance(client_id, bytes):
            client_id = client_id.decode(errors='ignore')
        if rc == 0:
            print(f"[{client_id}] Connected to MQTT Broker!")
        else:
            print(f"[{client_id}] Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        client_id = getattr(client, "_client_id", "mqtt_client")
        if isinstance(client_id, bytes):
            client_id = client_id.decode(errors='ignore')
        print(f"[{client_id}] Disconnected from MQTT Broker")

    def _create_client(self, client_id):
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
        except AttributeError:
            client = mqtt.Client(client_id)
        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.connect(self.mqtt_broker, self.mqtt_port, 60)
        client.loop_start()
        return client

    
    # Parallel loop tasks
    def run_data_loop(self, msg_round, qty_topic):
        client = self._create_client("mqtt_pub_data")
        try:
            msg_loop = 1
            for i in range(1, msg_round + 1):
                print(f"[Data] Publishing round {i}/{msg_round}...")
                message_data = {f"data{k}": msg_loop for k in range(1, 6)}
                message_data["model"] = "A"
                for j in range(1, qty_topic + 1):
                    topic = f"{self.topic_name1}no_{j}"
                    client.publish(topic, json.dumps(message_data))
                msg_loop += 1
                time.sleep(5)
        finally:
            client.loop_stop()
            client.disconnect()

    def run_status_loop(self, msg_round, qty_topic):
        client = self._create_client("mqtt_pub_status")
        status_list = ["run","alarm","stop","wait"]
        try:
            for i in range(1, msg_round + 1):
                print(f"[Status] Publishing round {i}/{msg_round}...")
                for j in range(1, qty_topic + 1):
                    status = random.choice(status_list)
                    message_status = {"status": status}
                    topic = f"{self.topic_name2}no_{j}"
                    client.publish(topic, json.dumps(message_status))
                time.sleep(30)
        finally:
            client.loop_stop()
            client.disconnect()

    def run_alarm_loop(self, msg_round, qty_topic):
        client = self._create_client("mqtt_pub_alarm")
        try:
            for i in range(1, msg_round + 1):
                print(f"[Alarm] Publishing round {i}/{msg_round}...")
                alarm_name = f"alarm_{random.randrange(1,5)}"
                message_alarm = {"status": alarm_name}
                for j in range(1, qty_topic + 1):
                    topic = f"{self.topic_name3}no_{j}"
                    client.publish(topic, json.dumps(message_alarm))
                time.sleep(30.0)

                message_alarm_closed = {"status": f"{alarm_name}_"}
                for j in range(1, qty_topic + 1):
                    topic = f"{self.topic_name3}no_{j}"
                    client.publish(topic, json.dumps(message_alarm_closed))
                time.sleep(1)
        finally:
            client.loop_stop()
            client.disconnect()

    def run_esp32_loop(self, msg_round, qty_topic):
        client = self._create_client("mqtt_pub_esp32")
        try:
            for i in range(1, msg_round + 1):
                print(f"[ESP32] Publishing round {i}/{msg_round}...")
                for j in range(1, qty_topic + 1):
                    mac_id = f"mac-{random.randrange(10)}"
                    message_esp32 = {
                        "broker": 1,
                        "modbus": 1,
                        "mac_id": mac_id
                    }
                    topic = f"{self.topic_name4}no_{j}"
                    client.publish(topic, json.dumps(message_esp32))
                time.sleep(300)
        finally:
            client.loop_stop()
            client.disconnect()

    def run(self, msg_round,qty_topic):
        print(f"Starting parallel MQTT simulation for {msg_round} rounds...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self.run_data_loop, msg_round, qty_topic),
                executor.submit(self.run_status_loop, msg_round, qty_topic),
                executor.submit(self.run_alarm_loop, msg_round, qty_topic),
                executor.submit(self.run_esp32_loop, msg_round, qty_topic)
            ]
            concurrent.futures.wait(futures)
        print("Parallel MQTT simulation completed!")

if __name__ == "__main__":
    publisher = MQTTPublish()
    publisher.run(10,100)