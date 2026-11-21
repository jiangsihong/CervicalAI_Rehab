"""
颈椎健康四级分级逻辑校验
包含四级分级的算法逻辑
"""

def calculate_cervical_grade(flexion_angle, extension_angle, 
                            left_lateral_angle, right_lateral_angle,
                            left_rotation_angle, right_rotation_angle):
    """
    根据颈椎活动度计算健康分级
    
    分级标准（参考临床指南）：
    1级（正常）：所有方向活动度正常，无疼痛
    2级（轻度）：1-2个方向活动度轻度受限，偶有不适
    3级（中度）：3-4个方向活动度明显受限，经常疼痛
    4级（重度）：5-6个方向活动度严重受限，持续疼痛
    
    角度参考范围（正常成年人）：
    - 前屈：45-60度
    - 后伸：45-75度  
    - 侧屈：每侧35-45度
    - 旋转：每侧60-80度
    """
    
    # 定义正常范围（最小值）
    normal_ranges = {
        'flexion': 45,
        'extension': 45,
        'lateral': 35,  # 左右侧屈
        'rotation': 60   # 左右旋转
    }
    
    # 计算各方向受限程度
    restricted_directions = 0
    
    # 前屈
    if flexion_angle < normal_ranges['flexion'] * 0.7:  # 严重受限
        restricted_directions += 2
    elif flexion_angle < normal_ranges['flexion'] * 0.9:  # 轻度受限
        restricted_directions += 1
    
    # 后伸
    if extension_angle < normal_ranges['extension'] * 0.7:
        restricted_directions += 2
    elif extension_angle < normal_ranges['extension'] * 0.9:
        restricted_directions += 1
    
    # 左侧屈
    if left_lateral_angle < normal_ranges['lateral'] * 0.7:
        restricted_directions += 2
    elif left_lateral_angle < normal_ranges['lateral'] * 0.9:
        restricted_directions += 1
    
    # 右侧屈
    if right_lateral_angle < normal_ranges['lateral'] * 0.7:
        restricted_directions += 2
    elif right_lateral_angle < normal_ranges['lateral'] * 0.9:
        restricted_directions += 1
    
    # 左旋转
    if left_rotation_angle < normal_ranges['rotation'] * 0.7:
        restricted_directions += 2
    elif left_rotation_angle < normal_ranges['rotation'] * 0.9:
        restricted_directions += 1
    
    # 右旋转
    if right_rotation_angle < normal_ranges['rotation'] * 0.7:
        restricted_directions += 2
    elif right_rotation_angle < normal_ranges['rotation'] * 0.9:
        restricted_directions += 1
    
    # 根据受限方向数量确定分级
    if restricted_directions == 0:
        return 'normal', 1, '颈椎活动度正常，无受限方向'
    elif restricted_directions <= 3:
        return 'mild', 2, f'轻度受限，{restricted_directions}个方向活动度轻度下降'
    elif restricted_directions <= 6:
        return 'moderate', 3, f'中度受限，{restricted_directions}个方向活动度明显下降'
    else:
        return 'severe', 4, f'重度受限，{restricted_directions}个方向活动度严重下降'

def calculate_grade_score(angles_dict):
    """从角度字典计算分级"""
    return calculate_cervical_grade(
        angles_dict.get('flexion_angle', 0),
        angles_dict.get('extension_angle', 0),
        angles_dict.get('left_lateral_flexion_angle', 0),
        angles_dict.get('right_lateral_flexion_angle', 0),
        angles_dict.get('left_rotation_angle', 0),
        angles_dict.get('right_rotation_angle', 0)
    )

def get_grade_description(grade):
    """获取分级描述"""
    descriptions = {
        'normal': {
            'level': '正常',
            'description': '颈椎活动度正常，无明显疼痛或不适',
            'recommendation': '继续保持良好姿势，定期进行颈椎保健操'
        },
        'mild': {
            'level': '轻度',
            'description': '颈椎活动度轻度受限，偶有不适感',
            'recommendation': '注意工作姿势，每天进行颈椎放松运动'
        },
        'moderate': {
            'level': '中度',
            'description': '颈椎活动度明显受限，经常感到疼痛',
            'recommendation': '建议就医检查，进行专业康复训练'
        },
        'severe': {
            'level': '重度',
            'description': '颈椎活动度严重受限，持续疼痛影响生活',
            'recommendation': '立即就医，可能需要专业治疗和康复'
        }
    }
    
    return descriptions.get(grade, descriptions['normal'])

def calculate_improvement_score(previous_angles, current_angles):
    """计算改善分数"""
    if not previous_angles or not current_angles:
        return 0
    
    # 计算各方向改善百分比
    improvements = []
    angle_types = ['flexion', 'extension', 'left_lateral', 'right_lateral', 'left_rotation', 'right_rotation']
    
    for angle_type in angle_types:
        prev_key = f'{angle_type}_angle'
        curr_key = f'{angle_type}_angle'
        
        prev = previous_angles.get(prev_key, 0)
        curr = current_angles.get(curr_key, 0)
        
        if prev > 0 and curr > 0:
            improvement = ((curr - prev) / prev) * 100
            improvements.append(improvement)
    
    if not improvements:
        return 0
    
    # 计算平均改善率
    avg_improvement = sum(improvements) / len(improvements)
    
    # 转换为0-100的分数
    if avg_improvement >= 20:
        return 100
    elif avg_improvement >= 10:
        return 75
    elif avg_improvement >= 5:
        return 50
    elif avg_improvement >= 0:
        return 25
    else:
        return 0  # 恶化

def validate_angles(flexion, extension, left_lateral, right_lateral, left_rotation, right_rotation):
    """验证角度数据合理性"""
    errors = []
    
    # 检查角度范围
    if flexion < 0 or flexion > 90:
        errors.append(f'前屈角度异常: {flexion}度 (正常范围: 0-90度)')
    
    if extension < 0 or extension > 90:
        errors.append(f'后伸角度异常: {extension}度 (正常范围: 0-90度)')
    
    if left_lateral < 0 or left_lateral > 60:
        errors.append(f'左侧屈角度异常: {left_lateral}度 (正常范围: 0-60度)')
    
    if right_lateral < 0 or right_lateral > 60:
        errors.append(f'右侧屈角度异常: {right_lateral}度 (正常范围: 0-60度)')
    
    if left_rotation < 0 or left_rotation > 90:
        errors.append(f'左旋转角度异常: {left_rotation}度 (正常范围: 0-90度)')
    
    if right_rotation < 0 or right_rotation > 90:
        errors.append(f'右旋转角度异常: {right_rotation}度 (正常范围: 0-90度)')
    
    # 检查左右对称性
    lateral_diff = abs(left_lateral - right_lateral)
    if lateral_diff > 20:
        errors.append(f'左右侧屈不对称: 左侧{left_lateral}度, 右侧{right_lateral}度')
    
    rotation_diff = abs(left_rotation - right_rotation)
    if rotation_diff > 25:
        errors.append(f'左右旋转不对称: 左侧{left_rotation}度, 右侧{right_rotation}度')
    
    return errors

if __name__ == "__main__":
    # 测试示例
    test_angles = {
        'flexion_angle': 50,
        'extension_angle': 55,
        'left_lateral_flexion_angle': 40,
        'right_lateral_flexion_angle': 38,
        'left_rotation_angle': 70,
        'right_rotation_angle': 68
    }
    
    grade, score, details = calculate_grade_score(test_angles)
    print(f"分级结果: {grade} (等级{score})")
    print(f"详细说明: {details}")
    
    desc = get_grade_description(grade)
    print(f"\n分级描述:")
    print(f"  等级: {desc['level']}")
    print(f"  描述: {desc['description']}")
    print(f"  建议: {desc['recommendation']}")
    
    # 验证角度
    errors = validate_angles(50, 55, 40, 38, 70, 68)
    if errors:
        print(f"\n角度验证警告:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n角度验证通过")
