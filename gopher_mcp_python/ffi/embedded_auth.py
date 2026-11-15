"""Optional additive embedded authorization v1 ABI; owned poll strings are freed."""
import ctypes
import json
from .library import GopherOrchAgentOptions
from ..errors import AgentError

UNAVAILABLE = "EMBEDDED_AUTH_UNAVAILABLE: multiple independent MCP OAuth flows require embedded authorization interface v1"
SPECS = {
    "capabilities": (ctypes.c_char_p, []),
    "create": (ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(GopherOrchAgentOptions)]),
    "start": (ctypes.c_int32, [ctypes.c_void_p]),
    "next_event": (ctypes.c_void_p, [ctypes.c_void_p]),
    "next_store_request": (ctypes.c_void_p, [ctypes.c_void_p]),
    "complete_store_request": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]),
    "create_agent": (ctypes.c_int32, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]),
    "take_agent": (ctypes.c_void_p, [ctypes.c_void_p]),
    "retain": (ctypes.c_int32, [ctypes.c_void_p]),
    "cancel": (None, [ctypes.c_void_p]),
    "release": (None, [ctypes.c_void_p]),
}

class EmbeddedAuthBindings:
    def __init__(self, library):
        self.library = library
        self.functions = {}
        for name, (result, arguments) in SPECS.items():
            function = getattr(library._lib, "gopher_orch_auth_" + name, None)
            if function is None:
                self.functions = {}
                break
            function.restype, function.argtypes = result, arguments
            self.functions[name] = function

    def capabilities(self):
        if not self.functions: return None
        try:
            result = json.loads(self.functions["capabilities"]())
            return result if result.get("version") == 1 and result.get("embedded_auth") is True else None
        except (ValueError, TypeError, AttributeError): return None

    def create(self, inventory, options, runtime_options=None):
        if not self.capabilities(): raise AgentError(UNAVAILABLE)
        storage = self.library._build_agent_options(runtime_options)
        handle = self.functions["create"](inventory.encode(), json.dumps(options).encode(), storage.pointer if storage else None)
        if not handle: raise AgentError("EMBEDDED_AUTH_CONFIG: invalid embedded authorization configuration")
        return EmbeddedAuthContext(self, handle, storage)

class EmbeddedAuthContext:
    def __init__(self, bindings, handle, storage):
        self.bindings, self.handle, self.storage = bindings, handle, storage

    def _status(self, name, *args):
        if self.bindings.functions[name](self.handle, *args) != 0:
            raise AgentError("EMBEDDED_AUTH_STATE: native authorization operation rejected")

    def start(self): self._status("start")
    def create_agent(self, provider, model): self._status("create_agent", provider.encode(), model.encode())
    def complete_store(self, request_id, result): self._status("complete_store_request", request_id.encode(), json.dumps(result).encode())
    def _poll(self, name):
        raw = self.bindings.functions[name](self.handle)
        if not raw: return None
        text = self.bindings.library._decode_owned_c_string(raw)
        try: return json.loads(text)
        except (ValueError, TypeError): raise AgentError("EMBEDDED_AUTH_PROTOCOL: invalid native event") from None
    def event(self): return self._poll("next_event")
    def store_request(self): return self._poll("next_store_request")
    def take_agent(self):
        handle = self.bindings.functions["take_agent"](self.handle)
        if not handle: raise AgentError("EMBEDDED_AUTH_STATE: native authorization returned no agent")
        self.bindings.library._retain_agent_option_storage(handle, self.storage)
        return handle
    def cancel(self):
        if self.handle: self.bindings.functions["cancel"](self.handle)
    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            try: self.bindings.functions["release"](handle)
            finally: self.storage = None
