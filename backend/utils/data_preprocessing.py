"""
数据预处理
处理原始数据，清洗并格式化为适合训练的格式
"""

import numpy as np
import pandas as pd
from datetime import datetime
import json

class DataPreprocessor:
    """数据预处理器"""
    
    @staticmethod
    def preprocess_assessment_data(assessment_data):
        """预处理评估数据"""
        try:
            # 确保所有必要的角度字段都存在
            required_angles = [
                'flexion_angle', 'extension_angle',
                'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
                'left_rotation_angle', 'right_rotation_angle'
            ]
            
            processed = {}
            
            # 处理角度数据
            for angle_field in required_angles:
                angle_value = assessment_data.get(angle_field)
                if angle_value is None:
                    # 如果角度缺失，使用默认值或估算值
                    processed[angle_field] = 0.0
                else:
                    # 确保角度是浮点数
                    processed[angle_field] = float(angle_value)
            
            # 处理分级数据
            grade = assessment_data.get('grade')
            if grade:
                grade_mapping = {'normal': 0, 'mild': 1, 'moderate': 2, 'severe': 3}
                processed['grade_label'] = grade_mapping.get(grade, 0)
                processed['grade'] = grade
            else:
                processed['grade_label'] = 0
                processed['grade'] = 'unknown'
            
            # 处理日期
            assessment_date = assessment_data.get('assessment_date')
            if assessment_date:
                if isinstance(assessment_date, str):
                    try:
                        date_obj = datetime.strptime(assessment_date, '%Y-%m-%d')
                        processed['assessment_date'] = date_obj.isoformat()
                        processed['day_of_week'] = date_obj.weekday()
                        processed['month'] = date_obj.month
                    except:
                        processed['assessment_date'] = assessment_date
                        processed['day_of_week'] = 0
                        processed['month'] = 1
                else:
                    processed['assessment_date'] = assessment_date.isoformat() if hasattr(assessment_date, 'isoformat') else str(assessment_date)
            
            # 处理用户信息
            user_info = assessment_data.get('user_info', {})
            if user_info:
                processed['age'] = float(user_info.get('age', 30))
                processed['gender'] = 1 if user_info.get('gender') == 'male' else 0
                processed['occupation_encoded'] = DataPreprocessor.encode_occupation(user_info.get('occupation'))
            
            # 添加衍生特征
            processed = DataPreprocessor.add_derived_features(processed)
            
            return processed
            
        except Exception as e:
            print(f"预处理评估数据失败: {e}")
            return None
    
    @staticmethod
    def encode_occupation(occupation):
        """编码职业信息"""
        occupation_mapping = {
            '学生': 0,
            '办公室职员': 1,
            '程序员': 2,
            '教师': 3,
            '医生': 4,
            '工人': 5,
            '其他': 6
        }
        
        if occupation in occupation_mapping:
            return occupation_mapping[occupation]
        else:
            return 6  # 其他
    
    @staticmethod
    def add_derived_features(data):
        """添加衍生特征"""
        try:
            # 计算平均角度
            angles = [
                data.get('flexion_angle', 0),
                data.get('extension_angle', 0),
                data.get('left_lateral_flexion_angle', 0),
                data.get('right_lateral_flexion_angle', 0),
                data.get('left_rotation_angle', 0),
                data.get('right_rotation_angle', 0)
            ]
            
            valid_angles = [a for a in angles if a > 0]
            if valid_angles:
                data['average_angle'] = sum(valid_angles) / len(valid_angles)
            else:
                data['average_angle'] = 0
            
            # 计算左右对称性
            left_lateral = data.get('left_lateral_flexion_angle', 0)
            right_lateral = data.get('right_lateral_flexion_angle', 0)
            if left_lateral > 0 and right_lateral > 0:
                data['lateral_symmetry'] = abs(left_lateral - right_lateral) / ((left_lateral + right_lateral) / 2)
            else:
                data['lateral_symmetry'] = 0
            
            left_rotation = data.get('left_rotation_angle', 0)
            right_rotation = data.get('right_rotation_angle', 0)
            if left_rotation > 0 and right_rotation > 0:
                data['rotation_symmetry'] = abs(left_rotation - right_rotation) / ((left_rotation + right_rotation) / 2)
            else:
                data['rotation_symmetry'] = 0
            
            # 计算前后活动度比例
            flexion = data.get('flexion_angle', 0)
            extension = data.get('extension_angle', 0)
            if flexion > 0 and extension > 0:
                data['flexion_extension_ratio'] = flexion / extension
            else:
                data['flexion_extension_ratio'] = 1
            
            # 计算总活动度
            data['total_mobility'] = sum([a for a in angles if a > 0])
            
            return data
            
        except Exception as e:
            print(f"添加衍生特征失败: {e}")
            return data
    
    @staticmethod
    def normalize_features(data, feature_ranges=None):
        """特征归一化"""
        try:
            normalized = data.copy()
            
            # 角度归一化（0-100度范围）
            angle_fields = [
                'flexion_angle', 'extension_angle',
                'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
                'left_rotation_angle', 'right_rotation_angle',
                'average_angle', 'total_mobility'
            ]
            
            for field in angle_fields:
                if field in normalized:
                    # 假设正常角度范围0-100度
                    normalized[field] = normalized[field] / 100.0
            
            # 对称性归一化（0-1，越小越好）
            symmetry_fields = ['lateral_symmetry', 'rotation_symmetry']
            for field in symmetry_fields:
                if field in normalized:
                    normalized[field] = min(normalized[field], 1.0)
            
            # 年龄归一化（假设0-100岁）
            if 'age' in normalized:
                normalized['age'] = normalized['age'] / 100.0
            
            return normalized
            
        except Exception as e:
            print(f"特征归一化失败: {e}")
            return data
    
    @staticmethod
    def prepare_training_data(assessments, target_field='grade_label'):
        """准备训练数据"""
        try:
            features = []
            labels = []
            
            for assessment in assessments:
                # 预处理数据
                processed = DataPreprocessor.preprocess_assessment_data(assessment)
                if processed is None:
                    continue
                
                # 归一化特征
                normalized = DataPreprocessor.normalize_features(processed)
                
                # 提取特征向量
                feature_vector = DataPreprocessor.extract_feature_vector(normalized)
                if feature_vector is not None:
                    features.append(feature_vector)
                    
                    # 提取标签
                    if target_field in normalized:
                        labels.append(normalized[target_field])
                    else:
                        labels.append(0)
            
            if not features:
                return None, None
            
            return np.array(features), np.array(labels)
            
        except Exception as e:
            print(f"准备训练数据失败: {e}")
            return None, None
    
    @staticmethod
    def extract_feature_vector(data):
        """提取特征向量"""
        try:
            # 定义特征顺序
            feature_order = [
                'flexion_angle', 'extension_angle',
                'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
                'left_rotation_angle', 'right_rotation_angle',
                'average_angle', 'total_mobility',
                'lateral_symmetry', 'rotation_symmetry',
                'flexion_extension_ratio',
                'age', 'gender', 'occupation_encoded',
                'day_of_week', 'month'
            ]
            
            feature_vector = []
            for feature in feature_order:
                if feature in data:
                    feature_vector.append(data[feature])
                else:
                    feature_vector.append(0.0)  # 默认值
            
            return feature_vector
            
        except Exception as e:
            print(f"提取特征向量失败: {e}")
            return None
    
    @staticmethod
    def clean_raw_data(raw_data):
        """清洗原始数据"""
        try:
            cleaned_data = []
            
            for item in raw_data:
                cleaned_item = {}
                
                # 清理角度数据
                angle_fields = [
                    'flexion_angle', 'extension_angle',
                    'left_lateral_flexion_angle', 'right_lateral_flexion_angle',
                    'left_rotation_angle', 'right_rotation_angle'
                ]
                
                for field in angle_fields:
                    value = item.get(field)
                    if value is not None:
                        try:
                            # 转换为浮点数，处理异常值
                            float_value = float(value)
                            # 移除异常值（假设角度在0-120度之间是合理的）
                            if 0 <= float_value <= 120:
                                cleaned_item[field] = float_value
                            else:
                                cleaned_item[field] = None
                        except:
                            cleaned_item[field] = None
                    else:
                        cleaned_item[field] = None
                
                # 清理分级数据
                grade = item.get('grade')
                if grade in ['normal', 'mild', 'moderate', 'severe']:
                    cleaned_item['grade'] = grade
                
                # 清理日期
                date_str = item.get('assessment_date')
                if date_str:
                    try:
                        # 尝试解析日期
                        datetime.strptime(date_str, '%Y-%m-%d')
                        cleaned_item['assessment_date'] = date_str
                    except:
                        cleaned_item['assessment_date'] = None
                
                # 只保留有足够数据的记录
                valid_angles = sum(1 for field in angle_fields if cleaned_item.get(field) is not None)
                if valid_angles >= 4:  # 至少4个角度数据
                    cleaned_data.append(cleaned_item)
            
            return cleaned_data
            
        except Exception as e:
            print(f"清洗原始数据失败: {e}")
            return []
    
    @staticmethod
    def split_dataset(data, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1):
        """分割数据集"""
        try:
            # 随机打乱数据
            np.random.shuffle(data)
            
            total = len(data)
            train_end = int(total * train_ratio)
            val_end = train_end + int(total * val_ratio)
            
            train_data = data[:train_end]
            val_data = data[train_end:val_end]
            test_data = data[val_end:]
            
            return train_data, val_data, test_data
            
        except Exception as e:
            print(f"分割数据集失败: {e}")
            return [], [], []
    
    @staticmethod
    def save_preprocessed_data(data, filepath):
        """保存预处理后的数据"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到: {filepath}")
            return True
        except Exception as e:
            print(f"保存数据失败: {e}")
            return False
    
    @staticmethod
    def load_preprocessed_data(filepath):
        """加载预处理后的数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"数据已从 {filepath} 加载")
            return data
        except Exception as e:
            print(f"加载数据失败: {e}")
            return None


if __name__ == "__main__":
    # 测试示例
    print("数据预处理模块测试")
    
    # 创建示例数据
    sample_data = {
        'flexion_angle': 45,
        'extension_angle': 50,
        'left_lateral_flexion_angle': 35,
        'right_lateral_flexion_angle': 32,
        'left_rotation_angle': 60,
        'right_rotation_angle': 58,
        'grade': 'mild',
        'assessment_date': '2024-01-15',
        'user_info': {
            'age': 28,
            'gender': 'male',
            'occupation': '程序员'
        }
    }
    
    # 测试预处理
    processed = DataPreprocessor.preprocess_assessment_data(sample_data)
    print(f"\n预处理结果:")
    for key, value in processed.items():
        print(f"  {key}: {value}")
    
    # 测试特征提取
    features = DataPreprocessor.extract_feature_vector(processed)
    print(f"\n特征向量 ({len(features)} 维):")
    print(features[:10])  # 显示前10个特征
