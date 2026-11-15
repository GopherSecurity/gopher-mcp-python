#!/usr/bin/env python3
"""Check actual loaded binary capability; package versions are not sufficient."""
from gopher_mcp_python.ffi.library import GopherOrchLibrary
from gopher_mcp_python.ffi.embedded_auth import EmbeddedAuthBindings, UNAVAILABLE

def main():
    library = GopherOrchLibrary.get_instance()
    if library is None: raise SystemExit(GopherOrchLibrary.get_load_error_message())
    capabilities = EmbeddedAuthBindings(library).capabilities()
    if not capabilities: raise SystemExit(UNAVAILABLE)
    print('Embedded authorization interface v1 available; async_store=' + str(capabilities.get('async_store',False)))

if __name__ == '__main__': main()
