import json

from odoo import models, fields, api


class FtsNrFlow(models.Model):
    _name = "fts.nr.flow"
    _description = "Node-RED Flow"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="名称", required=True)
    nr_id = fields.Char(string="Flow ID", required=True)
    type = fields.Char(string="类型")
    # FIXME：流程转应用，是需要填写很多内容，AI大模型需要的内容
    is_template = fields.Boolean("是模板")
    content = fields.Text("内容")

    instance_id = fields.Many2one("fts.nr.instance", string="实例", ondelete="cascade")
    data_model_id = fields.Many2one('fts.data.model', string="Data Model")

    tag_ids = fields.Many2many("fts.nr.tag", string="标签")
    param_ids = fields.One2many("fts.nr.flow.param", "flow_id", string="参数")
    heat = fields.Integer("热度")
    description = fields.Html("说明")
    prompt = fields.Text("提示词")

    def action_sync_to_knowledge(self):
        """批量同步流程数据到知识库并向量化"""
        Knowledge = self.env['fts.knowledge']
        created_records = Knowledge.browse()
        for record in self:
            # 构造知识库记录
            vals = {
                'name': f"Flow: {record.name}",
                'description': record.description or '',
                'json_source': record.content,
            }
            # 创建并收集记录
            created_records |= Knowledge.create(vals)
        
        # 批量向量化
        created_records.action_vectorize()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '同步成功',
                'message': f'已同步 {len(self)} 条流程到知识库并完成向量化',
                'sticky': False,
            }
        }

    def action_view_nodes(self):
        """
            打开节点以及节点的关联配置节点(config_node_ids)
        """
        self.ensure_one()
        action = self.env.ref("feitas_iot.action_fts_nr_node", raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res["display_name"] = "节点"
            res["name"] = "节点"
            Node = self.env["fts.nr.node"]
            nodes = Node.search([("flow_id", "=", self.id)])
            to_process = nodes
            seen_ids = set(nodes.ids)
            config_ids = set()
            while to_process:
                cfgs = to_process.mapped("config_node_ids")
                new_cfgs = cfgs.filtered(lambda r: r.id not in seen_ids)
                if not new_cfgs:
                    break
                new_ids = set(new_cfgs.ids)
                config_ids |= new_ids
                seen_ids |= new_ids
                to_process = new_cfgs

            if config_ids:
                res["domain"] = ["|", ("flow_id", "=", self.id), ("id", "in", sorted(config_ids))]
            else:
                res["domain"] = [("flow_id", "=", self.id)]
            res["context"] = {
                "default_flow_id": self.id,
            }
            return res
        return {}

    def _format_json_text(self, value):
        if value is None:
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped[0] not in ("{", "["):
                return value
            try:
                parsed = json.loads(value)
            except Exception:
                return value
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        return value

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "content" in vals:
                vals["content"] = self._format_json_text(vals.get("content"))
        return super().create(vals_list)

    def write(self, vals):
        if "content" in vals:
            vals["content"] = self._format_json_text(vals.get("content"))
        return super().write(vals)
