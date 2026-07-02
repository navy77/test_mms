import os
import sys
import json
import time
import logging
from datetime import datetime
import dotenv
import redis
from confluent_kafka import Producer

# Setup logging to write to both stdout and log/redis_to_kafka.log
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "redis_to_kafka.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("RedisToKafka")

class RedisToKafka:
    def __init__(self, redis_host, redis_port, redis_queue_key, kafka_brokers, kafka_topic=None):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_queue_key = redis_queue_key
        self.kafka_brokers = kafka_brokers
        self.kafka_topic = kafka_topic  # If set, all category messages go here

        logger.info(f"Initialized RedisToKafka. Target Kafka Topic override: {self.kafka_topic or 'None (using category as topic)'}")

        # Initialize Redis client
        logger.info(f"Connecting to Redis at {self.redis_host}:{self.redis_port}...")
        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port)

        # Initialize Kafka Producer with optimized settings for high-throughput (1,000 msg/s)
        logger.info(f"Connecting to Kafka at {self.kafka_brokers}...")
        conf = {
            'bootstrap.servers': self.kafka_brokers,
            'batch.size': 131072,    # 128 KB batch size
            'linger.ms': 20,         # 20 ms linger to package messages in batches
            'compression.type': 'gzip',
            'acks': 1
        }
        self.producer = Producer(conf)

    def get_partition_for_category(self, category):
        # Determine partition index based strictly on category name
        category_clean = category.strip().lower()
        if category_clean == 'data':
            return 0
        elif category_clean == 'status':
            return 1
        elif category_clean == 'alarm':
            return 2
        elif category_clean == 'mqtt':
            return 3
        else:
            # Fallback to partition 0
            return 0

    def delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")

    def process_pipeline(self):
        logger.info(f"Starting pipeline polling Redis queue: {self.redis_queue_key}")
        while True:
            try:
                # BLPOP blocks until an item is available in Redis
                result = self.redis_client.blpop(self.redis_queue_key, timeout=5)
                if not result:
                    continue

                _, payload_bytes = result
                payload_str = payload_bytes.decode('utf-8')
                
                # Parse JSON message structure from Redis
                message_data = json.loads(payload_str)
                topic = message_data.get("topic", "")
                payload = message_data.get("payload", "")
                timestamp = message_data.get("timestamp", datetime.now().isoformat())

                # Parse category and process name from MQTT topic safely
                # Example topic: data/div/process/demo1 -> category: data, process: demo1
                parts = [p.strip().strip("'\"") for p in topic.split('/') if p.strip()]
                if len(parts) >= 2:
                    category = parts[0]     # e.g., 'data', 'status', 'alarm', 'mqtt'
                    process_name = parts[-1] # e.g., 'demo1'
                else:
                    category = "default"
                    process_name = "unknown"

                # Define target Kafka topic name: use override if specified, otherwise fall back to category name
                target_topic = self.kafka_topic if self.kafka_topic else category
                
                # Get the partition index for this category
                partition = self.get_partition_for_category(category)

                # Prepare the Kafka payload containing metadata
                kafka_payload = json.dumps({
                    "topic": topic,
                    "process_name": process_name,
                    "payload": payload,
                    "timestamp": timestamp
                })

                # Publish message to Kafka on the specific partition
                self.producer.produce(
                    topic=target_topic,
                    value=kafka_payload.encode('utf-8'),
                    partition=partition,
                    callback=self.delivery_report
                )

                # Poll to trigger delivery callbacks periodically
                self.producer.poll(0)

            except Exception as e:
                logger.error(f"Error in pipeline loop: {e}")
                time.sleep(1)

def main():
    # Load .env relative to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    dotenv.load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment variables from: {env_path}")
    
    # Clean connection variables to strip any quotes inside .env
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1").strip().strip("'\"")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_queue_key = os.getenv("REDIS_QUEUE_KEY", "mqtt_queue").strip().strip("'\"")
    kafka_brokers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092").strip().strip("'\"")
    
    # Load optional single topic override name from environment
    kafka_topic = os.getenv("KAFKA_TOPIC", "").strip().strip("'\"")
    if not kafka_topic:
        kafka_topic = None

    agent = RedisToKafka(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_queue_key=redis_queue_key,
        kafka_brokers=kafka_brokers,
        kafka_topic=kafka_topic
    )
    
    try:
        agent.process_pipeline()
    except KeyboardInterrupt:
        logger.info("Agent shutting down cleanly...")

if __name__ == "__main__":
    main()
