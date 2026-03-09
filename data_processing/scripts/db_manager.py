# Data_processing/scripts/db_manager.py

import mysql.connector
import json
from mysql.connector import Error

class DBManager:
    def __init__(self, host='localhost', user='root', password='your_password', database='navi_room_db'):
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

    def save_rooms(self, rooms_data):
        """
        保存房间数据，如果 room_id 已存在则更新
        """
        if not self.conn: return
        
        cursor = self.conn.cursor()
        query = """
        INSERT INTO rooms (room_id, floor, capacity, room_type, equipment, layout, use_cases, accessibility, raw_description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            floor=VALUES(floor),
            capacity=VALUES(capacity),
            equipment=VALUES(equipment),
            raw_description=VALUES(raw_description);
        """

        data_to_insert = []
        for r in rooms_data:
            # 将列表转换为 JSON 字符串存入数据库
            data_to_insert.append((
                r.get('room_id'),
                str(r.get('floor')) if r.get('floor') else None, # floor可能是int或str
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
            print(f"成功存入/更新 {cursor.rowcount} 个房间数据")
        except Error as e:
            print(f"保存房间数据出错: {e}")
        finally:
            cursor.close()

    def save_reservations(self, reservations_data):
        """
        保存预约数据
        注意：需要确保对应的 room_id 在 rooms 表中已经存在
        """
        if not self.conn: return

        cursor = self.conn.cursor()
        query = """
        INSERT INTO reservations (room_id, start_time, end_time, duration_minutes, status)
        VALUES (%s, %s, %s, %s, %s)
        """

        data_to_insert = []
        for r in reservations_data:
            # 简单的日期字符串清洗 T -> 空格 (ISO格式转MySQL格式)
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
            print(f"成功存入 {cursor.rowcount} 条预约记录")
        except Error as e:
            print(f"保存预约数据出错 (可能是找不到对应的 room_id): {e}")
        finally:
            cursor.close()