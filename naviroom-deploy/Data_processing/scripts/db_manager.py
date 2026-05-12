# Data_processing/scripts/db_manager.py
#
# 每个数据集（如 dku、kaggle）拥有独立的 MySQL 表：
#   {dataset}_rooms, {dataset}_reservations
# 表在首次写入时自动创建。

import re
import mysql.connector
import json
from mysql.connector import Error


def _safe_table_prefix(name: str) -> str:
    """只允许字母、数字、下划线，防止 SQL 注入"""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "ds_" + cleaned
    return cleaned.lower()


class DBManager:
    def __init__(self, host='localhost', user='navi_user', password='your_password', database='navi_room_db'):
        try:
            self.conn = mysql.connector.connect(
                host=host,
                database=database,
                user=user,
                password=password
            )
            if self.conn.is_connected():
                print("成功连接到 MySQL 数据库")
        except Error as e:
            print(f"连接失败: {e}")
            self.conn = None

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()

    # --------------------------------------------------
    # 自动建表
    # --------------------------------------------------
    def _ensure_rooms_table(self, dataset_name: str):
        prefix = _safe_table_prefix(dataset_name)
        table = f"{prefix}_rooms"
        cursor = self.conn.cursor()
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
            room_id      VARCHAR(50)  PRIMARY KEY,
            floor        VARCHAR(20),
            capacity     INT,
            room_type    VARCHAR(100),
            equipment    JSON,
            layout       JSON,
            use_cases    JSON,
            accessibility JSON,
            raw_description TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        self.conn.commit()
        cursor.close()
        return table

    def _ensure_reservations_table(self, dataset_name: str):
        prefix = _safe_table_prefix(dataset_name)
        rooms_table = f"{prefix}_rooms"
        table = f"{prefix}_reservations"
        cursor = self.conn.cursor()
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            room_id         VARCHAR(50),
            start_time      DATETIME,
            end_time        DATETIME,
            duration_minutes INT,
            status          VARCHAR(30),
            FOREIGN KEY (room_id) REFERENCES `{rooms_table}`(room_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        self.conn.commit()
        cursor.close()
        return table

    # --------------------------------------------------
    # 写入方法
    # --------------------------------------------------
    def save_rooms(self, rooms_data, dataset_name: str = "default"):
        """保存房间数据到 {dataset}_rooms 表，如果 room_id 已存在则更新"""
        if not self.conn:
            return
        table = self._ensure_rooms_table(dataset_name)

        cursor = self.conn.cursor()
        query = f"""
        INSERT INTO `{table}` (room_id, floor, capacity, room_type, equipment, layout, use_cases, accessibility, raw_description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            floor=VALUES(floor),
            capacity=VALUES(capacity),
            room_type=VALUES(room_type),
            equipment=VALUES(equipment),
            layout=VALUES(layout),
            use_cases=VALUES(use_cases),
            accessibility=VALUES(accessibility),
            raw_description=VALUES(raw_description);
        """

        data_to_insert = []
        for r in rooms_data:
            data_to_insert.append((
                r.get('room_id'),
                str(r.get('floor')) if r.get('floor') else None,
                r.get('capacity'),
                r.get('room_type'),
                json.dumps(r.get('equipment', [])),
                json.dumps(r.get('layout', [])),
                json.dumps(r.get('use_cases', [])),
                json.dumps(r.get('accessibility', [])),
                str(r.get('raw_description', ''))
            ))

        try:
            cursor.executemany(query, data_to_insert)
            self.conn.commit()
            print(f"[{dataset_name}] 成功存入/更新 {cursor.rowcount} 个房间 → {table}")
        except Error as e:
            print(f"保存房间数据出错: {e}")
        finally:
            cursor.close()

    def save_reservations(self, reservations_data, dataset_name: str = "default"):
        """保存预约数据到 {dataset}_reservations 表"""
        if not self.conn:
            return
        table = self._ensure_reservations_table(dataset_name)

        cursor = self.conn.cursor()
        query = f"""
        INSERT INTO `{table}` (room_id, start_time, end_time, duration_minutes, status)
        VALUES (%s, %s, %s, %s, %s)
        """

        data_to_insert = []
        for r in reservations_data:
            start = r['start_time'].replace('T', ' ')
            end = r['end_time'].replace('T', ' ')
            data_to_insert.append((
                r['room_id'],
                start,
                end,
                r['duration_minutes'],
                r.get('status', 'completed')
            ))

        try:
            cursor.executemany(query, data_to_insert)
            self.conn.commit()
            print(f"[{dataset_name}] 成功存入 {cursor.rowcount} 条预约 → {table}")
        except Error as e:
            print(f"保存预约数据出错: {e}")
        finally:
            cursor.close()