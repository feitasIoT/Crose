from odoo import models, fields


class FtsNodeItem(models.Model):
    _name = "fts.node.item"
    _description = "Node Item"

    name = fields.Char(string="名称")
    key = fields.Char(string="Key")
    value_type = fields.Selection(
        [
            ("text", "Text"),
            ("json", "JSON"),
        ],
        string="类型",
        required=True,
        default="text",
    )
    value = fields.Text(string="Value")
    note = fields.Text(string="备注")
    node_id = fields.Many2one("fts.nr.node", string="节点", required=True, ondelete="cascade")

