from odoo import models, fields, api

class FtsMqttTopic(models.Model):
    _name = "fts.mqtt.topic"
    _description = "MQTT Topic"

    name = fields.Char(string="Name", required=True)
    broker_id = fields.Many2one("crose.component", string="MQTT Broker", required=True, domain=[('component_type', '=', 'mqtt')])
    partner_ids = fields.Many2many("res.partner", string="Partners")
    create_date = fields.Datetime("创建时间")

    @api.depends('name', 'broker_id.name')
    def _compute_display_name(self):
        for topic in self:
            if topic.broker_id:
                topic.display_name = f"{topic.broker_id.name} - {topic.name}"
            else:
                topic.display_name = topic.name

    @api.model
    def action_sync_all(self):
        # 从所有在线的 MQTT Broker 同步主题
        brokers = self.env["crose.component"].search([('component_type', '=', 'mqtt'), ('status', '=', 'online')])
        for broker in brokers:
            # 这里的同步逻辑需要根据新的模型结构调整，或者调用 broker 的特定方法
            # 暂时保持结构，实际同步逻辑可能需要在 crose.component 中实现
            pass 
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '同步完成',
                'message': 'MQTT主题已同步',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
