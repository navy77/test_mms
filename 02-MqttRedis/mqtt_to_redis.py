import os
import asyncio
import json
import logging
from datetime import datetime
from queue import Queue
from threading import Thread
import dotenv
from gmqtt import Client as MQTTClient
import redis

# Configure logging to write to both stdout and a local file
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log/mqtt_redis.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MqttToRedis")

class MqttToRedis:
    def __init__(self, mqtt_host, redis_host, mqtt_port=1883, redis_port=6379, redis_queue_key="raw_data_queue", redis_queue_max_len=500000, topics=None):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_queue_key = redis_queue_key
        self.redis_queue_max_len = redis_queue_max_len
        self.topics = topics or ['data/#', 'status/#', 'alarm/#', 'mqtt/#']

        # Instantiate Redis client
        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port)
        
        # Instantiate and configure MQTT client using gmqtt
        self.client_id = "agent-mqtt-redis"
        self.mqtt_client = MQTTClient(self.client_id)
        self.mqtt_client.set_config({'reconnect_retries': 10, 'reconnect_delay': 10})
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        # Internal buffer queue to prevent blocking the event loop when executing synchronous Redis commands
        self.queue = Queue(maxsize=500000)
        Thread(target=self.process_queue, daemon=True).start()

    def on_connect(self, client, flags, rc, properties):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            for topic in self.topics:
                self.mqtt_client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")

    def on_message(self, client, topic, payload, qos, properties):
        try:
            self.queue.put_nowait((payload, topic))
        except Exception as e:
            logger.error(f"Error putting message into queue: {e}")

    def on_disconnect(self, client, packet, exc=None):
        logger.info("Disconnected from MQTT Broker")

    def process_queue(self):
        logger.info("Started Redis queue writer thread")
        while True:
            try:
                payload, topic = self.queue.get()
                # Decode bytes payload to string safely
                try:
                    payload_str = payload.decode('utf-8')
                except Exception:
                    payload_str = str(payload)

                # Prepare the payload with metadata
                message_data = {
                    "topic": topic,
                    "payload": payload_str,
                    "timestamp": datetime.now().isoformat()
                }

                # Push the JSON serialized message to the Redis queue and trim
                pipe = self.redis_client.pipeline()
                pipe.rpush(self.redis_queue_key, json.dumps(message_data))
                pipe.ltrim(self.redis_queue_key, -self.redis_queue_max_len, -1)
                pipe.execute()
            except Exception as e:
                logger.error(f"Error processing and pushing queue: {e}")
            finally:
                self.queue.task_done()

    async def start(self):
        logger.info(f"Connecting to MQTT Broker at {self.mqtt_host}:{self.mqtt_port}...")
        await self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
        self.stop_event = asyncio.Event()
        try:
            await self.stop_event.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Shutdown signal received")
        finally:
            await self.mqtt_client.disconnect()
            logger.info("Disconnected from MQTT Broker cleanly")

async def main():
    dotenv.load_dotenv()
    mqtt_host = os.getenv("MQTT_BROKER", "127.0.0.1")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    # Read the queue key, falling back to what's defined in dotenv or raw_data_queue
    redis_queue_key = os.getenv("REDIS_QUEUE_KEY", "raw_data_queue")
    redis_queue_max_len = int(os.getenv("REDIS_QUEUE_MAX_LEN", 500000))
    
    sub_topics = os.getenv("MQTT_SUB_TOPIC")
    if sub_topics:
        topics = [t.strip().strip("'\"") for t in sub_topics.split(",") if t.strip()]
    else:
        topics = ['data/#', 'status/#', 'alarm/#', 'mqtt/#']

    agent = MqttToRedis(
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        redis_host=redis_host,
        redis_port=redis_port,
        redis_queue_key=redis_queue_key,
        redis_queue_max_len=redis_queue_max_len,
        topics=topics
    )
    await agent.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")