from odoo import models, fields

class FtsNrTag(models.Model):
    _name = "fts.nr.tag"
    _description = "Node-RED Tag"

    name = fields.Char(string="名称", required=True)
    color = fields.Integer(string="颜色索引")
