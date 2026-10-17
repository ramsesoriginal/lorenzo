"""Local wire fixture for simulator tests. Never authenticates against production."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlparse
note = None
audience = {"is_public": False, "entity_ids": [], "player_ids": []}
character = "11111111-1111-4111-8111-111111111111"
item = "22222222-2222-4222-8222-222222222222"
library = "33333333-3333-4333-8333-333333333333"
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, value, status=200):
        data=json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.send_header("ETag",'W/"2026-10-17T00:00:00Z"')
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path == "/me":
            return self.reply({"id":"user","locales":["en"],"players":[{"tenant_id":library,"characters":[{"entity_id":character,"name":"Brisk"}]}]})
        if "/held-by/" in path:
            return self.reply({"groups":[{"container":{"id":character,"name":"Equipped"},"carried":True,"item_instances":[{"entity_id":item,"title":"Ornate Spellbook","quantity":1,"descriptions":[{"content":"Pages bound between two covers.","locale":"en","from_entity":{"id":item,"name":"Book"}}],"physical_stats":[{"name":"Weight","value":2}],"tags":[{"name":"Magical","value":True}]}]}],"owners":[]})
        if path.endswith("/characters"): return self.reply({"items":[{"entity_id":character,"name":"Brisk"}],"total":1})
        if path.endswith("/groups"): return self.reply({"items":[{"id":"44444444-4444-4444-8444-444444444444","name":"The Company"}],"total":1})
        if path.endswith("/audience"): return self.reply(audience)
        if path.endswith("/editor"): return self.reply(note or {},200 if note else 404)
        if path.endswith("/information"): return self.reply({"items":[note] if note else [],"total":1 if note else 0})
        return self.reply({"title":"Not found"},404)
    def do_POST(self):
        global note
        data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or "{}")
        if self.path.endswith("/information"):
            note={"id":data["id"],"title":data["title"],"type":"note","is_public":False,"updated_at":"2026-10-17T00:00:00Z","created_by_name":"Pia","payloads":[{"id":"55555555-5555-4555-8555-555555555555","kind":"description","order":0,"updated_at":"2026-10-17T00:00:00Z","content":data["content"],"locale":data["locale"]}]}
            return self.reply(note,201)
        return self.reply({"title":"Not found"},404)
    def do_PUT(self):
        global audience
        data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or "{}")
        if self.path.endswith("/audience"):
            audience=data
            if note: note["is_public"]=data["is_public"]
            return self.reply(audience)
        return self.reply({"title":"Not found"},404)
ThreadingHTTPServer(("127.0.0.1",8874),Handler).serve_forever()
