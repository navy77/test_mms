import os
import sys
import json
import logging
import time
from datetime import datetime
import dotenv
import redis
import paho.mqtt.client as mqtt
import clickhouse_connect
import psycopg2

from logging.handlers import RotatingFileHandler

# Configure logging to write to both stdout and a local file
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "device_checker.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=20 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("DeviceChecker")


class DeviceChecker:
    def __init__(
        self,
        redis_host: str,
        redis_port: int,
        redis_key: str,
        mqtt_broker: str,
        mqtt_port: int,
        mqtt_status_topic: str,
        ch_host: str,
        ch_port: int,
        ch_user: str,
        ch_pass: str,
        ch_db: str,
        pg_host: str,
        pg_port: int,
        pg_user: str,
        pg_pass: str,
        pg_db: str,
        check_period: int,
    ) -> None:
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_key = redis_key
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_status_topic = mqtt_status_topic
        self.ch_host = ch_host
        self.ch_port = ch_port
        self.ch_user = ch_user
        self.ch_pass = ch_pass
        self.ch_db = ch_db
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_pass = pg_pass
        self.pg_db = pg_db
        self.check_period = check_period

        # Initialize Redis client
        logger.info(f"Connecting to Redis at {self.redis_host}:{self.redis_port}...")
        self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port)

        # Track previous status of devices to only publish when transitioning to offline
        self.last_status = {}  # key: (process, device), value: status ("online" / "offline")

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.ch_client = None
        self.pg_conn = None

    def connect_mqtt(self):
        try:
            logger.info(
                f"Connecting to MQTT Broker at {self.mqtt_broker}:{self.mqtt_port}..."
            )
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            logger.info("Connected to MQTT Broker and started background loop")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker: {e}")

    def check_device(self) -> None:
        logger.info("Starting device check round...")
        try:
            # 1. Query registered devices from PostgreSQL device_register_tb
            if self.pg_conn is None:
                logger.info(
                    f"Connecting to PostgreSQL at {self.pg_host}:{self.pg_port}..."
                )
                try:
                    self.pg_conn = psycopg2.connect(
                        host=self.pg_host,
                        port=self.pg_port,
                        user=self.pg_user,
                        password=self.pg_pass,
                        dbname=self.pg_db,
                    )
                except Exception as pg_err:
                    if self.pg_host not in ("127.0.0.1", "localhost"):
                        logger.info(
                            f"Failed to connect to PostgreSQL at '{self.pg_host}'. Trying fallback to '127.0.0.1'..."
                        )
                        self.pg_conn = psycopg2.connect(
                            host="127.0.0.1",
                            port=self.pg_port,
                            user=self.pg_user,
                            password=self.pg_pass,
                            dbname=self.pg_db,
                        )
                    else:
                        raise pg_err
            else:
                try:
                    with self.pg_conn.cursor() as cur:
                        cur.execute("SELECT 1")
                except Exception:
                    logger.info("PostgreSQL connection lost, reconnecting...")
                    try:
                        self.pg_conn.close()
                    except Exception:
                        pass
                    try:
                        self.pg_conn = psycopg2.connect(
                            host=self.pg_host,
                            port=self.pg_port,
                            user=self.pg_user,
                            password=self.pg_pass,
                            dbname=self.pg_db,
                        )
                    except Exception as pg_err:
                        if self.pg_host not in ("127.0.0.1", "localhost"):
                            logger.info(
                                f"Failed to connect to PostgreSQL at '{self.pg_host}'. Trying fallback to '127.0.0.1'..."
                            )
                            self.pg_conn = psycopg2.connect(
                                host="127.0.0.1",
                                port=self.pg_port,
                                user=self.pg_user,
                                password=self.pg_pass,
                                dbname=self.pg_db,
                            )
                        else:
                            raise pg_err

            with self.pg_conn.cursor() as cur:
                cur.execute("SELECT process, device FROM device_register_tb")
                master_devices = cur.fetchall()  # list of tuples (process, device)
            logger.info(
                f"Retrieved {len(master_devices)} master devices from PostgreSQL device_register_tb"
            )
        except Exception as e:
            logger.error(f"Error querying PostgreSQL: {e}")
            return

        try:
            # 2. Get latest data from Redis hash key (default: rt_mqtt)
            redis_data = self.redis_client.hgetall(self.redis_key)

            latest_device_data = {}
            for topic_bytes, msg_bytes in redis_data.items():
                try:
                    msg = json.loads(msg_bytes.decode("utf-8"))
                    proc = msg.get("process")
                    dev = msg.get("device")
                    if proc and dev:
                        latest_device_data[(proc, dev)] = msg
                except Exception as e:
                    logger.error(f"Error parsing Redis hash entry: {e}")
        except Exception as e:
            logger.error(f"Error querying Redis: {e}")
            return

        now = datetime.now()
        data_to_insert = []

        # 3. Check status for each registered device
        for proc, dev in master_devices:
            status = "offline"
            broker = ""
            modbus = ""
            mac_id = ""

            # Look up device in Redis real-time data
            redis_entry = latest_device_data.get((proc, dev))
            if redis_entry:
                try:
                    timestamp_str = redis_entry.get("timestamp")
                    try:
                        ts = datetime.fromisoformat(timestamp_str)
                    except ValueError:
                        # Fallback for formats that might not be fully standard
                        if "." in timestamp_str:
                            ts = datetime.strptime(
                                timestamp_str.split("+")[0].split("Z")[0],
                                "%Y-%m-%dT%H:%M:%S.%f",
                            )
                        else:
                            ts = datetime.strptime(
                                timestamp_str.split("+")[0].split("Z")[0],
                                "%Y-%m-%dT%H:%M:%S",
                            )

                    if ts.tzinfo is not None:
                        diff_seconds = (datetime.now(ts.tzinfo) - ts).total_seconds()
                    else:
                        diff_seconds = (now - ts).total_seconds()

                    # Parse payload variables
                    payload_str = redis_entry.get("payload", "{}")
                    try:
                        payload_dict = json.loads(payload_str)
                    except Exception:
                        payload_dict = {}

                    broker = str(payload_dict.get("broker", ""))
                    modbus = str(payload_dict.get("modbus", ""))
                    mac_id = str(payload_dict.get("mac_id", ""))

                    if diff_seconds <= self.check_period:
                        status = "online"
                    else:
                        status = "offline"
                        broker = ""
                        modbus = ""
                        mac_id = ""
                except Exception as e:
                    logger.error(
                        f"Error checking timestamps/payloads for {proc}/{dev}: {e}"
                    )
                    status = "offline"
                    broker = ""
                    modbus = ""
                    mac_id = ""
            else:
                # Device not present in Redis at all
                status = "offline"

            # 4. If status is offline and transitioned from online/none, publish to MQTT
            prev_status = self.last_status.get((proc, dev))
            if status == "offline" and prev_status != "offline":
                # Construct topic from self.mqtt_status_topic
                if "#" in self.mqtt_status_topic:
                    topic = self.mqtt_status_topic.replace("#", f"{proc}/{dev}")
                else:
                    topic = f"{self.mqtt_status_topic}/{proc}/{dev}"
                payload = json.dumps({"status": "offline"})
                try:
                    self.mqtt_client.publish(topic, payload, qos=1, retain=True)
                    # if redis_entry is not None:
                    #     logger.info(f"Device {proc}/{dev} is OFFLINE (diff > {self.check_period}s). Published to MQTT topic: {topic}")
                    # else:
                    #     logger.info(f"Device {proc}/{dev} is OFFLINE (never seen in Redis). Published to MQTT topic: {topic}")
                except Exception as e:
                    logger.error(f"Error publishing to MQTT topic {topic}: {e}")
            elif status == "online" and prev_status == "offline":
                logger.info(f"Device {proc}/{dev} is back ONLINE.")

            # Update status map
            self.last_status[(proc, dev)] = status

            # Collect for ClickHouse insert
            data_to_insert.append([proc, dev, status, broker, modbus, mac_id])

        # 5. Insert records into ClickHouse device_tb
        if data_to_insert:
            try:
                if self.ch_client is None:
                    try:
                        self.ch_client = clickhouse_connect.get_client(
                            host=self.ch_host,
                            port=self.ch_port,
                            username=self.ch_user,
                            password=self.ch_pass,
                            database=self.ch_db,
                        )
                    except Exception as ch_err:
                        if self.ch_host not in ("127.0.0.1", "localhost"):
                            logger.info(
                                f"Failed to connect to ClickHouse at '{self.ch_host}'. Trying fallback to '127.0.0.1'..."
                            )
                            self.ch_client = clickhouse_connect.get_client(
                                host="127.0.0.1",
                                port=self.ch_port,
                                username=self.ch_user,
                                password=self.ch_pass,
                                database=self.ch_db,
                            )
                        else:
                            raise ch_err
                else:
                    try:
                        self.ch_client.command("SELECT 1")
                    except Exception:
                        logger.info(
                            "ClickHouse client connection lost, reconnecting..."
                        )
                        try:
                            self.ch_client = clickhouse_connect.get_client(
                                host=self.ch_host,
                                port=self.ch_port,
                                username=self.ch_user,
                                password=self.ch_pass,
                                database=self.ch_db,
                            )
                        except Exception as ch_err:
                            if self.ch_host not in ("127.0.0.1", "localhost"):
                                logger.info(
                                    f"Failed to connect to ClickHouse at '{self.ch_host}'. Trying fallback to '127.0.0.1'..."
                                )
                                self.ch_client = clickhouse_connect.get_client(
                                    host="127.0.0.1",
                                    port=self.ch_port,
                                    username=self.ch_user,
                                    password=self.ch_pass,
                                    database=self.ch_db,
                                )
                            else:
                                raise ch_err
                self.ch_client.insert(
                    "device_tb",
                    data_to_insert,
                    column_names=[
                        "process",
                        "device",
                        "status",
                        "broker",
                        "modbus",
                        "mac_id",
                    ],
                )
                logger.info(
                    f"Successfully inserted {len(data_to_insert)} records to ClickHouse device_tb"
                )
            except Exception as e:
                logger.error(f"Error inserting to ClickHouse table device_tb: {e}")

    def run_schedule(self):
        self.connect_mqtt()
        logger.info("Scheduler loop started...")
        while True:
            try:
                self.check_device()
            except Exception as e:
                logger.error(f"Unhandled error in check loop: {e}")

            time.sleep(self.check_period)


def main():
    env_path = dotenv.find_dotenv()
    if env_path:
        dotenv.load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded environment variables from: {env_path}")
    else:
        logger.info("No .env file found, using system environment variables")

    # Read config from environment variables
    mqtt_broker = os.getenv("MQTT_BROKER", "127.0.0.1").strip().strip("'\"")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    mqtt_status_topic = (
        os.getenv("MQTT_STATUS_TOPIC", "status/mic/#").strip().strip("'\"")
    )

    redis_host = os.getenv("REDIS_HOST", "redis").strip().strip("'\"")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_hash_key = os.getenv("REDIS_HASH_KEY", "rt_mqtt").strip().strip("'\"")

    period = int(os.getenv("PERIOD", 300))

    ch_host = os.getenv("CLICKHOUSE_HOST", "clickhouse").strip().strip("'\"")
    ch_port = int(os.getenv("CLICKHOUSE_PORT", 8123))
    ch_user = os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\"")
    ch_pass = os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\"")
    ch_db = os.getenv("CLICKHOUSE_DATABASE", "default").strip().strip("'\"")

    pg_host = os.getenv("POSTGRES_HOST", "postgres").strip().strip("'\"")
    pg_port = int(os.getenv("POSTGRES_PORT", 5432))
    pg_user = os.getenv("POSTGRES_USER", "postgres").strip().strip("'\"")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "postgres").strip().strip("'\"")
    pg_db = os.getenv("POSTGRES_DB", "iiot_db").strip().strip("'\"")

    checker = DeviceChecker(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_key=redis_hash_key,
        mqtt_broker=mqtt_broker,
        mqtt_port=mqtt_port,
        mqtt_status_topic=mqtt_status_topic,
        ch_host=ch_host,
        ch_port=ch_port,
        ch_user=ch_user,
        ch_pass=ch_pass,
        ch_db=ch_db,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_user=pg_user,
        pg_pass=pg_pass,
        pg_db=pg_db,
        check_period=period,
    )

    try:
        checker.run_schedule()
    except KeyboardInterrupt:
        logger.info("Device Checker stopped by keyboard interrupt")


if __name__ == "__main__":
    main()
