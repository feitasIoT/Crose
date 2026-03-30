import zipfile
import io
import os
import base64
from .utils import EmbeddingManager

from odoo import models, fields, api, exceptions


class FtsAiModel(models.Model):
    _name = "fts.ai.model"
    _description = "AI模型"

    name = fields.Char(string="名称", required=True)
    model_file = fields.Binary('模型压缩包 (.zip)', required=True, help="从 HuggingFace 下载的文件夹打成 zip 包上传")
    is_active = fields.Boolean('当前激活', default=False)
    local_path = fields.Char('本地解压路径', compute='_compute_local_path')

    @api.depends('is_active')
    def _compute_local_path(self):
        for record in self:
            if record.id:
                record.local_path = os.path.join(self.env['ir.attachment']._storage(), 'ai_models', str(record.id))
            else:
                record.local_path = False

    @api.constrains('is_active')
    def _check_single_active(self):
        # 确保全局只有一个激活的模型
        if self.search_count([('is_active', '=', True)]) > 1:
            raise exceptions.ValidationError("只能激活一个模型！")

    def action_deploy_model(self):
        """解压模型到持久化目录"""
        self.ensure_one()
        # 定义解压路径
        base_path = self.local_path
        
        if not os.path.exists(base_path):
            os.makedirs(base_path)

        # 解压二进制文件 (Odoo 的 Binary 是 base64 编码的 bytes)
        try:
            zip_data = base64.b64decode(self.model_file)
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zip_ref:
                zip_ref.extractall(base_path)
        except Exception as e:
            raise exceptions.UserError(f"解压模型文件失败: {e}")
        
        # 激活此模型并取消其他激活
        self.env['fts.ai.model'].search([('id', '!=', self.id)]).write({'is_active': False})
        self.write({'is_active': True})
        
        # 强制清理缓存中的旧模型
        EmbeddingManager.clear_cache()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '部署成功',
                'message': f'模型已部署到 {base_path} 并激活',
                'sticky': False,
            }
        }


class FtsAiDataset(models.Model):
    _name = "fts.ai.dataset"
    _description = "数据集"

    name = fields.Char(string="名称", required=True)


class FtsAiTraining(models.Model):
    _name = "fts.ai.training"
    _description = "模型训练"

    name = fields.Char(string="名称", required=True)

