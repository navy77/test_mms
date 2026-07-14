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
    device String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY created_at;




