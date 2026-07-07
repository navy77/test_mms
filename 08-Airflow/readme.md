## docker command

docker build --no-cache -t mic/airflow:1.0.0 .\
docker compose up -d

---

## 🔌 วิธีการนำไปใช้งานแบบ Offline (Offline Deployment Guide)

เนื่องจากระบบปลายทางเป็นแบบ **Offline (ไม่มีอินเทอร์เน็ต)** คุณต้องทำการ Build อิมเมจจากเครื่องที่มีอินเทอร์เน็ตก่อน แล้วทำการแพ็กไฟล์อิมเมจเพื่อย้ายไปรันที่เครื่องปลายทางตามขั้นตอนดังนี้ครับ:

### ขั้นตอนที่ 1: Build และเซฟอิมเมจบนเครื่องที่มีเน็ต (On Online Machine)
1. สั่ง Build อิมเมจตามปกติ:
   ```bash
   docker build --no-cache -t mic/airflow:1.0.0 .
   ```
2. ทำการ Export ตัวอิมเมจออกมาเป็นไฟล์ `.tar`:
   ```bash
   docker save -o mic_airflow_1.0.0.tar mic/airflow:1.0.0
   ```
3. ดาวน์โหลดและเซฟฐานข้อมูล Postgres 17 (เนื่องจากระบบปลายทางไม่มีเน็ตดึงรูปภาพ Postgres):
   ```bash
   docker pull postgres:17-alpine
   docker save -o postgres_17_alpine.tar postgres:17-alpine
   ```

### ขั้นตอนที่ 2: โหลดอิมเมจและรันบนเครื่องออฟไลน์ (On Offline Machine)
1. คัดลอกไฟล์ `mic_airflow_1.0.0.tar` และ `postgres_17_alpine.tar` ไปยังเครื่องออฟไลน์ (ผ่าน USB หรือ Local Network)
2. สั่งนำเข้าอิมเมจทั้งสองตัวเข้า Docker:
   ```bash
   docker load -i mic_airflow_1.0.0.tar
   docker load -i postgres_17_alpine.tar
   ```
3. สั่งรันบริการผ่าน Docker Compose ได้ทันทีโดยไม่ต้องใช้เน็ต:
   ```bash
   docker compose up -d
   ```
