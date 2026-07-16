# 📊 MMS Observability Stack (Grafana, Prometheus, Loki)

ระบบเฝ้าระวังประสิทธิภาพและความเสถียร (Monitoring & Logging) สำหรับโครงการระบบส่งข้อมูลความเร็วสูง MMS

---

## 🛠️ รายชื่อบริการ (Containers)

ระบบนี้รันบริการหลัก 6 ตัวเพื่อใช้ตรวจสอบระบบแบบครบวงจร:
1.  **Grafana (พอร์ต `3000`):** เว็บบอร์ดแสดงผลวิเคราะห์และกราฟสถิติ
2.  **Prometheus (พอร์ต `9090`):** ฐานข้อมูลเก็บสถิติประสิทธิภาพการประมวลผล (Metrics)
3.  **Loki (พอร์ต `3100`):** ฐานข้อมูลรวบรวมไฟล์บันทึกการทำงาน (Logs)
4.  **Promtail:** ดึงและคัดกรองไฟล์ Log จากภายนอกส่งเข้าไปยัง Loki
5.  **cAdvisor (พอร์ต `8089`):** ตัวเก็บสถิติอัตราการกินแรมและซีพียูระดับคอนเทนเนอร์
6.  **Node Exporter (พอร์ต `9100`):** ตัวเก็บสถิติระดับฮาร์ดแวร์เซิร์ฟเวอร์หลัก

---

## 🚀 ขั้นตอนการเริ่มทำงาน (Quick Start)

1.  เปิด Terminal และเข้าไปยังโฟลเดอร์ของระบบสังเกตการณ์:
    ```bash
    cd d:\test_mms\08-observability
    ```
2.  รันคอมโพสเพื่อเริ่มต้นทำงาน:
    ```bash
    docker compose up -d
    ```
3.  ตรวจสอบการรันของคอนเทนเนอร์ทั้งหมด:
    ```bash
    docker compose ps
    ```

---

## 🖥️ วิธีการตั้งค่าใช้งานครั้งแรกบน Grafana

1.  เปิดเว็บเบราว์เซอร์ไปที่ลิงก์: **[http://localhost:3000](http://localhost:3000)**
2.  เข้าสู่ระบบด้วยรหัสเริ่มต้น:
    *   **Username:** `admin`
    *   **Password:** `admin`
    *(ระบบจะบังคับให้ตั้งรหัสผ่านใหม่ในการล็อกอินครั้งแรก)*

### 🔗 วิธีเชื่อมต่อ Data Source เข้าหาฐานข้อมูล:

#### A. เพิ่ม Prometheus (สำหรับแสดงกราฟ):
1.  ไปที่เมนู **Connections** ➡️ **Data sources** ➡️ คลิก **Add data source**
2.  เลือกประเภท **Prometheus**
3.  ในช่อง Connection URL ให้ป้อน: **`http://prometheus:9090`**
4.  เลื่อนลงล่างสุดแล้วกด **Save & test**

#### B. เพิ่ม Loki (สำหรับอ่าน Log):
1.  ไปที่เมนู **Connections** ➡️ **Data sources** ➡️ คลิก **Add data source**
2.  เลือกประเภท **Loki**
3.  ในช่อง Connection URL ให้ป้อน: **`http://loki:3100`**
4.  เลื่อนลงล่างสุดแล้วกด **Save & test**

---

## 🔍 วิธีการเปิดอ่าน Log ข้ามระบบ (Explore Logs):
เมื่อเพิ่มข้อมูล Loki สำเร็จแล้ว คุณสามารถค้นหา Log รวมของทุกคอนเทนเนอร์พร้อมกันได้ง่าย ๆ:
1.  คลิกเมนู **Explore** บนแถบด้านข้าง
2.  เลือก Data source เป็น **Loki**
3.  ในช่อง Query ให้ป้อนเงื่อนไขการค้นหา เช่น:
    *   ดูเฉพาะ Log ของ Python Aggregator: `{job="applogs"}`
    *   ดู Log จาก docker container Dashboard Backend: `{container="dashboard-backend"}`
    *   ค้นหาเฉพาะบรรทัดที่ขึ้น Error: `{job="applogs"} |= "error"`
