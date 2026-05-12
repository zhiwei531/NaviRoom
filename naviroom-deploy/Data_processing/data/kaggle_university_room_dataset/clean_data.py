import csv

# 输入文件（原始不规范 CSV）
input_file = "/home/vivi/NaviRoom/Kaggle_University_Room_Dataset/training_room.csv"
# 输出文件（规范 CSV）
output_file = "rooms_clean.csv"

with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "w", newline="", encoding="utf-8") as outfile:

    writer = csv.writer(outfile)
    for line in infile:
        # 去掉首尾空白符
        line = line.strip()
        # 如果是空行，跳过
        if not line:
            continue
        # 用空格或制表符分隔
        parts = line.split()  # 默认按任意空白字符分割
        # 写入 CSV
        writer.writerow(parts)

print(f"Clean CSV saved to {output_file}")