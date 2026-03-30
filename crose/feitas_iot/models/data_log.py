# -*- coding: utf-8 -*-

from odoo import models, fields

class FtsDataLog(models.Model):
    _name = 'fts.data.log'
    _description = 'Data Model History Log'
    _order = 'create_date desc'

    model_id = fields.Many2one('fts.data.model', string='Data Model', required=True, ondelete='cascade')
    value = fields.Text(string='Value')
