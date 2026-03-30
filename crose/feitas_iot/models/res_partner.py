# -*- coding: utf-8 -*-

from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    mqtt_username = fields.Char(string='MQTT 用户名', prefetch=False)
