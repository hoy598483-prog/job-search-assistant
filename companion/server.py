"""Run: python -m companion.server --extension-id <Chrome extension ID>"""
import argparse
import hmac
import json
import re
import secrets
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from companion.service import Companion


def make_handler(service, token, origin, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            return self.headers.get("Host", "").split(":")[0] in {"127.0.0.1", "localhost"}

        def reply(self, code, result):
            data = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(code)
            if self.allowed():
                self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", origin))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.end_headers()

        def do_GET(self):
            if self.path != "/handshake":
                return self.reply(404, {"error": "路径不存在"})
            # Tokens are delivered only through Chrome's registered native pipe.
            # A web page must not acquire a session token by probing localhost.
            self.reply(410, {"error": "请使用扩展本机桥接连接，此HTTP握手已停用"})

        def do_POST(self):
            self.connection.settimeout(10)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 3000000:
                    raise ValueError("请求过大或为空")
                body = self.rfile.read(length)
            except (ValueError, OSError):
                return self.reply(400, {"error": "请求长度无效或读取超时"})
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return self.reply(403, {"error": "连接口令不正确"})
            if self.path not in {"/action", "/chat-stream"} or self.headers.get("Content-Type") != "application/json":
                return self.reply(400, {"error": "请求路径或类型不允许"})
            if self.path == "/chat-stream":
                return self.stream_chat(body)
            try:
                result = service.handle(json.loads(body))
                self.reply(200, result)
            except (ValueError, TypeError, KeyError) as exc:
                self.reply(400, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "处理失败，未确认完成。请检查本地服务。"})

        def stream_chat(self, body):
            try:
                request = json.loads(body)
                if not isinstance(request, dict) or request.get("approved") is not True:
                    raise ValueError("发送聊天上下文需要确认")
                workspace = service.route(request.get("workspace"), request.get("direction"))
                from companion.providers import chat_prompt
                from companion.streaming import chat_stream
                messages, samples = request.get("messages"), request.get("samples", [])
                mode = request.get("mode", "chat")
                allow_web = request.get("allow_web") is True
                chat_prompt(messages, samples, mode=mode, allow_web=allow_web)
            except (ValueError, TypeError, KeyError) as exc:
                return self.reply(400, {"error": str(exc)})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", origin))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def emit(event):
                self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

            stream = chat_stream(messages, samples, mode=mode, allow_web=allow_web)
            try:
                for event in stream:
                    emit(event)
                service.audit("chat_stream", workspace, "ok")
            except (BrokenPipeError, ConnectionError, OSError):
                service.audit("chat_stream", workspace, "disconnected")
            except Exception as exc:
                try:
                    emit({"type": "error", "text": str(exc) if isinstance(exc, ValueError) else "流式调用失败，回复未完成"})
                except OSError:
                    pass
                service.audit("chat_stream", workspace, "failed")
            finally:
                stream.close()
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-id", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not re.fullmatch("[a-p]{32}", args.extension_id):
        parser.error("请输入 Chrome 扩展管理页面显示的 32 位扩展 ID")
    server, token = create_server(args.extension_id, args.port)
    server.timeout = 10
    print(f"仅本机连接：http://127.0.0.1:{args.port}\n本次口令（复制到扩展，关闭服务即失效）：{token}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def create_server(extension_id, port=8765, root=None):
    token = secrets.token_urlsafe(32)
    service = Companion(Path(root) if root else Path(__file__).resolve().parents[1])
    server = HTTPServer(("127.0.0.1", port), make_handler(service, token, "chrome-extension://" + extension_id, port))
    return server, token


if __name__ == "__main__":
    main()
