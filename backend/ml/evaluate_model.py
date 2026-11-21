"""
模型评估代码
验证模型准确性，生成评估报告
"""

import os
import sys
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from datetime import datetime
import json
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import seaborn as sns

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.deep_learning_model import CervicalAIModel
from utils.data_preprocessing import DataPreprocessor
from models.assessment import Assessment
from models.user import User, db

class ModelEvaluator:
    """模型评估器"""
    
    def __init__(self, model_path=None):
        """初始化评估器"""
        self.model_path = model_path
        self.model = None
        self.evaluation_results = {}
        
    def load_model(self, model_path=None):
        """加载模型"""
        try:
            if model_path is None:
                model_path = self.model_path
            
            if model_path is None:
                # 尝试加载最新模型
                latest_path = "backend/ml/model_weights/latest_model.h5"
                if os.path.exists(latest_path):
                    model_path = os.path.realpath(latest_path)
                else:
                    # 查找最新的模型文件
                    model_dir = "backend/ml/model_weights"
                    if os.path.exists(model_dir):
                        model_files = [f for f in os.listdir(model_dir) if f.endswith('.h5')]
                        if model_files:
                            model_files.sort(reverse=True)
                            model_path = os.path.join(model_dir, model_files[0])
            
            if model_path and os.path.exists(model_path):
                print(f"加载模型: {model_path}")
                self.model = CervicalAIModel(model_path)
                return True
            else:
                print("未找到模型文件")
                return False
                
        except Exception as e:
            print(f"加载模型失败: {e}")
            return False
    
    def load_test_data(self):
        """加载测试数据"""
        try:
            print("加载测试数据...")
            
            # 从数据库加载评估数据
            assessments = Assessment.query.filter(
                Assessment.grade.isnot(None)
            ).all()
            
            if not assessments:
                print("没有找到测试数据")
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
            
            # 准备测试数据
            X, y = DataPreprocessor.prepare_training_data(assessment_data)
            
            if X is None or y is None:
                print("准备测试数据失败")
                return None, None
            
            print(f"测试数据形状: X={X.shape}, y={y.shape}")
            
            return X, y
            
        except Exception as e:
            print(f"加载测试数据失败: {e}")
            return None, None
    
    def evaluate_model(self, X_test, y_test):
        """评估模型性能"""
        try:
            if self.model is None or self.model.model is None:
                print("模型未加载")
                return False
            
            if X_test is None or y_test is None:
                print("测试数据为空")
                return False
            
            print("评估模型性能...")
            
            # 进行预测
            y_pred_proba = self.model.model.predict(X_test, verbose=0)
            y_pred = np.argmax(y_pred_proba, axis=1)
            
            # 计算准确率
            accuracy = accuracy_score(y_test, y_pred)
            
            # 生成分类报告
            class_names = ['正常', '轻度', '中度', '重度']
            report = classification_report(
                y_test, y_pred, 
                target_names=class_names,
                output_dict=True
            )
            
            # 计算混淆矩阵
            cm = confusion_matrix(y_test, y_pred)
            
            # 保存评估结果
            self.evaluation_results = {
                'accuracy': float(accuracy),
                'classification_report': report,
                'confusion_matrix': cm.tolist(),
                'predictions': {
                    'true_labels': y_test.tolist(),
                    'predicted_labels': y_pred.tolist(),
                    'predicted_probabilities': y_pred_proba.tolist()
                },
                'evaluation_date': datetime.now().isoformat(),
                'model_path': self.model_path
            }
            
            print(f"模型准确率: {accuracy:.4f}")
            print("\n分类报告:")
            for class_name in class_names:
                if class_name in report:
                    metrics = report[class_name]
                    print(f"  {class_name}: 精确率={metrics['precision']:.3f}, 召回率={metrics['recall']:.3f}, F1={metrics['f1-score']:.3f}")
            
            return True
            
        except Exception as e:
            print(f"评估模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_evaluation_report(self):
        """生成评估报告"""
        try:
            if not self.evaluation_results:
                print("没有评估结果")
                return None
            
            report = {
                'evaluation_summary': {
                    'accuracy': self.evaluation_results['accuracy'],
                    'model_path': self.evaluation_results['model_path'],
                    'evaluation_date': self.evaluation_results['evaluation_date']
                },
                'detailed_metrics': self.evaluation_results['classification_report'],
                'confusion_matrix': self.evaluation_results['confusion_matrix'],
                'performance_analysis': self.analyze_performance()
            }
            
            return report
            
        except Exception as e:
            print(f"生成评估报告失败: {e}")
            return None
    
    def analyze_performance(self):
        """分析模型性能"""
        try:
            if not self.evaluation_results:
                return {}
            
            cm = np.array(self.evaluation_results['confusion_matrix'])
            report = self.evaluation_results['classification_report']
            
            analysis = {}
            
            # 计算各类别的性能
            class_names = ['正常', '轻度', '中度', '重度']
            for i, class_name in enumerate(class_names):
                if i < len(cm):
                    # 真正例、假正例、假反例
                    tp = cm[i, i]
                    fp = cm[:, i].sum() - tp
                    fn = cm[i, :].sum() - tp
                    
                    analysis[class_name] = {
                        'true_positives': int(tp),
                        'false_positives': int(fp),
                        'false_negatives': int(fn),
                        'support': int(tp + fn)
                    }
            
            # 识别模型弱点
            weaknesses = []
            for class_name in class_names:
                if class_name in report:
                    metrics = report[class_name]
                    if metrics['recall'] < 0.7:
                        weaknesses.append(f"{class_name}类别的召回率较低 ({metrics['recall']:.3f})")
                    if metrics['precision'] < 0.7:
                        weaknesses.append(f"{class_name}类别的精确率较低 ({metrics['precision']:.3f})")
            
            analysis['weaknesses'] = weaknesses
            
            # 总体分析
            accuracy = self.evaluation_results['accuracy']
            if accuracy >= 0.9:
                analysis['overall_assessment'] = "优秀"
                analysis['recommendation'] = "模型性能优秀，可以直接部署使用"
            elif accuracy >= 0.8:
                analysis['overall_assessment'] = "良好"
                analysis['recommendation'] = "模型性能良好，可以考虑部署使用"
            elif accuracy >= 0.7:
                analysis['overall_assessment'] = "一般"
                analysis['recommendation'] = "模型性能一般，建议进一步优化"
            else:
                analysis['overall_assessment'] = "较差"
                analysis['recommendation'] = "模型性能较差，需要重新训练或调整"
            
            return analysis
            
        except Exception as e:
            print(f"分析性能失败: {e}")
            return {}
    
    def save_evaluation_report(self, report, output_dir="backend/ml/evaluation_reports"):
        """保存评估报告"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(output_dir, f"evaluation_report_{timestamp}.json")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"评估报告已保存到: {report_file}")
            
            # 生成可视化图表
            self.generate_visualizations(report, output_dir, timestamp)
            
            return report_file
            
        except Exception as e:
            print(f"保存评估报告失败: {e}")
            return None
    
    def generate_visualizations(self, report, output_dir, timestamp):
        """生成可视化图表"""
        try:
            # 创建可视化目录
            viz_dir = os.path.join(output_dir, "visualizations")
            os.makedirs(viz_dir, exist_ok=True)
            
            # 1. 混淆矩阵热图
            if 'confusion_matrix' in report:
                cm = np.array(report['confusion_matrix'])
                plt.figure(figsize=(8, 6))
                sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                           xticklabels=['正常', '轻度', '中度', '重度'],
                           yticklabels=['正常', '轻度', '中度', '重度'])
                plt.title('混淆矩阵')
                plt.xlabel('预测标签')
                plt.ylabel('真实标签')
                plt.tight_layout()
                cm_path = os.path.join(viz_dir, f"confusion_matrix_{timestamp}.png")
                plt.savefig(cm_path, dpi=300)
                plt.close()
                print(f"混淆矩阵图已保存: {cm_path}")
            
            # 2. 各类别性能条形图
            if 'detailed_metrics' in report:
                metrics = report['detailed_metrics']
                class_names = ['正常', '轻度', '中度', '重度']
                
                precision_scores = []
                recall_scores = []
                f1_scores = []
                
                for class_name in class_names:
                    if class_name in metrics:
                        precision_scores.append(metrics[class_name]['precision'])
                        recall_scores.append(metrics[class_name]['recall'])
                        f1_scores.append(metrics[class_name]['f1-score'])
                
                x = np.arange(len(class_names))
                width = 0.25
                
                plt.figure(figsize=(10, 6))
                plt.bar(x - width, precision_scores, width, label='精确率', color='skyblue')
                plt.bar(x, recall_scores, width, label='召回率', color='lightgreen')
                plt.bar(x + width, f1_scores, width, label='F1分数', color='salmon')
                
                plt.xlabel('类别')
                plt.ylabel('分数')
                plt.title('各类别性能对比')
                plt.xticks(x, class_names)
                plt.legend()
                plt.ylim(0, 1.1)
                plt.grid(True, alpha=0.3)
                plt.tight_layout()
                
                metrics_path = os.path.join(viz_dir, f"class_metrics_{timestamp}.png")
                plt.savefig(metrics_path, dpi=300)
                plt.close()
                print(f"类别性能图已保存: {metrics_path}")
            
            # 3. 准确率饼图
            if 'evaluation_summary' in report:
                accuracy = report['evaluation_summary']['accuracy']
                error_rate = 1 - accuracy
                
                plt.figure(figsize=(6, 6))
                labels = ['正确', '错误']
                sizes = [accuracy, error_rate]
                colors = ['lightgreen', 'lightcoral']
                explode = (0.1, 0)
                
                plt.pie(sizes, explode=explode, labels=labels, colors=colors,
                       autopct='%1.1f%%', shadow=True, startangle=90)
                plt.title(f'模型准确率: {accuracy:.2%}')
                plt.axis('equal')
                
                accuracy_path = os.path.join(viz_dir, f"accuracy_pie_{timestamp}.png")
                plt.savefig(accuracy_path, dpi=300)
                plt.close()
                print(f"准确率饼图已保存: {accuracy_path}")
            
        except Exception as e:
            print(f"生成可视化图表失败: {e}")
    
    def compare_models(self, model_paths):
        """比较多个模型"""
        try:
            comparison_results = {}
            
            for model_path in model_paths:
                print(f"\n评估模型: {model_path}")
                
                # 加载模型
                self.model_path = model_path
                if not self.load_model():
                    continue
                
                # 加载测试数据
                X_test, y_test = self.load_test_data()
                if X_test is None:
                    continue
                
                # 评估模型
                if self.evaluate_model(X_test, y_test):
                    report = self.generate_evaluation_report()
                    if report:
                        model_name = os.path.basename(model_path)
                        comparison_results[model_name] = {
                            'accuracy': report['evaluation_summary']['accuracy'],
                            'path': model_path,
                            'assessment': report['performance_analysis'].get('overall_assessment', '未知')
                        }
            
            # 排序并选择最佳模型
            if comparison_results:
                sorted_models = sorted(comparison_results.items(), 
                                      key=lambda x: x[1]['accuracy'], 
                                      reverse=True)
                
                print("\n" + "=" * 60)
                print("模型比较结果:")
                for model_name, metrics in sorted_models:
                    print(f"  {model_name}: 准确率={metrics['accuracy']:.4f}, 评估={metrics['assessment']}")
                
                best_model = sorted_models[0]
                print(f"\n最佳模型: {best_model[0]} (准确率: {best_model[1]['accuracy']:.4f})")
                
                return sorted_models
            
            return None
            
        except Exception as e:
            print(f"比较模型失败: {e}")
            return None


def main():
    """主函数"""
    print("=" * 60)
    print("颈椎评估模型评估")
    print("=" * 60)
    
    # 初始化评估器
    evaluator = ModelEvaluator()
    
    # 加载模型
    if not evaluator.load_model():
        print("无法加载模型，退出评估")
        return
    
    # 加载测试数据
    X_test, y_test = evaluator.load_test_data()
    if X_test is None or y_test is None:
        print("无法加载测试数据，退出评估")
        return
    
    # 评估模型
    if evaluator.evaluate_model(X_test, y_test):
        # 生成评估报告
        report = evaluator.generate_evaluation_report()
        
        if report:
            # 保存报告
            report_file = evaluator.save_evaluation_report(report)
            
            print("\n" + "=" * 60)
            print("✅ 模型评估完成！")
            print(f"\n评估报告已保存到: {report_file}")
            
            # 显示关键指标
            accuracy = report['evaluation_summary']['accuracy']
            assessment = report['performance_analysis'].get('overall_assessment', '未知')
            recommendation = report['performance_analysis'].get('recommendation', '')
            
            print(f"\n关键指标:")
            print(f"  准确率: {accuracy:.4f}")
            print(f"  总体评估: {assessment}")
            print(f"  建议: {recommendation}")
            
            # 显示弱点分析
            weaknesses = report['performance_analysis'].get('weaknesses', [])
            if weaknesses:
                print(f"\n需要改进的方面:")
                for weakness in weaknesses:
                    print(f"  • {weakness}")
    else:
        print("\n" + "=" * 60)
        print("❌ 模型评估失败")


if __name__ == "__main__":
    # 设置TensorFlow日志级别
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    
    # 运行评估
    main()
