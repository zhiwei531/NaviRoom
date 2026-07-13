-- NaviRoom 数据库初始化
-- 此文件在 MySQL 容器首次启动时自动执行
USE navi_room_db;

-- 房间表
CREATE TABLE IF NOT EXISTS rooms (
    room_id VARCHAR(120) NOT NULL PRIMARY KEY,
    floor VARCHAR(40) DEFAULT NULL,
    capacity INT DEFAULT NULL,
    room_type VARCHAR(80) DEFAULT NULL,
    equipment TEXT DEFAULT '[]',
    layout TEXT DEFAULT '[]',
    use_cases TEXT DEFAULT '[]',
    accessibility TEXT DEFAULT '[]',
    raw_description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_room_type (room_type),
    INDEX idx_capacity (capacity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 预订记录表
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id VARCHAR(120) NOT NULL,
    start_time VARCHAR(64) NOT NULL,
    end_time VARCHAR(64) NOT NULL,
    duration_minutes INT DEFAULT NULL,
    status VARCHAR(64) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_room_id (room_id),
    INDEX idx_start_time (start_time),
    CONSTRAINT fk_reservation_room
        FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数据集表
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    CONSTRAINT fk_dataset_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户房间记录表
CREATE TABLE IF NOT EXISTS user_rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    room_id VARCHAR(120) NOT NULL,
    floor VARCHAR(40) DEFAULT NULL,
    capacity INT DEFAULT NULL,
    room_type VARCHAR(80) DEFAULT NULL,
    equipment TEXT DEFAULT '[]',
    layout TEXT DEFAULT '[]',
    use_cases TEXT DEFAULT '[]',
    accessibility TEXT DEFAULT '[]',
    raw_description TEXT DEFAULT '',
    INDEX idx_dataset_id (dataset_id),
    INDEX idx_room_id (room_id),
    CONSTRAINT fk_userroom_dataset
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户预订记录表
CREATE TABLE IF NOT EXISTS user_reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    room_id VARCHAR(120) NOT NULL,
    start_time VARCHAR(64) DEFAULT NULL,
    end_time VARCHAR(64) DEFAULT NULL,
    duration_minutes INT DEFAULT NULL,
    status VARCHAR(64) DEFAULT 'completed',
    INDEX idx_dataset_id (dataset_id),
    INDEX idx_room_id (room_id),
    CONSTRAINT fk_userreservation_dataset
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
