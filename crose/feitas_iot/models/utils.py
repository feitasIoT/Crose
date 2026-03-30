# -*- coding: utf-8 -*-
import os
import logging

from odoo import exceptions
import base64

_logger = logging.getLogger(__name__)

import requests
import json

_logger = logging.getLogger(__name__)

class EmbeddingManager:
    @classmethod
    def clear_cache(cls):
        """由于现在使用远程 AI 容器，无需清理本地缓存"""
        pass

    @classmethod
    def encode(cls, env, text):
        """调用远程 AI 容器进行向量化"""
        # 从配置或环境变量获取 AI 服务地址，默认使用 docker-compose 中的服务名
        ai_endpoint = env['ir.config_parameter'].sudo().get_param('crose_iot.ai_endpoint', 'http://crose-ai:8000/embed')
        
        try:
            response = requests.post(ai_endpoint, json={'text': text}, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('vector', [])
        except Exception as e:
            _logger.error(f"Failed to get embedding from AI service: {e}")
            raise exceptions.UserError(f"AI 向量化服务调用失败: {e}")
