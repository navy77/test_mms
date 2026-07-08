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
* **`03-RedisKafka/`** : สารบรรณ Agent ที่ทำหน้าที่ดึงข้อมูลจาก Redis ส่งต่อให้ Kafka 
* **`04-KafkaClickHouse/`** : สารบรรณ Agent ที่ทำหน้าที่ดึงข้อมูลจาก Kafka และบันทึกลง ClickHouse
* **`05-DeviceChecker/`** : สารบรรณของตรวจสอบสถานะอุปกรณ์ว่า online หรือ offline และบันทึกลง Clickhouse
* **`06-Dashboard/`** : สารบรรณ สร้าง frontend ,backend ของ web dashboard เพื่อใช้ input clickhouse user_register_tb,device_register_tb,columns_register_tb
* **`07-API/`** : สารบรรณของ API Service ที่แบ่งแยกการทำงานเป็น Server-Sent Events (SSE) ดึงข้อมูลจาก Redis และ REST API ดึงข้อมูลจาก ClickHouse
* **`08-ScriptStorage/`** : สารบรรณของ Python Aggregation Script ที่จะประมวลผลข้อมูลส่งไป PostgreSQL
---

## 🛠️ Agents Detail & Code Specification (Python Class Style)

เพื่อประสิทธิภาพสูงสุด ทุก Agent จะถูกเขียนขึ้นด้วยภาษา Python โดยออกแบบในรูปแบบ **Class-based Object Oriented (OOP)** และใช้ไลบรารีประเภท Asynchronous หรือ High-throughput Client

### 1. tools (`01-tools`)
* **หน้าที่:** บริหารจัดการโครงสร้างพื้นฐาน (Docker Compose สำหรับ MQTT, Redis, Kafka, ClickHouse, Postgres)

### 2. MqttToRedisAgent (`02-MqttRedis`)
* **หน้าที่:** ทำหน้าที่เป็น Subscriber คอยฟังข้อมูลจาก MQTT Broker จากนั้นบันทึกข้อมูลลง Redis ในลักษณะ In-Memory Buffer อย่างรวดเร็ว เพื่อไม่ให้เกิดคอขวด (Bottleneck) 
ที่ MQTT โดยจะอ่านไฟลล์ .env เกี่ยวกับ brokers,port
example topic : data/div/process/##,status/div/process/##,alarm/div/process/##,mqtt/div/process/##

* **Docker Service:** `mqtt-redis`
* **Benthos Configuration:**
    ```yaml
    input:
      batched:
        child:
          mqtt:
            urls: ["tcp://${MQTT_BROKER:localhost}:${MQTT_PORT:1883}"]
            topics: ["data/#", "status/#", "alarm/#", "mqtt/#"]
            client_id: "agent-mqtt-redis-benthos"
        policy:
          count: 5000
          period: 1s

    pipeline:
      processors:
        - mapping: |
            root.topic = meta("mqtt_topic")
            root.div = meta("mqtt_topic").split("/").index(1).catch("")
            root.process = meta("mqtt_topic").split("/").index(2).catch("")
            root.device = meta("mqtt_topic").split("/").index(3).catch("")
            root.payload = content().string()
            root.timestamp = now()

    output:
      broker:
        pattern: fan_out
        outputs:
          # Branch 1: Push JSON serialized message to Redis Queue (RPUSH)
          - redis_list:
              url: "redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}"
              key: "${REDIS_QUEUE_KEY:mqtt_queue}"

          # Branch 2: Update real-time tracking Redis Hash (HSET)
          - drop: {}
            processors:
              - redis:
                  url: "redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}"
                  command: hset
                  args_mapping: |
                    root = [
                      "rt_" + meta("mqtt_topic").split("/").index(0).catch("mqtt"),
                      meta("mqtt_topic"),
                      content().string()
                    ]
    ```

### 3. RedisToKafkaAgent (`03-RedisKafka`)
* **หน้าที่:** ทำหน้าที่ Pop ข้อมูลออกจาก Redis Queue อย่างรวดเร็ว แล้วทำการ Publish ข้อมูลกระจายส่งต่อไปยัง Apache Kafka Topic ที่กำหนด เพื่อรองรับการทำ Scalability
โดยจะอ่านไฟลล์ .env เกี่ยวกับ brokers,port
example topic : data/div/process/##,status/div/process/##,alarm/div/process/##
บันทึก 1 partition ต่อ process
* **Docker Service:** `redis-kafka`
* **Benthos Configuration:**
    ```yaml
    input:
      redis_list:
        url: "redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}"
        key: "${REDIS_QUEUE_KEY:mqtt_queue}"

    pipeline:
      processors:
        - mapping: |
            let topic = json("topic").catch("")
            let category = $topic.split("/").index(0).catch("default")
            
            let partition = match $category {
              "data" => 0,
              "status" => 1,
              "alarm" => 2,
              "mqtt" => 3,
              _ => 0
            }
            
            meta kafka_topic = $category
            meta kafka_partition = $partition.string()
            
            root.topic = $topic
            root.process = json("process").catch("")
            root.device = json("device").catch("")
            root.payload = json("payload").catch("")
            root.timestamp = json("timestamp").catch(now())

    output:
      kafka:
        addresses: [ "${KAFKA_BOOTSTRAP_SERVERS:localhost:29092}" ]
        topic: "${! meta(\"kafka_topic\") }"
        partitioner: manual
        partition: "${! meta(\"kafka_partition\") }"
        batching:
          count: 1000
          period: 20ms
    ```


### 4. KafkaToClickhouseAgent (`04-KafkaClickhouse`)
* **หน้าที่:** ทำหน้าที่ Pop ข้อมูลออกจาก Kafka Topic อย่างรวดเร็ว แล้วทำการบันทึกข้อมูลลง ClickHouse DB
โดยจะอ่านข้อมูลจาก topics `data`, `status`, `alarm` และบันทึกลงตารางที่เกี่ยวข้องแบบ Batch
* **Docker Service:** `kafka-clickhouse`
* **Benthos Configuration:**
    ```yaml
    input:
      kafka:
        addresses: ["kafka:9092"]
        topics: ["data", "status", "alarm"]
        consumer_group: "benthos_clickhouse_group"
        start_from_oldest: true
        batching:
          period: 2s
          byte_size: 5000000

    output:
      switch:
        cases:
          - check: meta("kafka_topic") == "status"
            output:
              sql_insert:
                driver: clickhouse
                dsn: clickhouse://default:maibok@clickhouse:9000/default
                table: status_tb
                columns: [- process, - device, - status]
                args_mapping: |
                  root = [ 
                    this.process,
                    this.device,
                    this.payload.parse_json().catch({"status": this.payload}).status
                  ]
                batching:
                  count: 10000
                  period: 10s

          - check: meta("kafka_topic") == "alarm"
            output:
              sql_insert:
                driver: clickhouse
                dsn: clickhouse://default:maibok@clickhouse:9000/default
                table: alarm_tb
                columns: [- process, - device, - status]
                args_mapping: |
                  root = [ 
                    this.process,
                    this.device,
                    this.payload.parse_json().catch({"status": this.payload}).status
                  ]
                batching:
                  count: 10000
                  period: 10s

          - check: meta("kafka_topic") == "data"
            output:
              sql_insert:
                driver: clickhouse
                dsn: clickhouse://default:maibok@clickhouse:9000/default
                table: data_tb
                columns: [- process, - device, - data1, - data2, - data3, - data4, - data5]
                args_mapping: |
                  root = [ 
                    this.process,
                    this.device,
                    this.payload.parse_json().catch({}).data1.number().catch(0.0),
                    this.payload.parse_json().catch({}).data2.number().catch(0.0),
                    this.payload.parse_json().catch({}).data3.number().catch(0.0),
                    this.payload.parse_json().catch({}).data4.number().catch(0.0),
                    this.payload.parse_json().catch({}).data5.number().catch(0.0)
                  ]
                batching:
                  count: 10000
                  period: 10s
    ```

### 5. DeviceChecker (`05-DeviceChecker`)
* **หน้าที่:** ดึงข้อมูลจาก Redis hash 'rt_mqtt' ที่เก็บข้อมูลล่าสุดของแต่ละอุปกรณ์ จากนั้นตรวจสอบว่าข้อมูลล่าสุดของแต่ละอุปกรณ์คือช่วงเวลาเท่าไหร่ ถ้าเกิน X second ให้ส่ง MQTT offline เข้า topic status/div/##
* **Docker Service:** `agent-python-devicechecker`
* **โครงสร้างคลาสต้นแบบ (Python Class Concept):**
    ```python
    import clickhouse_connect

    class DeviceChecker:
        def __init__(self, ch_host, pg_host):

        def check_device(self):
            # 1. Query ข้อมูลล่าสุดจาก redis 'rt_mqtt' hash
            # 2. ตรวจสอบ timestamp เทียบกับ now ต้องไม่เกิน x second 
            # 3. ถ้าเกิน(offline) ส่ง mqtt topic ใน .env ว่า {"status":offline} 
            # 4 บันทึกลง clickhouse table device_tb โดยแตาละรอบให้ดึงข้อมมูลจาก device_register_tb มาอ้างอิง เช่น
            # device process status broker modbus mac_id status,
            #  ข้อมูลดึงมาจาก redis = {"topic": "mqtt/mic/demo1/no_854", "process": "demo1", "device": "no_854", "payload": "{\"broker\": 1, \"modbus\": 1, \"mac_id\": \"mac-2\"}", "timestamp": "2026-07-03T14:56:49.417961"}

            
        def run_schedule(self):
            # ตั้งเวลาให้รันทุกๆ X นาที
            pass
    ```

### 6. Dashboard (`06-Dashboard`)
* **หน้าที่:** backend: fastapi เพื่อรับข้อมูลจาก frontend ผ่าน API โดยมามันทึกลง clichouse table user_register_tb,device_register_tb,columns_register_tb โดยสามาร create,update,delete ข้อมูลในตารางทั้งสาม

* **หน้าที่:** Frontend: โดยใช้ Sveltekit+shadcn (npx shadcn-svelte init --preset bMTlT9ESW) style minimal iot dashboard
*** ไม่ใช้ cdn เด็ดขาด เนื่องจาก offline****
1.สร้าง ui ลักษณะ dashboard มี sidebar = [home,production,machine status,alarm status,device status,setting]
  1.1 home = แสดงภาพรวมของข้อมูลทั้งหมด
  1.2 production = แสดงข้อมูลการผลิต
  1.3 machine status = แสดงสถานะของเครื่องจักร
  1.4 alarm status = แสดงสถานะของ alarm
  1.5 device status = แสดงสถานะของ device
  1.6 setting = แสดงการตั้งค่าสร้าง ui ลักษณะ wizard setup โดยสร้างผ่าน API โดยมามันทึกลง clichouse table user_register_tb,device_register_tb,columns_register_tb โดยสามาร create,update,delete ข้อมูลในตารางทั้งสาม




* **Docker Service:** `agent-dashboard`
* **โครงสร้างคลาสต้นแบบ (Python Class Concept):**


### 7. APIService (`07-API`)
* **หน้าที่:** ให้บริการ API สำหรับระบบเพื่อนำข้อมูลไปแสดงผลแบบ Real-time และเรียกดูประวัติ โดยแบ่งออกเป็น:
  1. **Server-Sent Events (SSE):** เชื่อมต่อกับ **Redis** เพื่อสร้าง Stream ข้อมูลแบบ Real-time ดึงข้อมูลสถานะหรือข้อมูลดิบล่าสุดส่งไปให้ Client (Frontend) ทันทีที่มีการเปลี่ยนแปลง
  2. **REST API:** เชื่อมต่อกับ **ClickHouse** เพื่อค้นหาและดึงข้อมูลประวัติย้อนหลัง (Historical Data) ตามช่วงเวลาและพารามิเตอร์ที่ต้องการ
* **โครงสร้างต้นแบบโฟลเดอร์ (FastAPI Folder Structure):**
    ```text
    07-API/
    ├── sse/
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   ├── .env
    │   ├── main.py
    │   ├── database.py
    │   ├── models.py
    │   └── routers/
    │       ├── __init__.py
    │       └── stream.py
    └── rest/
        ├── Dockerfile
        ├── requirements.txt
        ├── .env
        ├── main.py
        ├── database.py
        ├── models.py
        └── routers/
            ├── __init__.py
            ├── data.py
            ├── status.py
            ├── alarm.py
            ├── device.py
    ```

* **รายละเอียดไฟล์ต้นแบบแต่ละส่วน:**

  * **`database.py` (จัดการการเชื่อมต่อฐานข้อมูล)**
    ```python
    import os
    import redis
    import clickhouse_connect

    redis_host = os.getenv("REDIS_HOST", "redis")
    ch_host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    ch_user = os.getenv("CLICKHOUSE_USER", "default")
    ch_pass = os.getenv("CLICKHOUSE_PASSWORD", "maibok")
    ch_db = os.getenv("CLICKHOUSE_DATABASE", "default")

    # เชื่อมต่อ Redis และ ClickHouse
    redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
    ch_client = clickhouse_connect.get_client(
        host=ch_host, 
        port=8123,
        username=ch_user,
        password=ch_pass,
        database=ch_db
    )
    ```

  * **`models.py` (โมเดลโครงสร้างข้อมูล / Schema)**
    ```python
    from pydantic import BaseModel
    from typing import List, Any

    class DataResponse(BaseModel):
        device: str
        data: List[Any]
    ```

  ** `routers/data.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "data_tb")**
     ** การคำนวนวันจะเริ่มที่ 7:00 - 6:59 ของอีกวัน ต้องระวังวันที่ด้วย ช่วงหลัง 00:00-6:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันก่อนหน้ามา 1 วัน เช่น วันที่ 2026-07-03 00:00:00 - 06:59:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันที่ 2026-07-02
      แบ่งเป็น api ย่อย
      - /api/v1/data/hourly/{process}  # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/data/hourly/{process}/{device} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/data/daily/{process} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/data/daily/{process}/{device} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/data/monthly/{year}/{month}/{process}
      - /api/v1/data/monthly/{year}/{month}/{process}/{device}
    ```

  ** `routers/status.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "status_tb")**
     ** การคำนวนวันจะเริ่มที่ 7:00 - 6:59 ของอีกวัน ต้องระวังวันที่ด้วย ช่วงหลัง 00:00-6:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันก่อนหน้ามา 1 วัน เช่น วันที่ 2026-07-03 00:00:00 - 06:59:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันที่ 2026-07-02

     โดยส่งเป็น duration ของ status และ time_start และ time_end
      - /api/v1/status/currently/{process} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/status/currently/{process}/{device} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/status/daily/{process} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/status/daily/{process}/{device} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/status/monthly/{year}/{month}/{process}
      - /api/v1/status/monthly/{year}/{month}/{process}/{device}
    ```

  ** `routers/alarm.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "alarm_tb")**
     ** การคำนวนวันจะเริ่มที่ 7:00 - 6:59 ของอีกวัน ต้องระวังวันที่ด้วย ช่วงหลัง 00:00-6:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันก่อนหน้ามา 1 วัน เช่น วันที่ 2026-07-03 00:00:00 - 06:59:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันที่ 2026-07-02
     โดยส่งเป็น duration ของ status และ time_start และ time_end
      - /api/v1/alarm/currently/{process} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/alarm/currently/{process}/{device} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/alarm/daily/{process} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/alarm/daily/{process}/{device} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/alarm/monthly/{year}/{month}/{process}
      - /api/v1/alarm/monthly/{year}/{month}/{process}/{device}
    ```
  ** `routers/device.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "device_tb")**
     ** การคำนวนวันจะเริ่มที่ 7:00 - 6:59 ของอีกวัน ต้องระวังวันที่ด้วย ช่วงหลัง 00:00-6:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันก่อนหน้ามา 1 วัน เช่น วันที่ 2026-07-03 00:00:00 - 06:59:59 ของอีกวัน ให้ใช้การคำนวนเป็นวันที่ 2026-07-02
     โดยส่งเป็น duration ของ status และ time_start และ time_end
      - /api/v1/device/currently/{process} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/device/currently/{process}/{device} # เริ่ม7:00 ถึงชั่วโมงล่าสุด
      - /api/v1/device/daily/{process} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/device/daily/{process}/{device} # เริ่มวันที่ 1 ของ เดือนที่เรียก API
      - /api/v1/device/monthly/{year}/{month}/{process}
      - /api/v1/device/monthly/{year}/{month}/{process}/{device}
    ```

  ** `routers/stream.py` (SSE API: ดึงข้อมูล Real-time จาก Redis)**
    ```python
    import asyncio
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse
    from database import redis_client

    router = APIRouter(prefix="/api/v1", tags=["Stream"])

    @router.get("/stream")
    async def stream_realtime(channel: str):
        async def event_generator():
            pubsub = redis_client.pubsub()
            pubsub.subscribe(channel)
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    yield f"data: {message['data']}\n\n"
                await asyncio.sleep(0.1)
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    ```

  * **`main.py` (จุดเริ่มทำงานของระบบ)**
    ```python
    from fastapi import FastAPI
    from routers import history, stream

    app = FastAPI(title="MMS Data API Service")

    # นำ Router มารวมเข้าด้วยกัน
    app.include_router(history.router)
    app.include_router(stream.router)
    ```


### 8. DataAggregatorAgent (`08-ScriptStorage`)
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
5. **Benthos** จะเข้ามาทำหน้าที่เป็นตัวกลางในการรับข้อมูลจาก Kafka และบันทึกลง ClickHouse โดยตรง ทำให้ไม่ต้องเขียน Python Script แยกต่างหากสำหรับ Agent ตัวนี้
6. **DeviceChecker** การปรับเปลี่ยนนี้ช่วยให้ Agent สามารถจัดการสถานะ Online/Offline ของอุปกรณ์ได้แม่นยำยิ่งขึ้น ด้วยการตรวจจับข้อมูลที่ผิดปกติ (เช่น Timestamp ขาดหาย) และส่งสถานะ Offline กลับไปยัง MQTT พร้อมทั้งบันทึกลงฐานข้อมูล ClickHouse เพื่อการวิเคราะห์ย้อนหลัง
7. **DataAggregatorAgent** การปรับเปลี่ยนนี้จะทำให้ Agent สามารถคำนวณค่าทางสถิติจากข้อมูลดิบใน ClickHouse (เช่น ค่าเฉลี่ย, ผลรวม, จำนวนครั้ง) และบันทึกผลลัพธ์ลงใน **PostgreSQL** ซึ่งมักจะถูกใช้เป็นฐานข้อมูลหลักสำหรับแอปพลิเคชันเว็บหรือแดชบอร์ด
8. **log** ทุก process จะเก็บ log ไว้ที่ `/var/log/apps/` folder ในแต่ละ process เพื่อให้สามารถตรวจสอบ log ได้ง่าย และใช้ TZ=Asia/Bangkok
9. **time zone** ทุก process จะใช้ TZ=Asia/Bangkok และ clickhouse ใช้ UTC+7