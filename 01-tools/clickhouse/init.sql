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
    data1 Float32,
    data2 Float32,
    data3 Float32,
    data4 Float32,
    data5 Float32
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at;


-- Register table

CREATE TABLE IF NOT EXISTS device_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    device String
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS columns_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    process String,
    column_name String,
    column_type String

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

CREATE TABLE IF NOT EXISTS user_register_tb(
    last_update DateTime('Asia/Bangkok') DEFAULT now(),
    user String,
    password String,
    role String

) ENGINE = MergeTree()
PARTITION BY toYYYYMM(last_update)
ORDER BY last_update;

-- dummy

INSERT INTO "default"."columns_register_tb" 
(process, column_name,column_type) 
VALUES ('demo1', 'process', 'String'),
('demo1', 'device', 'String'),
('demo1', 'broker', 'String'),
('demo1', 'modbus', 'String'),
('demo1', 'mac_id', 'String'),
('demo1', 'status', 'String'),
('demo1', 'data1', 'Float32'),
('demo1', 'data2', 'Float32'),
('demo1', 'data3', 'Float32'),
('demo1', 'data4', 'Float32'),
('demo1', 'data5', 'Float32')
;

INSERT INTO "default"."device_register_tb" (process, device) 
SELECT 'demo1' AS process, concat('no_', toString(number + 1)) 
AS device FROM numbers(1000);

INSERT INTO "default"."user_register_tb" (user, password, role) 
VALUES ('admin', 'admin', 'admin'),
('user', 'user', 'user');