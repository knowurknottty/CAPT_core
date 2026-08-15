from __future__ import annotations
import asyncio, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from capt_runtime.drivers.provider import ProviderDriver

class _Server(BaseHTTPRequestHandler):
    seen = {}
    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers['Content-Length']))
        self.__class__.seen = {'path': self.path, 'body': json.loads(raw), 'auth': self.headers.get('Authorization')}
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
        payload = {'response':'CAPT TEST'} if self.path.endswith('/api/generate') else {'choices':[{'message':{'content':'CAPT TEST'}}]}
        self.wfile.write(json.dumps(payload).encode())
    def log_message(self, format, *args): return  # noqa: N802,A002

def test_openrouter_driver_provenance_and_secret_not_persisted(tmp_path: Path):
    server=ThreadingHTTPServer(('127.0.0.1',0),_Server); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    class Resolver:
        def resolve_for_execution(self, **_): return type('Task',(),{'objective':'minimal prompt'})()
    try:
        secret='synthetic-secret-not-to-persist'
        driver=ProviderDriver(str(tmp_path),provider_id='openrouter',model='deepseek/deepseek-v4-flash-0731',base_url=f'http://127.0.0.1:{server.server_port}/v1',api_key=secret,task_resolver=Resolver())
        out=asyncio.run(driver.submit({'driverRunId':'dr-1','missionId':'m-1','taskId':'t-1','contextSlice':{},'submittedAt':'2026-01-01T00:00:00Z'}))
        assert _Server.seen['path']=='/v1/chat/completions'
        assert _Server.seen['body']['model']=='deepseek/deepseek-v4-flash-0731'
        assert _Server.seen['auth']=='Bearer '+secret
        assert out['diagnostics']['provider']=='openrouter'
        assert out['diagnostics']['promptDigest'].startswith('sha256:')
        assert out['diagnostics']['responseDigest'].startswith('sha256:')
        assert secret not in str(out)
        assert secret not in Path(out['artifactCandidate']['artifactPath']).read_text()
    finally: server.shutdown(); server.server_close()

def test_ollama_driver_uses_native_generate_endpoint(tmp_path: Path):
    server=ThreadingHTTPServer(('127.0.0.1',0),_Server); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    class Resolver:
        def resolve_for_execution(self, **_): return type('Task',(),{'objective':'minimal prompt'})()
    try:
        driver=ProviderDriver(str(tmp_path),provider_id='ollama',model='local-model',base_url=f'http://127.0.0.1:{server.server_port}/v1',task_resolver=Resolver())
        out=asyncio.run(driver.submit({'driverRunId':'dr-2','missionId':'m-1','taskId':'t-1','contextSlice':{},'submittedAt':'2026-01-01T00:00:00Z'}))
        assert _Server.seen['path']=='/api/generate'
        assert _Server.seen['body']=={'model':'local-model','prompt':'minimal prompt','stream':False}
        assert _Server.seen['auth'] is None
        assert out['diagnostics']['endpointClass']=='local'
    finally: server.shutdown(); server.server_close()
