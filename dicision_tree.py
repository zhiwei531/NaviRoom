import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. 准备示例数据（你用真实数据替换这里）
data = {
    'weekday': ['Monday', 'Monday', 'Friday', 'Monday', 'Friday', 'Monday'],
    'time_slot': ['9-11', '9-11', '14-16', '14-16', '9-11', '9-11'],
    'room_id': ['A101', 'A102', 'A101', 'A102', 'A101', 'A102'],
    'room_capacity': [10, 15, 10, 15, 10, 15],
    'has_projector': [1, 1, 1, 0, 1, 0],
    'historical_booking_rate': [0.75, 0.25, 0.5, 0.2, 0.75, 0.25],
    'will_be_booked': [1, 0, 0, 0, 1, 0]  # 1=是, 0=否
}

df = pd.DataFrame(data)

# 2. 把文字转换成数字（计算机只认识数字）
df['weekday'] = df['weekday'].map({'Monday': 1, 'Friday': 5})
df['time_slot'] = df['time_slot'].map({'9-11': 1, '14-16': 2})
df['room_id'] = df['room_id'].map({'A101': 101, 'A102': 102})

# 3. 准备训练数据
X = df[['weekday', 'time_slot', 'room_id', 'room_capacity', 'has_projector', 'historical_booking_rate']]
y = df['will_be_booked']

# 4. 分割数据：80%训练，20%测试
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 5. 创建并训练决策树模型
model = DecisionTreeClassifier()
model.fit(X_train, y_train)

# 6. 预测并评估准确率
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"模型准确率: {accuracy:.2f}")

# 7. 预测新数据（比如预测下周一9-11点房间A101是否会被预订）
new_data = pd.DataFrame({
    'weekday': [1],  # Monday
    'time_slot': [1],  # 9-11
    'room_id': [101],  # A101
    'room_capacity': [10],
    'has_projector': [1],
    'historical_booking_rate': [0.8]
})

prediction = model.predict(new_data)
probability = model.predict_proba(new_data)

if prediction[0] == 1:
    print(f"预测结果：会被预订（概率：{probability[0][1]:.2%}）")
else:
    print(f"预测结果：不会被预订（概率：{probability[0][0]:.2%}）")