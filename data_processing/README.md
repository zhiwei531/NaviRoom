# NaviRoom 数据处理模块

将会议室/教室的原始数据（CSV、自然语言描述等）清洗、解析并统一为结构化 JSON 格式，供 NaviRoom 系统使用。

## 目录结构

```
data_processing/
├── data/                           # 原始数据
│   ├── kaggle_university_room_dataset/
│   │   ├── reservations.csv        # 预订记录（原始）
│   │   ├── reservations.json       # 预订记录（清洗后）
│   │   ├── rooms_clean.csv         # 房间信息（清洗后）
│   │   └── clean_data.py           # Kaggle 数据集预处理脚本
│   └── dku_room_data/
│       └── rooms.csv               # DKU 房间数据
├── scripts/                        # 处理脚本
│   ├── pipeline.py                 # 主流水线（推荐入口）
│   ├── csv_processing.py           # 预订记录 CSV 清洗
│   ├── nlp_2_json_spacy.py         # 基于 spaCy 的房间特征解析器
│   └── nlp_2_json_dspy.py          # 基于 DSPy/LLM 的房间特征解析器（可选）
├── output/                         # 输出
│   ├── kaggle_dataset.json         # Kaggle 数据集输出
│   └── dku_dataset.json            # DKU 数据集输出
└── README.md
```

## 数据流程

```
用户输入（CSV / Excel / 自然语言）
        ↓
    数据清洗（预订记录格式化、日期解析）
        ↓
    房间解析（RoomParser：提取 capacity、equipment、layout 等）
        ↓
    统一 JSON 输出（rooms + reservations）
```

## 输出格式

最终 JSON 结构：

```json
{
  "rooms": [
    {
      "room_id": "R1124",
      "floor": 1,
      "capacity": 4,
      "equipment": ["screen", "whiteboard"],
      "layout": ["study room"],
      "use_cases": [],
      "accessibility": [],
      "room_type": "study room",
      "raw_description": { ... }
    }
  ],
  "reservations": [
    {
      "room_id": "004",
      "start_time": "2024-01-15T09:00:00",
      "end_time": "2024-01-15T11:00:00",
      "duration_minutes": 120,
      "status": "completed"
    }
  ]
}
```

## 脚本说明

| 脚本 | 功能 |
|------|------|
| `pipeline.py` | **主入口**。串联房间解析与预订清洗，一键生成完整数据集 |
| `csv_processing.py` | 将预订 CSV 转为标准 JSON（支持 BOM、多日期格式、duration 标准化） |
| `nlp_2_json_spacy.py` | `RoomParser`：基于 spaCy 与规则，从文本/CSV/Excel 提取房间特征（设备、布局、无障碍、容量等） |
| `nlp_2_json_dspy.py` | 使用 DSPy + LLM 的替代解析器，适合复杂自然语言描述 |

## 快速开始

### 1. 依赖安装

```bash
pip install pandas spacy
python -m spacy download en_core_web_sm
```

若使用 DSPy 解析器，额外安装：

```bash
pip install dspy-ai
```

### 2. 运行主流水线

```bash
cd NaviRoom
python -m data_processing.scripts.pipeline \
  --rooms data_processing/data/dku_room_data/rooms.csv \
  --reservations data_processing/data/kaggle_university_room_dataset/reservations.csv \
  --output data_processing/output/dataset.json
```

仅解析房间（无预订）：

```bash
python -m data_processing.scripts.pipeline \
  --rooms data_processing/data/dku_room_data/rooms.csv \
  --output data_processing/output/rooms_only.json
```

### 3. 在代码中使用 RoomParser

```python
from data_processing.scripts.nlp_2_json_spacy import RoomParser

parser = RoomParser()
rooms = parser.parse("path/to/rooms.csv")  # 或 str / dict / DataFrame
parser.save(rooms, "out.json")
```

## 数据源说明

- **Kaggle University Room Dataset**：大学教室数据集，包含 `Room_Number`、`Capacity` 及预订记录
- **DKU Room Data**：DKU 自习室数据，包含 `room_id`、`floor`、`capacity`、`has_screen`、`has_whiteboard`、`room_type` 等字段

## RoomParser 能力概览

- 支持 `key=value` / `key:value` 内联解析（如 `has_screen=Y`、`cap=30`）
- 设备/布局/用途/无障碍多词条词汇表与同义词归一化（如 `wb` → `whiteboard`）
- 斜杠、& 符号展开（如 `projector/whiteboard` → 两个设备）
- 多格式容量识别（`pax`、`max N`、`up to N`、`N-person`）
- 多格式楼层识别（`B1`、`G`、`2F`、`L2`）
- 支持输入类型：字符串、字典、`pandas.DataFrame`、文件路径
