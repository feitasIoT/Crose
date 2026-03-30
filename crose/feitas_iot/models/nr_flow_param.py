from odoo import models, fields

class FtsNrFlowParam(models.Model):
    _name = "fts.nr.flow.param"
    _description = "Node-RED Flow Parameter"

    name = fields.Char(string="参数名", required=True)
    value = fields.Char(string="值")
    type = fields.Selection([
        ('str', 'String'),
        ('num', 'Number'),
        ('bool', 'Boolean'),
        ('json', 'JSON'),
        ('env', 'Environment Variable')
    ], string="类型", default='str', required=True)
    description = fields.Char(string="说明")
    
    flow_id = fields.Many2one("fts.nr.flow", string="关联流程", ondelete="cascade")
    model_id = fields.Many2one("fts.data.model", string="关联数据模型", ondelete="cascade")
