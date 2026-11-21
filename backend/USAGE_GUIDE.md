# CervicalAI Rehab 后端使用指南

## 项目概述

CervicalAI Rehab 是一个用于颈椎康复评估的后端系统，提供用户管理、颈椎评估数据存储、AI分析和群体统计功能。

## 系统要求

- Python 3.7+
- MySQL 5.7+ 或 SQLite（开发环境）
- 推荐使用虚拟环境

## 快速开始

### 1. 环境设置

当前 Windows 机器实际检测到的可用 Anaconda 环境是：

```text
D:\anaconda3\envs\realheponet
```

因此 `start_backend_realheponet.bat` 会固定使用 `realheponet`。

如果直接调用 `python.exe` 遇到 `_ssl` DLL 加载失败，需要先把 Conda 环境的 DLL 路径加入 `PATH`：

```powershell
cd E:\26_create\CervicalAI_Rehab\backend

$env:PATH='D:\anaconda3\envs\realheponet;D:\anaconda3\envs\realheponet\Library\mingw-w64\bin;D:\anaconda3\envs\realheponet\Library\usr\bin;D:\anaconda3\envs\realheponet\Library\bin;D:\anaconda3\envs\realheponet\Scripts;D:\anaconda3\envs\realheponet\bin;' + $env:PATH

& D:\anaconda3\envs\realheponet\python.exe --version
```

也可以用 Conda 激活后启动：

```powershell
conda activate realheponet
cd E:\26_create\CervicalAI_Rehab\backend
```

### 2. 数据库配置

#### 选项A：使用SQLite（开发环境，默认）
无需额外配置，直接使用默认的SQLite数据库。

#### 选项B：使用MySQL（生产环境）
1. 创建MySQL数据库：
```sql
CREATE DATABASE cervicalai_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cervicalai_user'@'localhost' IDENTIFIED BY 'cervicalai_password';
GRANT ALL PRIVILEGES ON cervicalai_db.* TO 'cervicalai_user'@'localhost';
FLUSH PRIVILEGES;
```

2. 设置环境变量：
```bash
# Windows
set DB_TYPE=mysql
set MYSQL_HOST=localhost
set MYSQL_PORT=3306
set MYSQL_USER=cervicalai_user
set MYSQL_PASSWORD=cervicalai_password
set MYSQL_DATABASE=cervicalai_db

# Linux/Mac
export DB_TYPE=mysql
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=cervicalai_user
export MYSQL_PASSWORD=cervicalai_password
export MYSQL_DATABASE=cervicalai_db
```

### 3. 初始化数据库

```bash
# 初始化数据库表
flask --app app.py init-db

# 填充示例数据（可选）
flask --app app.py seed-db

# 创建管理员用户（可选）
flask --app app.py create-admin
```

### 4. 启动应用

```bash
# 开发模式
& D:\anaconda3\envs\realheponet\python.exe app.py

# 或直接运行项目提供的 Windows 启动脚本
.\start_backend_realheponet.bat

# 或使用Flask命令行
& D:\anaconda3\envs\realheponet\python.exe -m flask --app app.py run --host=0.0.0.0 --port=5000 --debug
```

应用将在 http://localhost:5000 启动。

## API接口文档

### 认证方式
所有API（除注册和登录外）都需要在请求头中添加JWT令牌：
```
Authorization: Bearer <access_token>
```

### 1. 用户管理API

#### 用户注册
```http
POST /api/user/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "Password123",
  "full_name": "测试用户",
  "age": 30,
  "gender": "male",
  "occupation": "程序员",
  "role": "patient"  # patient, doctor, admin
}
```

#### 用户登录
```http
POST /api/user/login
Content-Type: application/json

{
  "username": "testuser",
  "password": "Password123"
}
```

响应包含访问令牌：
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": { ... }
  }
}
```

#### 获取用户资料
```http
GET /api/user/profile
Authorization: Bearer <access_token>
```

#### 更新用户资料
```http
PUT /api/user/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "新姓名",
  "age": 31,
  "occupation": "教师"
}
```

#### 修改密码
```http
POST /api/user/change-password
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "old_password": "旧密码",
  "new_password": "新密码123"
}
```

### 2. 评估管理API

#### 提交评估数据
```http
POST /api/assessment/submit
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "assessment_date": "2024-01-15",
  "flexion_angle": 45.5,
  "extension_angle": 50.2,
  "left_lateral_flexion_angle": 35.8,
  "right_lateral_flexion_angle": 32.1,
  "left_rotation_angle": 60.3,
  "right_rotation_angle": 58.7,
  "assessment_duration": 120,
  "device_info": "iPhone 12"
}
```

#### 获取评估历史
```http
GET /api/assessment/history
Authorization: Bearer <access_token>

# 可选查询参数
GET /api/assessment/history?start_date=2024-01-01&end_date=2024-01-31&limit=20&offset=0
```

#### 获取评估详情
```http
GET /api/assessment/{assessment_id}
Authorization: Bearer <access_token>
```

#### 获取评估趋势
```http
GET /api/assessment/trend
Authorization: Bearer <access_token>

# 可选参数：days（默认30天）
GET /api/assessment/trend?days=60
```

#### 获取评估摘要
```http
GET /api/assessment/summary
Authorization: Bearer <access_token>
```

### 3. 管理员API

#### 获取用户列表（仅管理员）
```http
GET /api/user/list
Authorization: Bearer <access_token>

# 可选参数：role, page, per_page
GET /api/user/list?role=patient&page=1&per_page=20
```

#### 获取用户统计（仅管理员）
```http
GET /api/user/stats
Authorization: Bearer <access_token>
```

#### 获取患者评估记录（医生/管理员）
```http
GET /api/assessment/patient/{patient_id}
Authorization: Bearer <access_token>
```

### 4. 颈椎倾角 AI 推理 API

这些接口会复用工程根目录下的模型文件：
- `../../headpose_final/models/pose-estimator.h5`
- `../../headpose_final/models/deploy.prototxt`
- `../../headpose_final/models/res10_300x300_ssd_iter_140000.caffemodel`
- `../../ssd_people/` 作为原始 SSD head detector 来源目录保留引用

#### 查看模型状态
```http
GET /api/assessment/pose/status
```

#### 上传图片并返回颈椎倾角
```powershell
curl.exe -X POST "http://localhost:5000/api/assessment/pose/image" `
  -F "image=@E:\26_create\headpose_final\data\people_drinking.jpg"
```

响应中的核心字段：
- `primary_detection.cervical_angles.raw_tilt`：模型输出的上下倾角，单位度
- `primary_detection.cervical_angles.raw_pan`：模型输出的左右旋转角，单位度
- `primary_detection.cervical_angles.tilt_angle`：倾角绝对值
- `primary_detection.assessment_angles`：映射到后端评估表的角度字段
- `primary_detection.health_status`：基于当前帧 `tilt/pan` 最大绝对角计算的实时健康状态
- `annotated_image`：带检测框和角度文字的 JPEG base64，可直接在前端显示

也可以传本地图片路径：
```http
POST /api/assessment/pose/image
Content-Type: application/json

{
  "image_path": "E:\\26_create\\headpose_final\\data\\people_drinking.jpg"
}
```

#### 打开摄像头实时显示倾角
浏览器访问：
```text
http://localhost:5000/api/assessment/pose/camera/view?camera=0
```

如果电脑有多个摄像头，可把 `camera=0` 改成 `camera=1`。后端会打开运行 Flask 服务这台机器上的摄像头，并在视频流里实时叠加 `TILT`、`PAN` 和 `STATUS`。状态颜色含义：绿色为正常，黄色为轻度，橙色为中度，红色为重度。

#### 直接接入 MJPEG 视频流
```http
GET /api/assessment/pose/camera/stream?camera=0
```

前端可以直接使用：
```html
<img src="http://localhost:5000/api/assessment/pose/camera/stream?camera=0" alt="颈椎倾角实时检测">
```

> 当前接入的 RealHePoNet 权重能稳定输出 `tilt/pan` 两个头部姿态角；左右侧屈角度没有对应权重，接口会以 `null` 返回，避免把缺失方向误当成 0 度参与完整六方向分级。实时 `health_status` 是当前姿态状态提示，不等同于最终医学诊断。

#### 本机验证过的样例结果

在 `realheponet` 环境下运行：

```powershell
& D:\anaconda3\envs\realheponet\python.exe -c "from services.pose_estimator_service import pose_estimator_service as s; r=s.estimate_image_path(r'E:\26_create\headpose_final\data\people_drinking.jpg', draw=False); print(r['detection_count']); print(r['primary_detection']['cervical_angles']); print(r['primary_detection']['health_status'])"
```

样例图可检测到头部候选，并返回 `raw_tilt`、`raw_pan` 和 `health_status`。

## 命令行工具

### 数据库管理
```bash
# 初始化数据库（删除所有表并重新创建）
flask --app app.py init-db

# 填充示例数据
flask --app app.py seed-db

# 创建管理员用户
flask --app app.py create-admin
```

### 机器学习模型
```bash
# 训练模型
cd backend
python ml/train_model.py

# 评估模型
python ml/evaluate_model.py

# 使用深度学习模型进行预测
python -c "
from models.deep_learning_model import CervicalAIModel
model = CervicalAIModel('backend/ml/model_weights/latest_model.h5')
# 进行预测...
"
```

## 数据模型

### 用户表 (users)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(80) | 用户名，唯一 |
| email | String(120) | 邮箱，唯一 |
| password_hash | String(256) | 密码哈希 |
| full_name | String(100) | 全名 |
| age | Integer | 年龄 |
| gender | String(20) | 性别 |
| occupation | String(100) | 职业 |
| role | String(20) | 角色：patient, doctor, admin |
| is_active | Boolean | 是否激活 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 评估记录表 (assessments)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户ID，外键 |
| assessment_date | Date | 评估日期 |
| flexion_angle | Float | 前屈角度 |
| extension_angle | Float | 后伸角度 |
| left_lateral_flexion_angle | Float | 左侧屈角度 |
| right_lateral_flexion_angle | Float | 右侧屈角度 |
| left_rotation_angle | Float | 左旋转角度 |
| right_rotation_angle | Float | 右旋转角度 |
| grade | String(20) | 分级：normal, mild, moderate, severe |
| grade_score | Integer | 分级分数：1-4 |
| grade_details | Text | 分级详情 |
| ai_confidence | Float | AI置信度 |
| assessment_duration | Integer | 评估时长（秒） |
| created_at | DateTime | 创建时间 |

## 颈椎健康分级标准

系统使用四级分级标准：

### 1级（正常）
- 所有方向活动度正常
- 无疼痛或不适
- 角度范围：前屈45-60°，后伸45-75°，侧屈35-45°，旋转60-80°

### 2级（轻度）
- 1-2个方向活动度轻度受限
- 偶有不适感
- 不影响日常生活

### 3级（中度）
- 3-4个方向活动度明显受限
- 经常感到疼痛
- 影响部分日常活动

### 4级（重度）
- 5-6个方向活动度严重受限
- 持续疼痛影响生活
- 需要医疗干预

## 配置说明

### 配置文件 (config.py)
```python
class Config:
    # 数据库配置
    DB_TYPE = 'sqlite'  # 或 'mysql'
    SQLALCHEMY_DATABASE_URI = '...'
    
    # JWT配置
    JWT_SECRET_KEY = 'your-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # 应用配置
    DEBUG = True
    SECRET_KEY = 'your-flask-secret-key'
    
    # 文件上传
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
```

### 环境变量
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| DB_TYPE | sqlite | 数据库类型：sqlite 或 mysql |
| MYSQL_HOST | localhost | MySQL主机 |
| MYSQL_PORT | 3306 | MySQL端口 |
| MYSQL_USER | cervicalai_user | MySQL用户名 |
| MYSQL_PASSWORD | cervicalai_password | MySQL密码 |
| MYSQL_DATABASE | cervicalai_db | MySQL数据库名 |
| SECRET_KEY | (自动生成) | Flask密钥 |
| JWT_SECRET_KEY | (自动生成) | JWT密钥 |
| FLASK_DEBUG | True | 调试模式 |

## 故障排除

### 常见问题

#### 1. 数据库连接失败
```bash
# 检查MySQL服务是否运行
# Windows
services.msc  # 查看MySQL服务状态

# 检查连接信息
python -c "
import pymysql
try:
    conn = pymysql.connect(
        host='localhost',
        user='cervicalai_user',
        password='cervicalai_password',
        database='cervicalai_db'
    )
    print('连接成功')
except Exception as e:
    print(f'连接失败: {e}')
"
```

#### 2. 依赖安装失败
```bash
# 如果greenlet安装失败（需要C++编译器），使用SQLite
# 修改config.py中的DB_TYPE = 'sqlite'

# 或安装预编译包
pip install --only-binary :all: greenlet
```

#### 3. 端口被占用
```bash
# 修改端口
python app.py --port 5001

# 或查找占用进程
# Windows
netstat -ano | findstr :5000
# Linux/Mac
lsof -i :5000
```

#### 4. JWT令牌无效
- 检查令牌是否过期（默认24小时）
- 重新登录获取新令牌
- 检查请求头格式：`Authorization: Bearer <token>`

## 开发指南

### 项目结构
```
backend/
├── app.py                 # Flask应用入口
├── config.py              # 配置文件
├── requirements.txt       # 依赖清单
├── models/                # 数据模型
│   ├── user.py           # 用户模型
│   ├── assessment.py     # 评估模型
│   └── deep_learning_model.py  # AI模型
├── api/                   # API路由
│   ├── user.py           # 用户API
│   └── assessment.py     # 评估API
├── services/             # 业务逻辑
│   ├── user_service.py   # 用户服务
│   ├── assessment_service.py  # 评估服务
│   └── analytics_service.py   # 分析服务
├── utils/                # 工具类
│   ├── response.py       # 响应工具
│   ├── grade_utils.py    # 分级工具
│   └── data_preprocessing.py  # 数据预处理
├── ml/                   # 机器学习
│   ├── train_model.py    # 训练脚本
│   ├── evaluate_model.py # 评估脚本
│   └── model_weights/    # 模型权重
└── logs/                 # 日志目录
```

### 添加新API
1. 在 `api/` 目录创建新的蓝图
2. 在 `app.py` 的 `register_blueprints` 函数中注册蓝图
3. 在 `services/` 目录实现业务逻辑
4. 使用 `utils/response.py` 的统一响应格式

### 添加新数据模型
1. 在 `models/` 目录创建新的模型类
2. 继承 `db.Model`
3. 在 `app.py` 中导入模型
4. 运行 `flask --app app.py init-db` 更新数据库

## 部署指南

### 生产环境配置
1. 使用MySQL数据库
2. 设置强密码和密钥
3. 禁用调试模式
4. 配置HTTPS
5. 设置防火墙规则

### 使用Gunicorn（Linux/Mac）
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Waitress（Windows）
```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

### Nginx反向代理配置
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 联系方式与支持

如有问题，请：
1. 查看日志文件：`backend/logs/app.log`
2. 检查API响应中的错误信息
3. 验证数据库连接和配置
4. 确保所有依赖已正确安装

## 版本历史

### v1.0.0 (2024-01)
- 初始版本发布
- 用户管理和认证系统
- 颈椎评估数据管理
- 四级分级算法
- 基础AI模型框架
- 群体统计分析

---

**注意**：本系统为医疗辅助工具，不能替代专业医疗诊断。如有颈椎问题，请及时就医。
