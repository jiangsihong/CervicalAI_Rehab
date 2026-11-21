"""
深度学习模型
用于加载与训练颈椎评估的AI模型
"""

import tensorflow as tf
import numpy as np
import os
from datetime import datetime

class CervicalAIModel:
    """颈椎评估AI模型"""
    
    def __init__(self, model_path=None):
        """初始化模型"""
        self.model = None
        self.model_path = model_path
        self.input_shape = (224, 224, 3)  # 默认输入形状
        self.num_classes = 4  # 四级分类
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        else:
            self.build_model()
    
    def build_model(self):
        """构建模型架构"""
        # 使用预训练的MobileNetV2作为基础模型
        base_model = tf.keras.applications.MobileNetV2(
            input_shape=self.input_shape,
            include_top=False,
            weights='imagenet'
        )
        
        # 冻结基础模型的前几层
        base_model.trainable = False
        
        # 添加自定义层
        inputs = tf.keras.Input(shape=self.input_shape)
        x = base_model(inputs, training=False)
        x = tf.keras.layers.GlobalAveragePooling2D()(x)
        x = tf.keras.layers.Dense(128, activation='relu')(x)
        x = tf.keras.layers.Dropout(0.5)(x)
        outputs = tf.keras.layers.Dense(self.num_classes, activation='softmax')(x)
        
        self.model = tf.keras.Model(inputs, outputs)
        
        # 编译模型
        self.model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return self.model
    
    def load_model(self, model_path):
        """加载预训练模型"""
        try:
            self.model = tf.keras.models.load_model(model_path)
            print(f"模型已从 {model_path} 加载")
            return True
        except Exception as e:
            print(f"加载模型失败: {e}")
            print("创建新模型...")
            self.build_model()
            return False
    
    def save_model(self, model_path=None):
        """保存模型"""
        if model_path is None:
            model_path = self.model_path
        
        if model_path is None:
            # 生成默认路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = f"backend/ml/model_weights/model_v1_{timestamp}.h5"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        self.model.save(model_path)
        print(f"模型已保存到 {model_path}")
        return model_path
    
    def predict(self, image_data):
        """预测颈椎健康等级"""
        if self.model is None:
            raise ValueError("模型未初始化")
        
        # 预处理图像数据
        processed_data = self.preprocess_image(image_data)
        
        # 进行预测
        predictions = self.model.predict(processed_data, verbose=0)
        
        # 获取预测结果
        predicted_class = np.argmax(predictions[0])
        confidence = float(predictions[0][predicted_class])
        
        # 映射到四级分类
        grade_mapping = {
            0: 'normal',
            1: 'mild',
            2: 'moderate',
            3: 'severe'
        }
        
        grade = grade_mapping.get(predicted_class, 'unknown')
        
        return {
            'grade': grade,
            'confidence': confidence,
            'predictions': predictions[0].tolist(),
            'grade_score': predicted_class + 1  # 1-4分
        }
    
    def preprocess_image(self, image_data):
        """预处理图像数据"""
        # 这里应该实现图像预处理逻辑
        # 包括调整大小、归一化等
        
        # 示例：假设image_data已经是numpy数组
        if isinstance(image_data, np.ndarray):
            # 调整大小到模型输入形状
            import cv2
            if len(image_data.shape) == 2:  # 灰度图
                image_data = cv2.cvtColor(image_data, cv2.COLOR_GRAY2RGB)
            
            resized = cv2.resize(image_data, (self.input_shape[0], self.input_shape[1]))
            
            # 归一化
            normalized = resized.astype('float32') / 255.0
            
            # 添加批次维度
            batched = np.expand_dims(normalized, axis=0)
            
            return batched
        else:
            # 如果是文件路径，加载图像
            import cv2
            image = cv2.imread(image_data)
            if image is None:
                raise ValueError(f"无法加载图像: {image_data}")
            
            return self.preprocess_image(image)
    
    def train(self, train_data, val_data, epochs=10, batch_size=32):
        """训练模型"""
        if self.model is None:
            self.build_model()
        
        # 训练历史
        history = self.model.fit(
            train_data,
            validation_data=val_data,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1
        )
        
        return history
    
    def evaluate(self, test_data):
        """评估模型性能"""
        if self.model is None:
            raise ValueError("模型未初始化")
        
        results = self.model.evaluate(test_data, verbose=0)
        
        return {
            'loss': results[0],
            'accuracy': results[1]
        }
    
    @staticmethod
    def create_sample_model():
        """创建示例模型（用于测试）"""
        model = CervicalAIModel()
        
        # 保存示例模型
        model_dir = "backend/ml/model_weights"
        os.makedirs(model_dir, exist_ok=True)
        
        model_path = os.path.join(model_dir, "model_v1.h5")
        model.save_model(model_path)
        
        return model_path


if __name__ == "__main__":
    # 示例用法
    print("颈椎评估AI模型模块")
    
    # 创建示例模型
    model_path = CervicalAIModel.create_sample_model()
    print(f"示例模型已创建: {model_path}")
    
    # 加载模型
    model = CervicalAIModel(model_path)
    
    # 创建虚拟数据测试
    dummy_image = np.random.rand(224, 224, 3).astype('float32')
    
    try:
        prediction = model.predict(dummy_image)
        print(f"预测结果: {prediction}")
    except Exception as e:
        print(f"预测测试失败: {e}")
