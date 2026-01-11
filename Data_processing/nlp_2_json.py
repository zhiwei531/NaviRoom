import dspy
import json
from typing import List, Dict

# -------------------------
# Signature定义：只定义输入输出schema
# -------------------------
class Text2RoomFeature(dspy.Signature):
    """
    Convert natural language description or CSV/Excel input into structured room features.
    
    Input: Natural language description or structured data row
    Output: List of room features in JSON format with fields:
    - room_id, floor, capacity, equipment, layout, use_cases, accessibility, room_type, raw_description
    """
    user_input: str = dspy.InputField(desc="Natural language description or structured CSV/Excel row")
    output: str = dspy.OutputField(desc="JSON list of room features with all fields")

# -------------------------
# DSPy Module：使用Predictor处理Signature
# -------------------------
class RoomFeatureModule(dspy.Module):
    """
    Module wrapping Text2RoomFeature signature, outputs JSON-compatible list.
    """
    def __init__(self):
        super().__init__()
        # 使用ChainOfThought或Predict来处理Signature
        self.predictor = dspy.ChainOfThought(Text2RoomFeature)
    
    def forward(self, user_input: str) -> str:
        """
        Returns JSON string for downstream storage or processing
        """
        # 调用predictor进行推理
        prediction = self.predictor(user_input=user_input)
        
        # 返回结构化的输出
        return prediction.output

# -------------------------
# 设置DSPy配置和示例
# -------------------------
def setup_dspy():
    """
    配置DSPy的LM和训练示例
    """
    # 配置语言模型（根据你的需求选择）
    # 示例：使用OpenAI
    # lm = dspy.OpenAI(model='gpt-3.5-turbo', max_tokens=1000)
    
    # 或使用本地模型
    # lm = dspy.HFModel(model='your-model-name')
    
    # 暂时使用一个dummy LM用于演示
    lm = dspy.OpenAI(model='gpt-4o-mini', max_tokens=2000)
    dspy.settings.configure(lm=lm)
    
    # 定义few-shot示例
    examples = [
        dspy.Example(
            user_input="A medium-sized seminar room with capacity for 25 people, projector and whiteboard, wheelchair accessible",
            output=json.dumps([{
                "room_id": None,
                "floor": None,
                "capacity": 25,
                "equipment": ["projector", "whiteboard"],
                "layout": ["seminar room"],
                "use_cases": ["discussion", "lecture"],
                "accessibility": ["wheelchair accessible"],
                "room_type": "seminar room",
                "raw_description": "A medium-sized seminar room with capacity for 25 people, projector and whiteboard, wheelchair accessible"
            }])
        ).with_inputs('user_input'),
        
        dspy.Example(
            user_input="R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y",
            output=json.dumps([{
                "room_id": "R1124",
                "floor": 1,
                "capacity": 4,
                "equipment": ["screen", "whiteboard"],
                "layout": ["study room"],
                "use_cases": [],
                "accessibility": [],
                "room_type": "study room",
                "raw_description": "R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y"
            }])
        ).with_inputs('user_input'),
        
        dspy.Example(
            user_input="Large lecture hall, floor 3, 100 seats, projector, microphone, recording equipment",
            output=json.dumps([{
                "room_id": None,
                "floor": 3,
                "capacity": 100,
                "equipment": ["projector", "microphone", "recording equipment"],
                "layout": ["lecture hall"],
                "use_cases": ["lecture", "presentation"],
                "accessibility": [],
                "room_type": "lecture hall",
                "raw_description": "Large lecture hall, floor 3, 100 seats, projector, microphone, recording equipment"
            }])
        ).with_inputs('user_input')
    ]
    
    return examples

# -------------------------
# 辅助函数：解析和验证输出
# -------------------------
def parse_and_validate_output(output_str: str) -> List[Dict]:
    """
    解析并验证DSPy输出的JSON
    """
    try:
        # 尝试解析JSON
        data = json.loads(output_str)
        
        # 确保是列表
        if not isinstance(data, list):
            data = [data]
        
        # 验证必需字段
        required_fields = ["room_id", "floor", "capacity", "equipment", 
                          "layout", "use_cases", "accessibility", 
                          "room_type", "raw_description"]
        
        for room in data:
            for field in required_fields:
                if field not in room:
                    room[field] = None if field in ["room_id", "floor", "room_type", "raw_description"] else []
        
        return data
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Raw output: {output_str}")
        return []

# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    # 设置DSPy（需要配置API key）
    try:
        examples = setup_dspy()
        print("DSPy configured successfully!")
        print(f"Loaded {len(examples)} training examples\n")
    except Exception as e:
        print(f"Warning: DSPy setup failed: {e}")
        print("Please configure your LM settings (OpenAI API key, etc.)\n")
    
    # 创建模块
    module = RoomFeatureModule()
    
    # 测试示例1：自然语言描述
    input_text = "A medium-sized seminar room with capacity for 25 people, projector and whiteboard, wheelchair accessible"
    print("=== RAW TEXT INPUT ===")
    print(f"Input: {input_text}\n")
    
    try:
        result = module.forward(input_text)
        print("Output:")
        print(result)
        
        # 解析并验证
        parsed = parse_and_validate_output(result)
        print(f"\nParsed {len(parsed)} room(s)")
        print(json.dumps(parsed, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试示例2：结构化CSV行
    input_csv_row = "R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y"
    print("=== STRUCTURED ROW INPUT ===")
    print(f"Input: {input_csv_row}\n")
    
    try:
        result = module.forward(input_csv_row)
        print("Output:")
        print(result)
        
        # 解析并验证
        parsed = parse_and_validate_output(result)
        print(f"\nParsed {len(parsed)} room(s)")
        print(json.dumps(parsed, indent=2))
    except Exception as e:
        print(f"Error: {e}")