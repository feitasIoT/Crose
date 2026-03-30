# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FtsKnowledge(models.Model):
    _name = 'fts.knowledge'
    _description = 'Knowledge Base for Node-RED'

    name = fields.Char(string='名称', required=True)
    description = fields.Text(string='详细描述')
    json_source = fields.Text(string='JSON源码')
    
    def action_vectorize(self):
        """调用 AI 模型进行向量化并保存"""
        from .utils import EmbeddingManager
        for record in self:
            if not record.json_source:
                continue
            # 使用 JSON 源码作为向量化的输入文本
            text_to_vector = f"Name: {record.name}\nDescription: {record.description or ''}\nJSON: {record.json_source}"
            try:
                vector = EmbeddingManager.encode(self.env, text_to_vector)
                if vector:
                    record.save_vector(vector)
            except Exception as e:
                raise models.ValidationError(f"向量化失败: {e}")

    def _register_hook(self):
        """
        在模块加载时确保数据库支持 vector 扩展并创建字段
        """
        # 手动执行 SQL 创建 vector 类型的列
        # paraphrase-multilingual-MiniLM-L12-v2 的维度为 384
        query = """
            CREATE EXTENSION IF NOT EXISTS vector;
            ALTER TABLE fts_knowledge 
            ADD COLUMN IF NOT EXISTS vector_data vector(384);
        """
        self.env.cr.execute(query)
        return super(FtsKnowledge, self)._register_hook()

    @api.model
    def search_similar_flows(self, query_vector, limit=3):
        """
        核心方法：使用 pgvector 的 <-> (欧氏距离) 进行相似度检索
        """
        # 将 Python 列表转换为 pgvector 识别的字符串格式 '[0.1, 0.2, ...]'
        vector_str = str(query_vector)
        
        sql = """
            SELECT id, name, flow_json, 
                   vector_data <-> %s AS distance
            FROM fts_knowledge
            ORDER BY distance ASC
            LIMIT %s
        """
        self.env.cr.execute(sql, (vector_str, limit))
        results = self.env.cr.dictfetchall()
        return results

    def save_vector(self, vector_list):
        """
        更新特定记录的向量值
        """
        self.ensure_one()
        sql = "UPDATE fts_knowledge SET vector_data = %s WHERE id = %s"
        self.env.cr.execute(sql, (str(vector_list), self.id))
