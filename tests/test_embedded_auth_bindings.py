import ctypes
import json
from types import SimpleNamespace
import pytest
from gopher_mcp_python.ffi.embedded_auth import EmbeddedAuthBindings, SPECS
from gopher_mcp_python.errors import AgentError

def test_missing_native_capability_does_not_break_legacy_library():
    bindings=EmbeddedAuthBindings(SimpleNamespace(_lib=object()))
    assert bindings.capabilities() is None
    with pytest.raises(AgentError,match='EMBEDDED_AUTH_UNAVAILABLE'): bindings.create('{}',{})

def test_capability_requires_all_symbols_and_exact_interface():
    for version in (1,2):
        exports={'gopher_orch_auth_'+key:(lambda *args: 0) for key in SPECS}
        exports['gopher_orch_auth_capabilities']=lambda:json.dumps({'version':version,'embedded_auth':True}).encode()
        bindings=EmbeddedAuthBindings(SimpleNamespace(_lib=SimpleNamespace(**exports)))
        assert bool(bindings.capabilities()) == (version==1)
        assert exports['gopher_orch_auth_next_event'].restype is ctypes.c_void_p
