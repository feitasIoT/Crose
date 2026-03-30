from odoo import models, fields, api


class FtsMqttUser(models.Model):
    _name = "fts.mqtt.user"
    _description = "MQTT User"

    name = fields.Char(string="Name", required=True)
    password = fields.Char(string="Password", required=True)
    broker_id = fields.Many2one("crose.component", string="MQTT Broker", required=True, domain=[('component_type', '=', 'mqtt')])
    partner_id = fields.Many2one("res.partner", string="联系人")

    status = fields.Selection(
        [
            ("active", "激活"),
            ("pause", "停用")
        ],
        string="状态",
        default="active",
    )

    _name_partner_unique = models.Constraint(
        'unique(name, partner_id)',
        '用户名和联系人的组合必须唯一！'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(FtsMqttUser, self).create(vals_list)
        # 增加 skip_broker_sync 上下文判断，防止从接口同步回来时又发起创建请求
        if not self.env.context.get('skip_broker_sync'):
            for record in records:
                if record.broker_id and record.name and record.password:
                    record.broker_id.api_create_users(record.name, record.password)
        return records