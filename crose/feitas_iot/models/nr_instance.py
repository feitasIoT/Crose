import json
import re
import uuid

import requests

from odoo import models, fields
from odoo.exceptions import UserError


class FtsNrInstance(models.Model):
    _name = "fts.nr.instance"
    _description = "IoT 实例"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="名称", required=True)
    ip_address = fields.Char(string="IP 地址", required=True)
    port = fields.Integer(string="端口", required=True, default=1880)
    # TODO 实例类型，分为本地、远程实例
    instance_type = fields.Selection(
        [
            ("local", "本地实例"),
            ("remote", "远程实例"),
        ],
        string="实例类型",
        required=True,
        default="local",
    )
    # TODO 远程实例需要选择代理
    edge_agent_id = fields.Many2one(
        "fts.edge.agent",
        string="边缘代理",
        ondelete="restrict",
        required=False,
    )
    status = fields.Selection(
        [
            ("online", "在线"),
            ("offline", "离线"),
            ("error", "异常"),
        ],
        string="状态",
        required=True,
        default="offline",
    )
    flow_ids = fields.One2many("instance.flow.line", "instance_id", string="流程")
    npm_registry_id = fields.Many2one("crose.component", string="NPM仓库", domain=[('component_type', '=', 'npm')])

    def update_status(self):
        for instance in self:
            if not instance.ip_address:
                instance.status = "offline"
                continue
            
            # Node-RED 通常可以通过访问根路径或 /settings 等接口来检查
            # 这里简单访问根路径
            url = "http://%s:%d" % (instance.ip_address, instance.port)
            try:
                response = requests.get(url, timeout=3)
                # 200-399 视为在线
                if 200 <= response.status_code < 400:
                    instance.status = "online"
                else:
                    instance.status = "error" # 连接成功但返回错误
            except Exception:
                instance.status = "offline"

    def _sync_nr_nodes_for_flow(
        self,
        flow_record,
        flow_detail,
        *,
        include_nodes=True,
        include_configs=False,
        include_subflows=False,
        global_nodes_by_nr_id=None,
    ):
        self.ensure_one()
        Node = self.env["fts.nr.node"]
        if not flow_record:
            return
        items = []
        if include_nodes:
            items.extend(flow_detail.get("nodes") or [])
        if include_configs:
            items.extend(flow_detail.get("configs") or [])
        if include_subflows:
            items.extend(flow_detail.get("subflows") or [])
        items = [i for i in items if isinstance(i, dict) and i.get("id")]
        nr_ids = [i["id"] for i in items]
        existing = Node.search([("flow_id", "=", flow_record.id)])
        existing_by_nr_id = {rec.nr_id: rec for rec in existing}

        def _collect_strings(value, out):
            if isinstance(value, dict):
                for v in value.values():
                    _collect_strings(v, out)
            elif isinstance(value, list):
                for v in value:
                    _collect_strings(v, out)
            elif isinstance(value, str):
                out.add(value)

        to_create = []
        for node in items:
            nr_id = node["id"]
            node_type = node.get("type")
            name = node.get("name") or node.get("label") or node_type or nr_id
            vals = {
                "name": name,
                "nr_id": nr_id,
                "node_type": node_type,
                "content": json.dumps(node, ensure_ascii=False),
                "flow_id": flow_record.id,
            }
            if global_nodes_by_nr_id is not None:
                strings = set()
                _collect_strings(node, strings)
                config_ids = sorted({global_nodes_by_nr_id[s] for s in strings if s in global_nodes_by_nr_id})
                vals["config_node_ids"] = [(6, 0, config_ids)]
            rec = existing_by_nr_id.get(nr_id)
            if rec:
                rec.write(vals)
            else:
                to_create.append(vals)
        if to_create:
            Node.create(to_create)
        stale = existing.filtered(lambda r: r.nr_id not in set(nr_ids))
        if stale:
            stale.unlink()

    def action_restart(self):
        return True

    def action_create(self):
        """
            创建远程实例
            一方面给agent发送创建消息
            另一方面在本地实例（代理上选择了本地实例）创建流程，以便收到远程实例创建成功后连接mqtt broker时发送的消息

            FIXME：目前是基于节点已有node-red实例，通过复制实例配置文件来创建新实例？如何在没有node-red实例的情况下创建新实例？
        """
        pass

    def action_start(self):
        """
        启动实例
        - 平台调用gmqtt broker发布消息，例如：agent/homeraspi/1/cmd
            payload: {"cmd": "start", "instance_id": 1, "instance_name": "nr2"}
        - 代理接收消息，根据cmd执行启动实例
        """
        self.ensure_one()
        if not self.edge_agent_id:
            raise UserError("远程实例必须选择边缘代理后才能启动。")

        # 实例-m2o-代理，代理-m2o-mqtt broker
        # FIXME: 不需要从系统配置中获取，而是从代理中获取
        config = self.env["ir.config_parameter"].sudo()
        publish_url = config.get_param("feitas_iot.gmqtt_publish_url") or ""
        if not publish_url:
            server_ip = config.get_param("feitas_iot.gmqtt_server_ip") or "127.0.0.1"
            server_port = config.get_param("feitas_iot.gmqtt_server_port") or "8083"
            publish_url = f"http://{server_ip}:{server_port}/v1/publish"
        publish_url = str(publish_url)

        body = {
            "topic_name": f"agent/create/{self.edge_agent_id.id}",
            "payload": json.dumps(
                {
                    "instance_id": self.id,
                    "instance_name": self.name,
                    "instance_type": self.instance_type,
                    "ip_address": self.ip_address,
                    "port": self.port,
                },
                ensure_ascii=False,
            ),
            "qos": 1,
            "retained": False,
        }

        try:
            response = requests.post(publish_url, json=body, timeout=15)
            response.raise_for_status()
        except Exception as e:
            raise UserError(f"调用 GMQTT 发布接口失败：{str(e)}")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "启动已提交",
                "message": f"已发布到 {body['topic_name']}",
                "type": "success",
                "sticky": False,
            },
        }




    def action_open_editor(self):
        self.ensure_one()
        action = self.env.ref("feitas_iot.action_node_red_editor_client", raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res["display_name"] = "Node-RED 编辑器"
            res["name"] = "Node-RED 编辑器"
            res['params'] = {
                'instance_id': self.id,
                'node_red_url': f"http://{self.ip_address}:{self.port}",
            }
            return res
        return {}

    def action_view_flows(self):
        self.ensure_one()
        action = self.env.ref("feitas_iot.action_fts_nr_flow", raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res["display_name"] = "应用"
            res["name"] = "应用"
            res["domain"] = [("instance_id", "=", self.id)]
            res["context"] = {
                "default_instance_id": self.id,
            }
            return res
        return {}

    def action_view_logs(self):
        self.ensure_one()
        if not self.edge_agent_id:
            raise UserError("该实例未配置边缘代理，无法读取运行日志。")
        action = self.env.ref("feitas_iot.action_node_red_logs_client", raise_if_not_found=False)
        if not action:
            raise UserError("未找到日志动作，请联系管理员。")
        res = action.read()[0]
        res["display_name"] = "日志"
        res["name"] = "日志"
        res["params"] = {
            "instance_id": self.id,
        }
        return res

    def action_test(self):
        self.ensure_one()
        import requests
        try:
            url = f"http://{self.ip_address}:{self.port}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                self.status = "online"
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '连接成功',
                        'message': 'Node-RED 实例连接正常',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.status = "error"
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '连接失败',
                        'message': f'服务器返回状态码: {response.status_code}',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        except Exception as e:
            self.status = "offline"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '连接错误',
                    'message': f'无法连接到 Node-RED: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_apply_flows(self):
        """
            实例选择的应用下发到NR中。
        """
        self.ensure_one()
        if not self.flow_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "应用完成",
                    "message": "未配置任何应用",
                    "type": "warning",
                    "sticky": False,
                },
            }

        ok_count = 0
        fail_count = 0
        error_messages = []

        for line in self.flow_ids:
            flow = line.flow_id
            if not flow:
                continue
            try:
                payload = self._nr_build_flow_payload(flow)
                self._nr_post_json("/flow", payload, timeout=30)
                ok_count += 1
            except Exception as e:
                fail_count += 1
                error_messages.append(f"{flow.display_name}: {str(e)}")

        message = f"成功：{ok_count}，失败：{fail_count}"
        if error_messages:
            message = f"{message}\n" + "\n".join(error_messages[:5])

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "应用完成",
                "message": message,
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
            },
        }

    def api_sync_flows(self):
        """
            同步实例的所有流程
            GET /flows
            Authorization	Bearer [token] - if authentication is enabled
            Node-RED-API-Version	v2
            response：v2 A flow response object that includes the current revision identifier of the flows
        """
        if not self:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '同步完成',
                    'message': '未选择任何实例',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        Flow = self.env['fts.nr.flow']
        Node = self.env["fts.nr.node"]
        ok_count = 0
        fail_count = 0
        error_messages = []

        for instance in self:
            try:
                flow_list = instance._nr_get_json('/flows')
                if isinstance(flow_list, dict):
                    flow_nodes = flow_list.get('flows') or []
                else:
                    flow_nodes = flow_list or []

                tabs = [
                    node for node in flow_nodes
                    if isinstance(node, dict) and node.get('type') == 'tab' and node.get('id')
                ]
                tab_ids = [t['id'] for t in tabs]

                global_detail = instance.api_sync_flow_global()
                global_vals = {
                    'name': 'Global',
                    'nr_id': 'global',
                    'type': 'global',
                    'content': json.dumps(global_detail, ensure_ascii=False),
                    'instance_id': instance.id,
                }
                global_flow = Flow.search([
                    ('instance_id', '=', instance.id),
                    ('type', '=', 'global'),
                    ('nr_id', '=', 'global'),
                ], limit=1)
                if global_flow:
                    global_flow.write(global_vals)
                    global_record = global_flow
                else:
                    global_record = Flow.create(global_vals)
                instance._sync_nr_nodes_for_flow(
                    global_record,
                    global_detail,
                    include_nodes=False,
                    include_configs=True,
                    include_subflows=True,
                    global_nodes_by_nr_id=None,
                )
                global_nodes = Node.search([("flow_id", "=", global_record.id)])
                global_nodes_by_nr_id = {rec.nr_id: rec.id for rec in global_nodes if rec.nr_id}

                existing_flows = Flow.search([
                    ('instance_id', '=', instance.id),
                    ('type', '=', 'tab'),
                    ('nr_id', 'in', tab_ids),
                ])
                existing_by_nr_id = {rec.nr_id: rec for rec in existing_flows}

                for tab in tabs:
                    flow_id = tab['id']
                    label = tab.get('label') or tab.get('name') or flow_id
                    flow_detail = instance.api_sync_flow_by_id(flow_id)
                    vals = {
                        'name': label,
                        'nr_id': flow_id,
                        'type': 'tab',
                        'content': json.dumps(flow_detail, ensure_ascii=False),
                        'instance_id': instance.id,
                    }
                    existing = existing_by_nr_id.get(flow_id)
                    if existing:
                        existing.write(vals)
                        flow_record = existing
                    else:
                        flow_record = Flow.create(vals)
                    instance._sync_nr_nodes_for_flow(
                        flow_record,
                        flow_detail,
                        include_nodes=True,
                        include_configs=True,
                        include_subflows=False,
                        global_nodes_by_nr_id=global_nodes_by_nr_id,
                    )

                stale_flows = Flow.search([
                    ('instance_id', '=', instance.id),
                    ('type', '=', 'tab'),
                    ('nr_id', 'not in', tab_ids),
                ])
                if stale_flows:
                    stale_flows.unlink()

                ok_count += 1
            except Exception as e:
                fail_count += 1
                error_messages.append(f'{instance.name}: {str(e)}')

        message = f'成功：{ok_count}，失败：{fail_count}'
        if error_messages:
            message = f'{message}\n' + '\n'.join(error_messages[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '同步完成',
                'message': message,
                'type': 'success' if fail_count == 0 else 'warning',
                'sticky': False,
            }
        }

    def api_sync_flow_by_id(self, flow_id):
        """
            根据流程id（来自 /flows）获取流程详细内容
            GET /flow/:id
            Header： Authorization	Bearer [token] - if authentication is enabled
            Arguments： id	The id of the flow. （If id is set to global, the global configuration nodes and subflow definitions are returned.）
            返回：
            {
                "id": "91ad451.f6e52b8",
                "label": "Sheet 1",
                "nodes": [ ],
                "configs": [ ],
                "subflows": [ ]
            }
        """
        self.ensure_one()
        if not flow_id:
            return {}
        return self._nr_get_json(f'/flow/{flow_id}')
    
    def api_sync_flow_global(self):
        """
            根据流程id（来自 /flows）获取流程详细内容
            GET /flow/global
            Header： Authorization	Bearer [token] - if authentication is enabled
            Arguments： 无
            返回：
            {
                "id": "global",
                "configs": [ ],
                "subflows": [ ]
            }
        """
        self.ensure_one()
        return self._nr_get_json('/flow/global')

    def _nr_get_json(self, path, timeout=15):
        self.ensure_one()
        url = f"http://{self.ip_address}:{self.port}{path}"
        headers = {
            'Node-RED-API-Version': 'v2',
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _nr_post_json(self, path, body, timeout=15):
        self.ensure_one()
        url = f"http://{self.ip_address}:{self.port}{path}"
        headers = {
            "Node-RED-API-Version": "v2",
        }
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
        try:
            return response.json()
        except Exception:
            return {}

    def _nr_generate_id(self):
        return f"{uuid.uuid4().hex[:7]}.{uuid.uuid4().hex[:7]}"

    def _nr_replace_ids(self, value, mapping):
        if isinstance(value, dict):
            return {k: self._nr_replace_ids(v, mapping) for k, v in value.items()}
        if isinstance(value, list):
            return [self._nr_replace_ids(v, mapping) for v in value]
        if isinstance(value, str) and value in mapping:
            return mapping[value]
        return value

    def _nr_render_item_value(self, value):
        if value is None:
            return value
        if not isinstance(value, str):
            return value

        def _resolve_path(record, path):
            current = record
            for part in path.split("."):
                if not part:
                    return ""
                current = getattr(current, part, None)
                if current is None:
                    return ""
            if isinstance(current, models.BaseModel):
                current.ensure_one()
                return current.id
            return current

        pattern = re.compile(r"\{\{\s*record\.([a-zA-Z_][\w\.]*)\s*\}\}")

        def _replace(match):
            resolved = _resolve_path(self, match.group(1))
            if resolved is None:
                return ""
            return str(resolved)

        return pattern.sub(_replace, value)

    def _nr_set_dict_path(self, target, path, value):
        if not isinstance(target, dict):
            return
        if not path:
            return
        parts = str(path).split(".")
        current = target
        for part in parts[:-1]:
            if not part:
                return
            nxt = current.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                current[part] = nxt
            current = nxt
        last = parts[-1]
        if last:
            current[last] = value

    def _nr_get_dict_path(self, target, path):
        if not isinstance(target, dict):
            return None
        if not path:
            return None
        parts = str(path).split(".")
        current = target
        for part in parts:
            if not part or not isinstance(current, dict) or part not in current:
                return None
            current = current.get(part)
        return current

    def _nr_build_flow_payload(self, flow):
        """
            构建Node-RED流程payload。
        """
        self.ensure_one()
        raw = flow.content or "{}"
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = {}

        nodes = []
        configs = []
        if isinstance(parsed, dict):
            if isinstance(parsed.get("nodes"), list):
                nodes = parsed.get("nodes") or []
            if isinstance(parsed.get("configs"), list):
                configs = parsed.get("configs") or []

        nodes = [n for n in nodes if isinstance(n, dict)]
        configs = [c for c in configs if isinstance(c, dict)]

        payload = {
            "id": self._nr_generate_id(),
            "label": flow.name or "",
            "nodes": nodes,
            "configs": configs,
        }

        Node = self.env["fts.nr.node"]
        def _parse_node_content(rec):
            raw_content = rec.content or "{}"
            try:
                val = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
            except Exception:
                return None
            return val if isinstance(val, dict) else None

        base_nr_ids = [
            n.get("id")
            for n in payload["nodes"] + payload["configs"]
            if isinstance(n, dict) and n.get("id")
        ]

        existing_config_nr_ids = {
            c.get("id") for c in (payload.get("configs") or []) if isinstance(c, dict) and c.get("id")
        }

        if base_nr_ids:
            base_records = Node.search([("instance_id", "=", flow.instance_id.id), ("nr_id", "in", base_nr_ids)])
            queue = list(base_records)
            seen_cfg_rec_ids = set()
            while queue:
                rec = queue.pop(0)
                for cfg in rec.config_node_ids:
                    if cfg.id in seen_cfg_rec_ids:
                        continue
                    seen_cfg_rec_ids.add(cfg.id)
                    cfg_dict = _parse_node_content(cfg)
                    if cfg_dict and cfg_dict.get("id") and cfg_dict["id"] not in existing_config_nr_ids:
                        payload["configs"].append(cfg_dict)
                        existing_config_nr_ids.add(cfg_dict["id"])
                    queue.append(cfg)

        all_nr_ids = [
            n.get("id")
            for n in payload["nodes"] + payload["configs"]
            if isinstance(n, dict) and n.get("id")
        ]
        if all_nr_ids:
            node_records = Node.search([("instance_id", "=", flow.instance_id.id), ("nr_id", "in", all_nr_ids)])
            node_by_nr_id = {rec.nr_id: rec for rec in node_records if rec.nr_id}
            credentials_by_nr_id = {}
            for node_dict in payload["nodes"] + payload["configs"]:
                if not isinstance(node_dict, dict):
                    continue
                nr_id = node_dict.get("id")
                rec = node_by_nr_id.get(nr_id)
                if not rec or not rec.item_ids:
                    continue
                if node_dict.get("type") == "mqtt-broker":
                    user_value = None
                    password_value = None
                    for item in rec.item_ids:
                        if item.key in ("user", "credentials.user"):
                            user_value = self._nr_render_item_value(item.value)
                        elif item.key in ("password", "credentials.password"):
                            password_value = self._nr_render_item_value(item.value)
                    if user_value is not None or password_value is not None:
                        node_dict["credentials"] = {
                            "user": user_value or "",
                            "password": password_value or "",
                        }
                        credentials_by_nr_id[nr_id] = {
                            "user": user_value or "",
                            "password": password_value or "",
                        }
                for item in rec.item_ids:
                    if not item.key:
                        continue
                    if node_dict.get("type") == "mqtt-broker" and item.key in (
                        "user",
                        "password",
                        "credentials.user",
                        "credentials.password",
                    ):
                        continue
                    rendered = self._nr_render_item_value(item.value)
                    if item.value_type == "json":
                        try:
                            parsed_json = json.loads(rendered) if isinstance(rendered, str) else rendered
                        except Exception as e:
                            raise UserError(f"Item 值不是合法 JSON：{item.key} ({str(e)})")
                        existing_value = self._nr_get_dict_path(node_dict, item.key)
                        if isinstance(existing_value, (dict, list)):
                            rendered = parsed_json
                        else:
                            rendered = json.dumps(parsed_json, ensure_ascii=False)
                    self._nr_set_dict_path(node_dict, item.key, rendered)

        mapping = {}
        for item in payload["nodes"] + payload["configs"]:
            old_id = item.get("id")
            if old_id and old_id not in mapping:
                mapping[old_id] = self._nr_generate_id()

        if all_nr_ids:
            credentials = {}
            for old_id, cred in credentials_by_nr_id.items():
                credentials[mapping.get(old_id, old_id)] = cred
            if credentials:
                payload["credentials"] = credentials

        payload = self._nr_replace_ids(payload, mapping)

        remapped_nodes = payload.get("nodes") or []
        remapped_ids = [n.get("id") for n in remapped_nodes if isinstance(n, dict)]
        if len(remapped_ids) != len(set(remapped_ids)):
            raise UserError("Flow 内存在重复节点 ID，无法应用。")

        return payload
        
