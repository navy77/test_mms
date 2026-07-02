# 🤖 Project Agents & Data Pipeline Specification

เอกสารฉบับนี้อธิบายรายละเอียดการทำงานของ Agents แต่ละตัวในระบบ Pipeline ข้อมูล ซึ่งออกแบบมาเพื่อรองรับ Load ระดับ **1,000 messages/second** ทุกส่วนทำงานอยู่บน **Docker Container** และขับเคลื่อนด้วยระบบ **Event-Driven Architecture**

---

## 🏗️ Data Pipeline Architecture

ระบบส่งต่อข้อมูลตามลำดับโครงสร้าง Pipeline ดังนี้:
`MQTT Broker` ➡️ `Redis (Buffer)` ➡️ `Apache Kafka` ➡️ `ClickHouse (OLAP)` ➡️ `Python Aggregator` ➡️ `PostgreSQL (App DB)`
โดยทุก service ต้องมี file .log
---

## 📂 Project Folder Structure

โปรเจกต์นี้แบ่งสัดส่วนการพัฒนาและ Deploy ออกเป็น 4 ส่วนหลัก:
* **`01-tools/`** : บริหารจัดการโครงสร้างพื้นฐาน (Docker Compose สำหรับ MQTT, Redis, Kafka, ClickHouse, Postgres)
* **`02-MqttRedis/`** : สารบรรณ Agent ที่ทำหน้าที่ดึงข้อมูลจาก MQTT มาใส่ใน Redis
* **`03-RedisKafka/`** : สารบรรณ Agent ที่ทำหน้าที่ดึงข้อมูลจาก Redis ส่งต่อให้ Kafka และดันเข้า ClickHouse
* **`04-ScriptStorage/`** : สารบรรณของ Python Aggregation Script ที่จะประมวลผลข้อมูลส่งไป PostgreSQL

---

## 🛠️ Agents Detail & Code Specification (Python Class Style)

เพื่อประสิทธิภาพสูงสุด ทุก Agent จะถูกเขียนขึ้นด้วยภาษา Python โดยออกแบบในรูปแบบ **Class-based Object Oriented (OOP)** และใช้ไลบรารีประเภท Asynchronous หรือ High-throughput Client

### 1. MqttToRedisAgent (`02-MqttRedis`)
* **หน้าที่:** ทำหน้าที่เป็น Subscriber คอยฟังข้อมูลจาก MQTT Broker จากนั้นบันทึกข้อมูลลง Redis ในลักษณะ In-Memory Buffer อย่างรวดเร็ว เพื่อไม่ให้เกิดคอขวด (Bottleneck) 
ที่ MQTT โดยจะอ่านไฟลล์ .env เกี่ยวกับ brokers,port
example topic : data/div/process/##,status/div/process/##,alarm/div/process/##,mqtt/div/process/##

* **Docker Service:** `agent-mqtt-redis`
* **โครงสร้างคลาสต้นแบบ (Python Class Concept):**
    ```python
    import gmqtt # แนะนำ gmqtt สำหรับ async
    import redis

    class MqttToRedisAgent:
        def __init__(self, mqtt_host, redis_host):
            self.mqtt_client = None
            self.redis_client = redis.Redis(host=redis_host, port=6379)

        def on_message(self, client, topic, payload, qos, properties):
            # บันทึกข้อมูลลง Redis (แนะนำใช้ List หรือ Stream สำหรับ Queue)
            self.redis_client.rpush("raw_data_queue", payload)

        def start(self):
            # เชื่อมต่อและเริ่มทำงาน
            pass
    ```

### 2. RedisToKafkaAgent (`03-RedisKafka`)
* **หน้าที่:** ทำหน้าที่ Pop ข้อมูลออกจาก Redis Queue อย่างรวดเร็ว แล้วทำการ Publish ข้อมูลกระจายส่งต่อไปยัง Apache Kafka Topic ที่กำหนด เพื่อรองรับการทำ Scalability
โดยจะอ่านไฟลล์ .env เกี่ยวกับ brokers,port
example topic : data/div/process/##,status/div/process/##,alarm/div/process/##,mqtt/div/process/##
บันทึก 1 partition ต่อ process
* **Docker Service:** `agent-redis-kafka`
* **โครงสร้างคลาสต้นแบบ (Python Class Concept):**
    ```python
    import time
    from confluent_kafka import Producer # แนะนำ confluent_kafka 
    import redis

    class RedisToKafkaAgent:
        def __init__(self, redis_host, kafka_brokers):
            self.redis_client = redis.Redis(host=redis_host)
            self.producer = KafkaProducer(bootstrap_servers=kafka_brokers)

        def process_pipeline(self):

    ```

*หมายเหตุ: ในส่วน `03-RedisKafka` จะมีกระบวนการดึงข้อมูลจาก Kafka เข้าไปจัดเก็บที่ **ClickHouse DB** เพื่อทำเป็นที่เก็บข้อมูลประวัติขนาดใหญ่ (Historical Data)*

### 3. DataAggregatorAgent (`04-ScriptStorage`)
* **หน้าที่:** ดึงข้อมูลดิบจาก ClickHouse (หรือดึงผ่าน Stream จาก Kafka) เพื่อนำมาคำนวณและประมวลผลลัพธ์เชิงสถิติ (เช่น การหาค่าเฉลี่ยรายนาที/รายชั่วโมง) จากนั้นจึงบันทึกผลลัพธ์สุดท้าย (Aggregated Data) ลงใน **PostgreSQL** เพื่อนำไปใช้งานบนแดชบอร์ดหรือเว็บแอปพลิเคชันต่อไป
* **Docker Service:** `agent-python-aggregator`
* **โครงสร้างคลาสต้นแบบ (Python Class Concept):**
    ```python
    import psycopg2
    from clickhouse_driver import Client

    class DataAggregatorAgent:
        def __init__(self, ch_host, pg_host):
            self.ch_client = Client(host=ch_host)
            self.pg_conn = psycopg2.connect(host=pg_host)

        def aggregate_data(self):
            # 1. Query ข้อมูลดิบจาก ClickHouse
            # 2. ทำการคำนวณทางสถิติ (Sum, Avg, Count)
            # 3. Insert/Upsert ผลลัพธ์ลง PostgreSQL
            pass
            
        def run_schedule(self):
            # ตั้งเวลาให้รันทุกๆ X นาที
            pass
    ```

---

## 🚀 Performance Tuning for 1,000 msg/sec
เพื่อให้ระบบสามารถรันบน Docker ได้โดยไม่เกิดสภาวะข้อมูลค้างค้าง (Backpressure) ควรตั้งค่าดังนี้:
1.  **Redis:** ใช้คำสั่ง `RPUSH / BLPOP` เพื่อรักษาระดับความเร็วในการเป็น Buffer
2.  **Kafka:** กำหนด `batch.size` และ `linger.ms` ใน Producer Class เพื่อให้ส่งข้อมูลเป็นชุด (Batch) แทนการส่งทีละข้อความ
3.  **ClickHouse:** เน้นการทำ Batch Insert (อย่างน้อย 10,000 แถวต่อครั้ง หรือทุกๆ 1-2 นาที) ห้ามเขียนข้อมูลแบบทีละบรรทัดเด็ดขาด
4.  **Docker Network:** ตรวจสอบให้อยู่ใน Bridge Network เดียวกันทั้งหมดใน `01-tools` เพื่อลด Network Latency