from odoo import models, fields


class InstanceFlowLine(models.Model):
    _name = "instance.flow.line"
    _description = "Instance Flow Line"

    instance_id = fields.Many2one("fts.nr.instance", string="实例", required=True, ondelete="cascade")
    flow_id = fields.Many2one("fts.nr.flow", string="流程", required=True, ondelete="restrict")

