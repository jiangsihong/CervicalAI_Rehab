"""
训练颈椎评估模型的代码
包含训练过程、数据加载、模型训练等
"""

import os
import sys
import numpy as np
import tensorflow as tf
from datetime import datetime
import json

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.deep_learning_model import CervicalAIModel
from utils.data_preprocessing import DataPreprocessor
from models.assessment import Assessment
from models.user import User, db

class ModelTrainer:
    """模型训练器"""
    
    def __init__(self, config=None):
        """初始化训练器"""
        self.config = config or self.get_default_config()
        self.model = None
        self.history = None
        
    @staticmethod
    def get_default_config():
        """获取默认配置"""
        return {
            'batch_size': 32,
            'epochs': 50,
            'learning_rate': 0.001,
            'validation_split': 0.2,
            'test_split': 0.1,
            'model_save_path': 'backend/ml/model_weights',
            'early_stopping_patience': 10,
            'reduce_lr_patience': 5
        }
    
    def load_training_data(self):
        """加载训练数据"""
        try:
            print("加载训练数据...")
            
            # 从数据库加载评估数据
            assessments = Assessment.query.filter(
                Assessment.grade.isnot(None)
            ).all()
            
            if not assessments:
                print("没有找到训练数据")
                return None, None
            
            # 转换为字典格式
            assessment_data = []
            for assessment in assessments:
                data = assessment.to_dict()
                
                # 添加用户信息
                user = User.query.get(assessment.user_id)
                if user:
                    data['user_info'] = {
                        'age': user.age,
                        'gender': user.gender,
                        'occupation': user.occupation
                    }
                
                assessment_data.append(data)
            
            print(f"加载了 {len(assessment_data)} 条评估记录")
            
            # 准备训练数据
            X, y = DataPreprocessor.prepare_training_data(assessment_data)
            
            if X is None or y is None:
                print("准备训练数据失败")
                return None, None
            
            print(f"训练数据形状: X={X.shape}, y={y.shape}")
            
            return X, y
            
        except Exception as e:
            print(f"加载训练数据失败: {e}")
            return None, None
    
    def create_model(self, input_shape, num_classes):
        """创建模型"""
        try:
            print(f"创建模型: input_shape={input_shape}, num_classes={num_classes}")
            
            # 使用CervicalAIModel
            self.model = CervicalAIModel()
            
            # 如果是分类任务，调整输出层
            if num_classes != self.model.num_classes:
                print(f"调整模型输出层: {self.model.num_classes} -> {num_classes}")
                # 这里可以重新构建模型或调整最后一层
                
            return self.model.model
            
        except Exception as e:
            print(f"创建模型失败: {e}")
            return None
    
    def train(self, X, y):
        """训练模型"""
        try:
            if X is None or y is None:
                print("训练数据为空")
                return False
            
            # 数据分割
            from sklearn.model_selection import train_test_split
            X_train, X_temp, y_train, y_temp = train_test_split(
                X, y, test_size=self.config['validation_split'] + self.config['test_split'], random_state=42
            )
            
            test_ratio = self.config['test_split'] / (self.config['validation_split'] + self.config['test_split'])
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp, y_temp, test_size=test_ratio, random_state=42
            )
            
            print(f"数据分割: 训练集={len(X_train)}, 验证集={len(X_val)}, 测试集={len(X_test)}")
            
            # 创建模型
            input_shape = X_train.shape[1:]
            num_classes = len(np.unique(y))
            
            model = self.create_model(input_shape, num_classes)
            if model is None:
                return False
            
            # 编译模型
            model.compile(
                optimizer=tf.keras.optimizers.Adam(learning_rate=self.config['learning_rate']),
                loss='sparse_categorical_crossentropy',
                metrics=['accuracy']
            )
            
            # 回调函数
            callbacks = []
            
            # 早停
            early_stopping = tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=self.config['early_stopping_patience'],
                restore_best_weights=True,
                verbose=1
            )
            callbacks.append(early_stopping)
            
            # 学习率调整
            reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=self.config['reduce_lr_patience'],
                min_lr=1e-6,
                verbose=1
            )
            callbacks.append(reduce_lr)
            
            # 模型检查点
            checkpoint_path = os.path.join(self.config['model_save_path'], 'checkpoint')
            os.makedirs(checkpoint_path, exist_ok=True)
            
            checkpoint = tf.keras.callbacks.ModelCheckpoint(
                filepath=os.path.join(checkpoint_path, 'model_epoch_{epoch:02d}.h5'),
                monitor='val_accuracy',
                save_best_only=True,
                verbose=1
            )
            callbacks.append(checkpoint)
            
            # 训练模型
            print("开始训练模型...")
            self.history = model.fit(
                X_train, y_train,
                batch_size=self.config['batch_size'],
                epochs=self.config['epochs'],
                validation_data=(X_val, y_val),
                callbacks=callbacks,
                verbose=1
            )
            
            # 评估模型
            print("\n评估模型性能...")
            test_loss, test_accuracy = model.evaluate(X_test, y_test, verbose=0)
            print(f"测试集损失: {test_loss:.4f}")
            print(f"测试集准确率: {test_accuracy:.4f}")
            
            # 保存最终模型
            self.save_model(model)
            
            # 保存训练历史
            self.save_training_history()
            
            return True
            
        except Exception as e:
            print(f"训练模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_model(self, model):
        """保存模型"""
        try:
            # 确保目录存在
            os.makedirs(self.config['model_save_path'], exist_ok=True)
            
            # 生成模型文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_filename = f"cervical_model_v1_{timestamp}.h5"
            model_path = os.path.join(self.config['model_save_path'], model_filename)
            
            # 保存模型
            model.save(model_path)
            print(f"模型已保存到: {model_path}")
            
            # 更新最新模型链接
            latest_path = os.path.join(self.config['model_save_path'], "latest_model.h5")
            if os.path.exists(latest_path):
                os.remove(latest_path)
            os.symlink(model_filename, latest_path)
            
            return model_path
            
        except Exception as e:
            print(f"保存模型失败: {e}")
            return None
    
    def save_training_history(self):
        """保存训练历史"""
        try:
            if self.history is None:
                return
            
            history_path = os.path.join(self.config['model_save_path'], 'training_history')
            os.makedirs(history_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_file = os.path.join(history_path, f"history_{timestamp}.json")
            
            # 转换历史数据为可序列化格式
            history_dict = {}
            for key, values in self.history.history.items():
                history_dict[key] = [float(v) for v in values]
            
            # 添加配置信息
            history_dict['config'] = self.config
            history_dict['timestamp'] = timestamp
            
            with open(history_file, 'w') as f:
                json.dump(history_dict, f, indent=2)
            
            print(f"训练历史已保存到: {history_file}")
            
        except Exception as e:
            print(f"保存训练历史失败: {e}")
    
    def generate_training_report(self):
        """生成训练报告"""
        try:
            if self.history is None:
                return None
            
            report = {
                'training_date': datetime.now().isoformat(),
                'config': self.config,
                'final_metrics': {},
                'training_summary': {}
            }
            
            # 提取最终指标
            history = self.history.history
            if 'val_accuracy' in history and history['val_accuracy']:
                report['final_metrics']['val_accuracy'] = float(history['val_accuracy'][-1])
            if 'val_loss' in history and history['val_loss']:
                report['final_metrics']['val_loss'] = float(history['val_loss'][-1])
            if 'accuracy' in history and history['accuracy']:
                report['final_metrics']['accuracy'] = float(history['accuracy'][-1])
            if 'loss' in history and history['loss']:
                report['final_metrics']['loss'] = float(history['loss'][-1])
            
            # 训练摘要
            report['training_summary']['total_epochs'] = len(history.get('loss', []))
            report['training_summary']['best_val_accuracy'] = max(history.get('val_accuracy', [0]))
            report['training_summary']['best_val_loss'] = min(history.get('val_loss', [float('inf')]))
            
            return report
            
        except Exception as e:
            print(f"生成训练报告失败: {e}")
            return None


def main():
    """主函数"""
    print("=" * 60)
    print("颈椎评估模型训练")
    print("=" * 60)
    
    # 初始化训练器
    trainer = ModelTrainer()
    
    # 加载数据
    X, y = trainer.load_training_data()
    if X is None or y is None:
        print("无法加载训练数据，退出训练")
        return
    
    # 训练模型
    success = trainer.train(X, y)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 模型训练完成！")
        
        # 生成报告
        report = trainer.generate_training_report()
        if report:
            print("\n训练报告:")
            for key, value in report['final_metrics'].items():
                print(f"  {key}: {value:.4f}")
        
        print(f"\n模型保存在: {trainer.config['model_save_path']}")
    else:
        print("\n" + "=" * 60)
        print("❌ 模型训练失败")


if __name__ == "__main__":
    # 设置TensorFlow日志级别
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    
    # 运行训练
    main()
