from odoo import http
from odoo.http import request
import json
from datetime import timedelta
from odoo import fields

class OverviewController(http.Controller):

    @http.route('/feitas_iot/get_component_status', type='jsonrpc', auth='user')
    def get_component_status(self):
        env = request.env
        env['crose.component']._sync_overview_metrics()
        components = env['crose.component'].search_read(
            [],
            ['name', 'component_type', 'status']
        )
        stats = {
            'agents': env['fts.edge.agent'].search_count([]),
            'instances': env['fts.nr.instance'].search_count([]),
            'topics': env['fts.mqtt.topic'].search_count([]),
        }
        metrics_param = env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.metrics', '{}')
        metrics = {'cpu': '-', 'memory': '-', 'disk': '-', 'network': '-'}
        try:
            parsed = json.loads(metrics_param)
            if isinstance(parsed, dict):
                metrics.update(parsed)
        except Exception:
            pass
        now_dt = fields.Datetime.to_datetime(fields.Datetime.now())
        minute_ago = fields.Datetime.to_string(now_dt - timedelta(minutes=1))
        day_start = fields.Datetime.to_string(now_dt.replace(hour=0, minute=0, second=0, microsecond=0))
        records_last_min = env['fts.data.log'].search_count([('create_date', '>=', minute_ago)])
        records_today = env['fts.data.log'].search_count([('create_date', '>=', day_start)])
        reports_today = env['fts.data.model'].search_count([
            ('write_date', '>=', day_start),
            ('spreadsheet_binary_data', '!=', False),
        ])
        throughput = {
            'records_per_sec': round(records_last_min / 60.0, 2),
            'records_today': records_today,
            'reports_today': reports_today,
            'latency_ms': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.latency_ms', '-'),
        }
        protocol = {
            'modbus_points': env['fts.data.address'].search_count([('model_id.protocol', 'in', ['mobus-tcp', 'mobus-rtu'])]),
            'mqtt_topics': env['fts.mqtt.topic'].search_count([]),
            'smb_connections': env['fts.data.model'].search_count([('protocol', '=', 'smb')]),
        }
        online_components = {
            c['component_type']: c['status'] == 'online'
            for c in components
            if c.get('component_type')
        }
        topology = [
            {'label': 'Device Layer', 'ok': env['fts.nr.instance'].search_count([]) > 0},
            {'label': 'Node-RED', 'ok': online_components.get('nodered', False)},
            {'label': 'Redis', 'ok': online_components.get('redis', False)},
            {'label': 'CRose', 'ok': True},
            {'label': 'UI', 'ok': True},
        ]
        industry_mode = env['ir.config_parameter'].sudo().get_param(
            'feitas_iot.overview.industry_mode', 'manufacturing'
        )
        if industry_mode == 'agriculture':
            kpis = [
                {'label': 'Greenhouse Environment Index', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_env_index', '82')},
                {'label': 'Soil Moisture Health', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_soil_moisture', '76%')},
                {'label': 'Irrigation Status', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_irrigation', 'Normal')},
            ]
            trend_title = 'Growth Trend'
        else:
            kpis = [
                {'label': 'OEE', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_oee', '85%')},
                {'label': 'Line Utilization', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_utilization', '88%')},
                {'label': 'Alarms Today', 'value': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.kpi_alarm', '3')},
            ]
            trend_title = 'Energy / Output Trend'
        trend_points_param = env['ir.config_parameter'].sudo().get_param(
            'feitas_iot.overview.trend_points',
            '[65,68,70,72,69,75,78,80,79,82,84,85]'
        )
        trend_points = []
        try:
            parsed_points = json.loads(trend_points_param)
            if isinstance(parsed_points, list):
                trend_points = [float(v) for v in parsed_points if isinstance(v, (int, float))]
        except Exception:
            trend_points = []
        if not trend_points:
            trend_points = [65, 68, 70, 72, 69, 75, 78, 80, 79, 82, 84, 85]
        online_devices = env['fts.edge.agent'].search_count([('status', '=', 'online')])
        total_devices = env['fts.edge.agent'].search_count([])
        offline_devices = max(total_devices - online_devices, 0)
        asset = {
            'devices_total': total_devices,
            'digital_models': env['fts.data.model'].search_count([]),
            'running_flows': env['instance.flow.line'].search_count([]),
            'commands_today': env['ir.config_parameter'].sudo().get_param('feitas_iot.overview.commands_today', '0'),
            'online_devices': online_devices,
            'offline_devices': offline_devices,
        }
        return {
            'components': components,
            'overview': {
                'stats': stats,
                'metrics': metrics,
                'dashboard': {
                    'connectivity': {
                        'topology': topology,
                        'protocol': protocol,
                    },
                    'throughput': throughput,
                    'value_delivery': {
                        'industry_mode': industry_mode,
                        'kpis': kpis,
                        'trend_title': trend_title,
                        'trend_points': trend_points,
                    },
                    'asset_insight': asset,
                },
            }
        }
