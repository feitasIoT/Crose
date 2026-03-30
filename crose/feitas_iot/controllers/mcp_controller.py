from odoo import http
from odoo.http import request
import json
import logging
import uuid
import time

_logger = logging.getLogger(__name__)


class McpServerController(http.Controller):
    
    @http.route('/mcp/sse', type='http', auth='public', csrf=False, cors='*')
    def mcp_sse(self):
        """
        MCP SSE Endpoint for connecting clients.
        Sends the endpoint for POST messages.
        """
        # In a real Odoo deployment, streaming responses via Werkzeug/Odoo is tricky 
        # because of buffering and worker limits. 
        # However, for a simple MCP handshake, we can try to return a generator 
        # or just a single event pointing to the message endpoint.
        
        # NOTE: True SSE requires long-lived connections which Odoo's threaded/gevent 
        # model supports but might timeout.
        
        headers = [
            ('Content-Type', 'text/event-stream'),
            ('Cache-Control', 'no-cache'),
            ('Connection', 'keep-alive'),
            ('Access-Control-Allow-Origin', '*')
        ]
        
        session_id = str(uuid.uuid4())
        
        def stream():
            # Send the endpoint event as per MCP SSE spec
            # The client should POST messages to /mcp/message?session_id=...
            endpoint_url = f"/mcp/message?session_id={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"
            
            # Keep alive for a bit (simulation)
            # In production, this would wait for events from a bus
            # For now, we just establish the session.
            # Many MCP clients just need the endpoint and then use POST.
            yield f"data: started\n\n"
            
        return request.make_response(stream(), headers)

    @http.route('/mcp/message', type='jsonrpc', auth='public', methods=['POST'], csrf=False, cors='*')
    def mcp_message_json(self, session_id=None, **kwargs):
        """
        Handle JSON-RPC messages from MCP client via Odoo JSON-RPC.
        Note: Odoo's type='json' wraps input/output in JSON-RPC 2.0.
        MCP also uses JSON-RPC 2.0.
        
        If the client sends raw JSON body to a URL, type='json' expects 
        specific Odoo format. We might need type='http' to handle raw MCP JSON-RPC.
        """
        pass

    @http.route('/mcp/message', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    def mcp_message_http(self, session_id=None):
        """
        Handle raw JSON-RPC messages from MCP client.
        """
        try:
            data = request.get_json_data()
        except Exception:
            return request.make_response("Invalid JSON", status=400)

        jsonrpc_req = data
        method = jsonrpc_req.get('method')
        params = jsonrpc_req.get('params', {})
        msg_id = jsonrpc_req.get('id')
        
        response_result = None
        error = None

        registry = request.env['fts.mcp.tool.registry'].sudo()

        try:
            if method == 'initialize':
                response_result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "CRose MCP Server",
                        "version": "1.0.0"
                    }
                }
            elif method == 'notifications/initialized':
                # Client acknowledging initialization
                response_result = True
            elif method == 'tools/list':
                tools = registry.list_tools()
                response_result = {
                    "tools": tools
                }
            elif method == 'tools/call':
                name = params.get('name')
                args = params.get('arguments', {})
                result = registry.execute_tool(name, args)
                response_result = {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            elif method == 'ping':
                response_result = {}
            else:
                error = {"code": -32601, "message": "Method not found"}

        except Exception as e:
            _logger.exception("MCP Error")
            error = {"code": -32000, "message": str(e)}

        # Construct JSON-RPC response
        resp_obj = {
            "jsonrpc": "2.0",
            "id": msg_id
        }
        if error:
            resp_obj["error"] = error
        else:
            resp_obj["result"] = response_result

        return request.make_response(
            json.dumps(resp_obj), 
            headers=[('Content-Type', 'application/json')]
        )
