import json
import os
import requests
import socket
from odoo import models, fields, api

class CroseComponent(models.Model):
    _name = "crose.component"
    _description = "系统组件"

    name = fields.Char(string="组件名称", required=True)
    component_type = fields.Selection([
        ('mqtt', 'MQTT 服务'),
        ('iotdb', 'IoTDB'),
        ('ai', 'AI 服务'),
        ('npm', 'NPM 仓库'),
        ('redis', 'Redis'),
        ('nodered', 'Node-RED')
    ], string="组件类型", required=True)
    status = fields.Selection([
        ('online', '在线'),
        ('offline', '离线'),
        ('error', '错误')
    ], string="状态", default='offline', readonly=True)
    host = fields.Char(string="主机")
    port = fields.Integer(string="端口")
    url = fields.Char(string="URL地址")
    metadata = fields.Text(string="元数据")
    last_check_time = fields.Datetime(string="最后检查时间", readonly=True)
    error_reason = fields.Text(string="错误原因", readonly=True)

    @api.onchange('component_type')
    def _onchange_component_type(self):
        """根据组件类型设置默认元数据和端口"""
        if not self.component_type:
            return

        defaults = {
            'mqtt': {'metrics_port': 8082, 'tcp_port': 1883, 'ws_port': 8083},
            'iotdb': {'dn_rpc_port': 6667, 'dn_internal_port': 10730},
            'ai': {'health_endpoint': '/health'},
            'npm': {'registry_url': 'http://verdaccio-staging:4873'},
            'redis': {'db': 0},
            'nodered': {'admin_path': '/admin'}
        }
        
        # 设置默认端口
        port_defaults = {
            'mqtt': 1883,
            'iotdb': 6667,
            'npm': 4873,
            'redis': 6379,
            'nodered': 1880
        }

        # 设置默认主机名 (基于 docker-compose 服务名)
        host_defaults = {
            'mqtt': 'gmqtt',
            'iotdb': 'iotdb',
            'ai': 'crose-ai',
            'npm': 'verdaccio-staging',
            'nodered': 'nodered'
        }

        if self.component_type in defaults:
            self.metadata = json.dumps(defaults[self.component_type], indent=4)
        
        if self.component_type in port_defaults and not self.port:
            self.port = port_defaults[self.component_type]

        if self.component_type in host_defaults and not self.host:
            self.host = host_defaults[self.component_type]
            
        # 自动生成默认 URL
        if not self.url:
            if self.component_type == 'npm':
                self.url = f"http://{host_defaults.get('npm')}:{port_defaults.get('npm')}"
            elif self.component_type == 'nodered':
                self.url = f"http://{host_defaults.get('nodered')}:{port_defaults.get('nodered')}"
            elif self.component_type == 'ai':
                self.url = f"http://{host_defaults.get('ai')}:8000/health"

    def action_check_status(self):
        for component in self:
            component._check_status()

    def _check_status(self):
        self.ensure_one()
        check_func = getattr(self, f"_check_status_{self.component_type}", None)
        if check_func:
            check_func()
        else:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': f'未找到组件类型 {self.component_type} 的检查方法'
            })

    def _check_status_mqtt(self):
        # Example: Check gmqtt metrics endpoint
        try:
            metadata_dict = {}
            if self.metadata:
                try:
                    metadata_dict = json.loads(self.metadata)
                except json.JSONDecodeError:
                    pass
            metrics_port = metadata_dict.get('metrics_port', 8082)
            url = f"http://{self.host}:{metrics_port}/metrics"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
            else:
                self.write({
                    'status': 'offline', 
                    'last_check_time': fields.Datetime.now(),
                    'error_reason': f'HTTP 状态码异常: {response.status_code}'
                })
        except Exception as e:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': str(e)
            })

    def _check_status_iotdb(self):
        # Example: Check IoTDB RPC port
        try:
            with socket.create_connection((self.host, self.port), timeout=5):
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
        except Exception as e:
            self.write({
                'status': 'offline', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': f'无法连接到 {self.host}:{self.port} - {str(e)}'
            })

    def _check_status_ai(self):
        # Example: Check AI service health endpoint
        try:
            if not self.url:
                raise ValueError("未配置 AI 服务 URL")
            response = requests.get(self.url, timeout=5)
            if response.status_code == 200:
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
            else:
                self.write({
                    'status': 'offline', 
                    'last_check_time': fields.Datetime.now(),
                    'error_reason': f'AI 服务响应异常: {response.status_code}'
                })
        except Exception as e:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': str(e)
            })

    def _check_status_npm(self):
        # Example: Check Verdaccio main page
        try:
            if not self.url:
                raise ValueError("未配置 NPM 仓库 URL")
            response = requests.get(self.url, timeout=5)
            if response.status_code == 200:
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
            else:
                self.write({
                    'status': 'offline', 
                    'last_check_time': fields.Datetime.now(),
                    'error_reason': f'NPM 仓库响应异常: {response.status_code}'
                })
        except Exception as e:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': str(e)
            })

    def _check_status_redis(self):
        # Example: Check Redis PING command
        try:
            import redis
            r = redis.Redis(host=self.host, port=self.port, socket_connect_timeout=5)
            if r.ping():
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
            else:
                self.write({
                    'status': 'offline', 
                    'last_check_time': fields.Datetime.now(),
                    'error_reason': 'Redis PING 响应失败'
                })
        except Exception as e:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': str(e)
            })

    def _check_status_nodered(self):
        try:
            if not self.url:
                raise ValueError("未配置 Node-RED URL")
            response = requests.get(self.url, timeout=5)
            if response.status_code == 200:
                self.write({'status': 'online', 'last_check_time': fields.Datetime.now(), 'error_reason': False})
            else:
                self.write({
                    'status': 'offline', 
                    'last_check_time': fields.Datetime.now(),
                    'error_reason': f'Node-RED 响应异常: {response.status_code}'
                })
        except Exception as e:
            self.write({
                'status': 'error', 
                'last_check_time': fields.Datetime.now(),
                'error_reason': str(e)
            })

    def action_view_packages(self):
        self.ensure_one()
        return {
            'name': '安装包',
            'res_model': 'crose.nr.package',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'context': {'default_component_id': self.id},
            'domain': [('component_id', '=', self.id)],
            'target': 'current',
        }

    def _get_staging_storage_path(self, component=None):
        return '/mnt/verdaccio-staging'

    def _get_prod_storage_path(self, component=None):
        return '/mnt/verdaccio-prod'
