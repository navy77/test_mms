# 🤖 Project Agents & Data Pipeline Specification

เอกสารฉบับนี้อธิบายรายละเอียดการทำงานของ Agents แต่ละตัวในระบบ Pipeline ข้อมูล ซึ่งออกแบบมาเพื่อรองรับ Load ระดับ **1,000 messages/second** ทุกส่วนทำงานอยู่บน **Docker Container** และขับเคลื่อนด้วยระบบ **Event-Driven Architecture**

---
## 🏗️ Data Pipeline Architecture

ระบบส่งต่อข้อมูลตามลำดับโครงสร้าง Pipeline ดังนี้:
`MQTT Broker` ➡️ `Redis (Buffer)` ➡️ `Apache Kafka` ➡️ `ClickHouse (OLAP)` ➡️ `Python Aggregator` ➡️ `PostgreSQL (App DB)`

> [!NOTE]
> ทุก Service ใน Pipeline จะต้องมีการบันทึกไฟล์ Log ในโฟลเดอร์ที่กำหนด

---

## 📂 Project Folder Structure

โปรเจกต์นี้แบ่งสัดส่วนการพัฒนาและ Deploy ออกเป็น 6 ส่วนหลัก:
* **`01-tools/`** : บริหารจัดการโครงสร้างพื้นฐาน (Docker Compose สำหรับ MQTT, Redis, Kafka, ClickHouse, PostgreSQL)
* **`02-benthos/`** : Benthos Configuration ที่ใช้สำหรับดึงข้อมูลจาก MQTT มาใส่ใน Redis, ดึงข้อมูลจาก Redis ส่งต่อให้ Kafka, และดึงข้อมูลจาก Kafka บันทึกลง ClickHouse
* **`03-DeviceChecker/`** : ตรวจสอบสถานะอุปกรณ์ว่า online หรือ offline และบันทึกลง ClickHouse
* **`04-API/`** : API Service ดึงข้อมูลประวัติย้อนหลังจาก ClickHouse โดยใช้ หลักการ batch endpoint
* **`05-Dashboard/`** : สร้าง Frontend และ Backend ของ Web Dashboard โดยใช้ PostgreSQL สำหรับเก็บข้อมูลของระบบ
* **`06-DataStorage/`** : Python Aggregation Script ที่จะประมวลผลข้อมูลจาก ClickHouse เพื่อส่งต่อไปยัง PostgreSQL โดยทำงานภายใต้ Prefect Workflow

---

## 🛠️ Agents Detail & Code Specification (Python Class Style)

เพื่อประสิทธิภาพสูงสุด ทุก Agent จะถูกเขียนขึ้นด้วยภาษา Python โดยออกแบบในรูปแบบ **Class-based Object Oriented (OOP)** และใช้ไลบรารีประเภท Asynchronous หรือ High-throughput Client

### 1. tools (`01-tools`)
* **หน้าที่:** บริหารจัดการโครงสร้างพื้นฐาน (Docker Compose สำหรับ MQTT, Redis, Kafka, ClickHouse, PostgreSQL)

### 2. benthos (`02-benthos`)
* **หน้าที่:** จัดการ Benthos Configuration สำหรับการส่งต่อข้อมูล:
  * ดึงข้อมูลจาก MQTT มาใส่ใน Redis
  * ดึงข้อมูลจาก Redis ส่งต่อให้ Kafka
  * ดึงข้อมูลจาก Kafka และบันทึกลง ClickHouse
   
### 3. DeviceChecker (`03-DeviceChecker`)
* **หน้าที่:** ดึงข้อมูลจาก Redis hash `rt_mqtt` ที่เก็บข้อมูลล่าสุดของแต่ละอุปกรณ์ จากนั้นตรวจสอบเวลาล่าสุดของแต่ละอุปกรณ์ หากไม่มีข้อมูลส่งเข้ามาเกิน 300 วินาที ให้ส่งข้อความ MQTT offline เข้าไปยัง Topic `status/div/##`

### 4. APIService (`04-API`)
* **หน้าที่:** ให้บริการ API สำหรับดึงข้อมูลเพื่อนำไปแสดงผล โดยเชื่อมต่อกับ **ClickHouse** เพื่อค้นหาและดึงข้อมูลประวัติย้อนหลัง (Historical Data) ตามช่วงเวลาและพารามิเตอร์ที่ระบุ 
โดยจะทำงานแบบ batch endpoint
* **โครงสร้างต้นแบบโฟลเดอร์ (FastAPI Folder Structure):**
    ```text
    04-API/
    ├── API_DOCUMENTION_DATA.md 
    ├── log/
    ├── pytest/
    ├── Dockerfile
    ├── requirements.txt
    ├── .env
    ├── main.py
    ├── database.py
    ├── models.py
    ├── routers/
    │   ├── __init__.py
    │   ├── data.py
    │   ├── status.py
    │   ├── alarm.py
    │   ├── device.py
    ```

  * **`routers/data.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "data_tb")**
    * **การคำนวณวัน:** เริ่มที่ 07:00 - 06:59 ของอีกวัน (ช่วงหลัง 00:00 - 06:59 ของอีกวัน ให้ใช้การคำนวณเป็นวันก่อนหน้า 1 วัน เช่น วันที่ `2026-07-03 00:00:00` - `06:59:59` ให้ถือเป็นวันที่ `2026-07-02`)
    * **แบ่งเป็น API ย่อย:**
      * `/api/v1/data/currently/{process}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/data/currently/{process}/{device}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/data/daily/{process}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/data/daily/{process}/{device}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/data/monthly/{year}/{month}/{process}`
      * `/api/v1/data/monthly/{year}/{month}/{process}/{device}`

  * **`routers/status.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "status_tb")**
    * **การคำนวณวัน:** เริ่มที่ 07:00 - 06:59 ของอีกวัน (ช่วงหลัง 00:00 - 06:59 ของอีกวัน ให้ใช้การคำนวณเป็นวันก่อนหน้า 1 วัน เช่น วันที่ `2026-07-03 00:00:00` - `06:59:59` ให้ถือเป็นวันที่ `2026-07-02`)
    * **รูปแบบข้อมูล:** ส่งเป็น duration ของ status, `time_start` และ `time_end`
    * **แบ่งเป็น API ย่อย:**
      * `/api/v1/status/currently/{process}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/status/currently/{process}/{device}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/status/daily/{process}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/status/daily/{process}/{device}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/status/monthly/{year}/{month}/{process}`
      * `/api/v1/status/monthly/{year}/{month}/{process}/{device}`

  * **`routers/alarm.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "alarm_tb")**
    * **การคำนวณวัน:** เริ่มที่ 07:00 - 06:59 ของอีกวัน (ช่วงหลัง 00:00 - 06:59 ของอีกวัน ให้ใช้การคำนวณเป็นวันก่อนหน้า 1 วัน เช่น วันที่ `2026-07-03 00:00:00` - `06:59:59` ให้ถือเป็นวันที่ `2026-07-02`)
    * **รูปแบบข้อมูล:** ส่งเป็น duration ของ status, `time_start` และ `time_end`
    * **แบ่งเป็น API ย่อย:**
      * `/api/v1/alarm/currently/{process}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/alarm/currently/{process}/{device}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/alarm/daily/{process}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/alarm/daily/{process}/{device}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/alarm/monthly/{year}/{month}/{process}`
      * `/api/v1/alarm/monthly/{year}/{month}/{process}/{device}`
    
  * **`routers/device.py` (REST API: ดึงประวัติข้อมูลจาก ClickHouse "device_tb")**
    * **การคำนวณวัน:** เริ่มที่ 07:00 - 06:59 ของอีกวัน (ช่วงหลัง 00:00 - 06:59 ของอีกวัน ให้ใช้การคำนวณเป็นวันก่อนหน้า 1 วัน เช่น วันที่ `2026-07-03 00:00:00` - `06:59:59` ให้ถือเป็นวันที่ `2026-07-02`)
    * **รูปแบบข้อมูล:** ส่งเป็น duration ของ status, `time_start` และ `time_end`
    * **แบ่งเป็น API ย่อย:**
      * `/api/v1/device/currently/{process}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/device/currently/{process}/{device}` (เริ่ม 07:00 ถึงชั่วโมงล่าสุด)
      * `/api/v1/device/daily/{process}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/device/daily/{process}/{device}` (เริ่มวันที่ 1 ของเดือนที่เรียก API)
      * `/api/v1/device/monthly/{year}/{month}/{process}`
      * `/api/v1/device/monthly/{year}/{month}/{process}/{device}`

  * **`main.py` (จุดเริ่มทำงานของระบบ)**
    ```python
    from fastapi import FastAPI
    from routers import history, stream

    app = FastAPI(title="MMS Data API Service")

    # นำ Router มารวมเข้าด้วยกัน
    app.include_router(history.router)
    app.include_router(stream.router)
    ```

### 5. Dashboard (`05-Dashboard`)
* **Backend:** พัฒนาด้วย **FastAPI** เพื่อรับข้อมูลจาก Frontend ผ่าน API
  * จัดการข้อมูลและบันทึกลงใน **PostgreSQL** รวมถึงดึงข้อมูลผ่าน API
  * สามารถจัดการข้อมูลแบบ CRUD (Create, Update, Delete) สำหรับตาราง: `user_register_tb`, `device_register_tb`, และ `columns_register_tb`
  * ให้บริการ **SSE (Server-Sent Events)** เพื่อดึงข้อมูลจาก Redis และ ClickHouse มาแสดงผลแบบ Real-time
* **Frontend:** พัฒนาด้วย **SvelteKit** + **shadcn-svelte** 
  * ใช้คำสั่งเริ่มต้นโครงการ: `npx shadcn-svelte init --preset bMTlT9ESW`
  * ออกแบบในสไตล์ Minimal IoT Dashboard
  * โครงสร้างของหน้าเว็บแยกสัดส่วนระหว่าง `+page.svelte` และ `+page.server.ts`
  * **ข้อกำหนดสำคัญ:** **ห้ามใช้ CDN เด็ดขาด เนื่องจากระบบทำงานในลักษณะ Offline**
  * **โครงสร้าง UI Dashboard:** มี Sidebar เมนูหลัก ประกอบด้วย:
    * **Home:** แสดงภาพรวมของข้อมูลทั้งหมด
    * **Production:** แสดงข้อมูลการผลิตแบบ Real-time
    * **Machine Status:** แสดงสถานะของเครื่องจักรแบบ Real-time
      * Machine Utilization Daily
      * Machine Utilization Monthly
    * **Alarm Status:** แสดงสถานะ Alarm ของเครื่องจักรแบบ Real-time
      * Alarm Ratio Daily
      * Alarm Ratio Monthly
    * **Device Status:** แสดงสถานะของ Device แบบ Real-time
      * Device Utilization Daily
      * Device Utilization Monthly
    * **Setting:** หน้าจอการตั้งค่าแบบ Wizard Setup สำหรับจัดการข้อมูล (Create, Update, Delete) ในตาราง `user_register_tb`, `device_register_tb`, และ `columns_register_tb` ผ่าน API บันทึกลงฐานข้อมูล postgresql / clickhouse (ตามการตั้งค่าสิทธิ์การลงทะเบียน)

### 6. DataAggregatorAgent (`06-DataStorage`)
* **หน้าที่:** ใช้ระบบ **Prefect Workflow** เพื่อดึงข้อมูลดิบจาก ClickHouse มาคำนวณและประมวลผลทางสถิติ (เช่น หาค่าเฉลี่ยรายนาที หรือรายชั่วโมง) แล้วบันทึกผลลัพธ์สุดท้าย (Aggregated Data) ลงไปยัง **PostgreSQL**

---

## 🚀 Performance Tuning for 1,000 msg/sec
เพื่อให้ระบบสามารถรันบน Docker ได้โดยไม่เกิดสภาวะข้อมูลค้างคา (Backpressure) ควรตั้งค่าดังนี้:
1. **Redis:** ใช้คำสั่ง `RPUSH / BLPOP` เพื่อรักษาระดับความเร็วในการเป็น Buffer ส่งต่อข้อมูล
2. **Kafka:** กำหนด `batch.size` และ `linger.ms` ใน Producer Class เพื่อให้ส่งข้อมูลเป็นชุด (Batch) แทนการส่งทีละข้อความ
3. **ClickHouse:** เน้นการทำ Batch Insert (อย่างน้อย 10,000 แถวต่อครั้ง หรือทุกๆ 1-2 นาที) ห้ามเขียนข้อมูลแบบทีละบรรทัดเด็ดขาด
4. **Docker Network:** ตรวจสอบให้อยู่ใน Bridge Network เดียวกันทั้งหมดใน `01-tools` เพื่อลด Network Latency
5. **Benthos:** ทำหน้าที่เป็นตัวกลางในการรับข้อมูลจาก Kafka และบันทึกลง ClickHouse โดยตรง ทำให้ไม่ต้องเขียน Python Script แยกต่างหากสำหรับ Agent ตัวนี้
6. **DeviceChecker:** จัดการสถานะ Online/Offline ของอุปกรณ์ได้อย่างแม่นยำขึ้น ด้วยการตรวจจับข้อมูลที่ผิดปกติ (เช่น Timestamp ขาดหาย) และส่งสถานะ Offline กลับไปยัง MQTT พร้อมทั้งบันทึกลงฐานข้อมูล ClickHouse เพื่อการวิเคราะห์ย้อนหลัง
7. **DataAggregatorAgent:** คำนวณค่าทางสถิติจากข้อมูลดิบใน ClickHouse (เช่น ค่าเฉลี่ย, ผลรวม, จำนวนครั้ง) แล้วบันทึกผลลัพธ์ลงใน **PostgreSQL** ซึ่งเป็นฐานข้อมูลหลักสำหรับแอปพลิเคชันเว็บหรือแดชบอร์ด
8. **Logging:** ทุก Process จะเก็บ Log ไว้ที่โฟลเดอร์ `/var/log/apps/` ของแต่ละ Container เพื่อให้สะดวกในการตรวจสอบ และใช้ `TZ=Asia/Bangkok`
9. **Time Zone:** ทุก Service/Process รวมถึง ClickHouse จะใช้ Time Zone ของไทย (`TZ=Asia/Bangkok` หรือ UTC+7)