#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理 REST API 启动入口
说明：核心路由定义在 user_routes.py，供多个 Flask 服务复用。
"""

from flask import Flask, jsonify
from flask_cors import CORS

from user_routes import user_bp


app = Flask(__name__)
CORS(app)
app.register_blueprint(user_bp)


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'code': 1,
        'message': '请求的资源不存在'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'code': 1,
        'message': '服务器内部错误'
    }), 500


if __name__ == '__main__':
    print('启动用户管理 API 服务...')
    print('访问 http://localhost:5000/api/health 检查服务状态')
    app.run(debug=True, host='0.0.0.0', port=5000)
