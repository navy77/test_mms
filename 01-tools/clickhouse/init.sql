-- Default database

CREATE TABLE IF NOT EXISTS status_tb(
    created_at DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String,
    status String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at ;

CREATE TABLE IF NOT EXISTS alarm_tb(
    created_at DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String,
    status String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at ;

CREATE TABLE IF NOT EXISTS device_tb(
    created_at DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String,
    status String,
    broker String,
    modbus String,
    mac_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at ;

CREATE TABLE IF NOT EXISTS data_tb(
    created_at DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String,
    model String,
    data1 Float32,
    data2 Float32,
    data3 Float32,
    data4 Float32,
    data5 Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at;


-- CONFIG DATABASE

CREATE DATABASE IF NOT EXISTS configdb;

CREATE TABLE IF NOT EXISTS configdb.device_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS configdb.columns_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    column_name String,
    column_type String,
    column_key Bool
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS configdb.user_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    user String,
    password String,
    role String

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS configdb.project_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    items String,
    value String

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS configdb.status_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    status String,
    color String

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS configdb.alarm_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    status String,
    color String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

-- dummy

INSERT INTO "configdb"."columns_register_tb" 
(process, column_name,column_type,column_key) 
VALUES ('demo1', 'model', 'String',true),
('demo1', 'data1', 'Float32',false),
('demo1', 'data2', 'Float32',false),
('demo1', 'data3', 'Float32',false),
('demo1', 'data4', 'Float32',false),
('demo1', 'data5', 'Float32',false)
;

INSERT INTO "configdb"."device_register_tb" (process, device) 
SELECT 'demo1' AS process, concat('no_', toString(number + 1)) 
AS device FROM numbers(1000);

-- INSERT INTO "configdb"."device_register_tb" (process, device) 
-- SELECT 'demo2' AS process, concat('no_', toString(number + 1)) 
-- AS device FROM numbers(500);

INSERT INTO "configdb"."user_register_tb" (user, password, role) 
VALUES ('admin', 'admin', 'admin'),
('user', 'user', 'user');

INSERT INTO "configdb"."project_register_tb" (items, value) 
VALUES ('division','mic'),
('server_IP', '0.0.0.0'),
('record_period',60);


