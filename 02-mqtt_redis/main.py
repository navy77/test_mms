from gmqtt import Client as MQTTClient
import os,asyncio,json,logging
import dotenv
from redis import Redis
from queue import Queue
from threading import Thread
from datetime import datetime

class MQTTRedisBridge:
    def __init__(self):
        dotenv.load_dotenv()
        self.redis_client = Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"), 
            port=int(os.getenv("REDIS_PORT", 6379))
        )

        self.client_id = "mqttRedisBridge"
        self.client = MQTTClient(self.client_id)
        self.client.set_config({'reconnect_retries': 10, 'reconnect_delay': 10})
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        self.mqtt_broker = os.getenv("MQTT_BROKER", "127.0.0.1")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))   
        
        # Parse subscription topics from .env or fallback to defaults
        sub_topics = os.getenv("MQTT_SUB_TOPIC")
        if sub_topics:
            self.topics = [t.strip().strip("'\"") for t in sub_topics.split(",") if t.strip()]
        else:
            self.topics = ['data/#', 'status/#', 'alarm/#', 'mqtt/#']

        self.queue = Queue(maxsize = 500000)
        self.redis_queue_key = os.getenv("REDIS_QUEUE_KEY", "mqtt_queue")
        self.redis_queue_max_len = int(os.getenv("REDIS_QUEUE_MAX_LEN", 500000))
        # Start the queue processing thread
        Thread(target=self.process_queue,daemon=True).start()

    async def connect(self):
        await self.client.connect(self.mqtt_broker,self.mqtt_port)

    def on_connect(self, client, flags, rc, properties):
        if rc == 0:
            print("Connected to MQTT Broker")
            for topic in self.topics:
                self.client.subscribe(topic)
                print(f"Subscribed to topic: {topic}")
        else:
            print(f"Connection failed with code {rc}")

    def on_message(self, client, topic, payload, qos, properties):
        try:
            topic = topic
            data = payload
            self.queue.put_nowait((data,topic))
        except Exception as e:
            logging.error(f"Error on_message: {e}")

    def on_disconnect(self, client, packet, exc=None):
        print('Disconnected from MQTT Broker')

    def process_queue(self):
        while True:
            data, topic = self.queue.get()
            try:
                # Decode bytes payload to string safely
                try:
                    payload_str = data.decode('utf-8')
                except Exception:
                    payload_str = str(data)

                # Prepare the payload with metadata
                message_data = {
                    "topic": topic,
                    "payload": payload_str,
                    "timestamp": datetime.now().isoformat()
                }

                # Push the JSON serialized message to the central Redis queue and trim
                pipe = self.redis_client.pipeline()
                pipe.rpush(self.redis_queue_key, json.dumps(message_data))
                pipe.ltrim(self.redis_queue_key, -self.redis_queue_max_len, -1)
                pipe.execute()
            except Exception as e:
                logging.error(f"Error processing queue: {e}")
            finally:
                self.queue.task_done()

    async def start(self):
        await self.connect()
        self.stop_event = asyncio.Event()
        try:
            await self.stop_event.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await self.client.disconnect()
            print("Disconnected from MQTT Broker cleanly")

async def main():
    mqtt_client = MQTTRedisBridge()
    await mqtt_client.start()

if __name__ == "__main__":
    asyncio.run(main())