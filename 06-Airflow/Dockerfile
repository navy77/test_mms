FROM apache/airflow:3.3.0-python3.12

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY dags/ /opt/airflow/dags/

COPY entrypoint.sh /entrypoint.sh

USER root

RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER airflow

ENTRYPOINT ["/entrypoint.sh"]
