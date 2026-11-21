"""
统一的JSON响应格式封装
规范返回的API格式
"""

from flask import jsonify
from datetime import datetime

def success(data=None, message='操作成功', code=200):
    """成功响应"""
    if data is None:
        data = {}
    
    response = {
        'success': True,
        'code': code,
        'message': message,
        'data': data,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    return jsonify(response), code

def error(message='操作失败', code=400, errors=None):
    """错误响应"""
    response = {
        'success': False,
        'code': code,
        'message': message,
        'errors': errors if errors else [],
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    return jsonify(response), code

def pagination_success(items, total, page, per_page, **kwargs):
    """分页成功响应"""
    data = {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page if per_page > 0 else 0
    }
    
    # 添加额外的数据
    for key, value in kwargs.items():
        data[key] = value
    
    return success(data)

def validation_error(errors):
    """验证错误响应"""
    return error('参数验证失败', 422, errors)

def not_found(message='资源未找到'):
    """未找到响应"""
    return error(message, 404)

def unauthorized(message='未授权访问'):
    """未授权响应"""
    return error(message, 401)

def forbidden(message='权限不足'):
    """禁止访问响应"""
    return error(message, 403)

def server_error(message='服务器内部错误'):
    """服务器错误响应"""
    return error(message, 500)

# 常用的HTTP状态码响应
responses = {
    200: lambda data=None, message='操作成功': success(data, message, 200),
    201: lambda data=None, message='创建成功': success(data, message, 201),
    204: lambda message='无内容': success({}, message, 204),
    400: lambda message='请求错误': error(message, 400),
    401: unauthorized,
    403: forbidden,
    404: not_found,
    422: validation_error,
    500: server_error
}

def make_response(code, *args, **kwargs):
    """根据状态码创建响应"""
    if code in responses:
        return responses[code](*args, **kwargs)
    else:
        return error(f'未知状态码: {code}', code)
