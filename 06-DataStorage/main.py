import pandas as pd
from sqlalchemy import create_engine
import clickhouse_connect
from datetime import datetime, timedelta

engine1 = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/iiot_db")
engine2 = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/storage_db")


def ch_conn():
    client = clickhouse_connect.get_client(host='localhost',port=8123, username='default', password='maibok')
    return client


def get_record_period():
  
    """Fetch record_period from PostgreSQL"""
    query = "SELECT items, value FROM project_register_tb"
    
    df = pd.read_sql(query, engine1)
    record_period = df.loc[df["items"] == "record_period", "value"].values[0]
    print(record_period)
    return record_period


def get_device():
    """Fetch device df from PostgreSQL"""
    query = "SELECT process, device  FROM device_register_tb"
    df = pd.read_sql(query, engine1)
    return df


def get_column():
    """Fetch column df from PostgreSQL"""
    query = "SELECT process, column_name, column_type,column_key  FROM columns_register_tb"
    df = pd.read_sql(query, engine1)
    return df

def get_data_from_clickhouse(type,period_minutes):
    client = ch_conn()
    now = datetime.now()
    start_time = (now - timedelta(minutes=period_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = now.strftime("%Y-%m-%d %H:%M:%S")
    query = f"SELECT * FROM {type}_tb WHERE created_at BETWEEN  '{start_time}' AND  '{end_time}'  order by created_at desc "

    if type == "data":
        df_data_raw = client.query_df(query)
        return df_data_raw
    elif type == "status":
        df_status_raw = client.query_df(query)
        return df_status_raw
    elif type == "alarm":
        df_alarm_raw = client.query_df(query)
        return df_alarm_raw
    
if __name__ == "__main__":
    x = get_record_period
    print(x)

