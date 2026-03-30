import json

from odoo import models, fields, api


class FtsNrNode(models.Model):
    _name = "fts.nr.node"
    _description = "Node-RED Node"

    name = fields.Char(string="名称", required=True)
    nr_id = fields.Char(string="Node ID", required=True)
    node_type = fields.Char(string="类型")
    content = fields.Text(string="内容")

    flow_id = fields.Many2one("fts.nr.flow", string="流程", required=True, ondelete="cascade")
    instance_id = fields.Many2one(
        "fts.nr.instance",
        string="实例",
        related="flow_id.instance_id",
        store=True,
        readonly=True,
    )
    config_node_ids = fields.Many2many(
        "fts.nr.node",
        "fts_nr_node_config_rel",
        "node_id",
        "config_node_id",
        string="配置节点",
    )
    item_ids = fields.One2many("fts.node.item", "node_id", string="配置项")

    def action_sync_to_knowledge(self):
        """批量同步节点数据到知识库并向量化"""
        Knowledge = self.env['fts.knowledge']
        created_records = Knowledge.browse()
        for record in self:
            # 构造知识库记录
            vals = {
                'name': f"Node: {record.name}",
                'description': f"Type: {record.node_type}",
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
                'message': f'已同步 {len(self)} 个节点到知识库并完成向量化',
                'sticky': False,
            }
        }

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
