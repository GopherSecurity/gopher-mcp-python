# Threading and ownership

This document describes the source implementation in this checkout. Installing
an older published SDK or native wheel does not provide these changes.

The Python wrapper coordinates agent and auth-object lifetimes. Native agent
operations also retain a handle for their duration when using a native library
built with the handle-lifetime fix at `gopher-orch` commit `db6dcb79`.

These are specific lifecycle guarantees, rather than a claim that every native
component, third-party provider, user callback, or application is memory-safe.

## Agent execution and disposal

| Operation | Contract |
| --- | --- |
| SDK initialization | Concurrent callers share one fully initialized library wrapper. An anticipated library-load failure is cached with its diagnostics. |
| `agent.run()` | At most one query executes on an agent. An overlapping call raises `AgentError` with an “already running” message. |
| `agent.run_detailed()` | Uses the same admission rules, translating execution errors into an `AgentResult`. |
| `agent.dispose()` while idle | Marks the agent disposed and releases its native ownership reference. Repeated calls do not release it twice. |
| `agent.dispose()` while running | Marks the agent disposed immediately and returns without waiting. The active call releases native ownership when it exits, including on an exception. |
| A query after disposal starts | Raises `AgentError` before entering native execution. |
| `agent.is_disposed()` | Reports whether disposal was requested. During a query this can be true before physical native cleanup finishes. |

Disposal does not cancel an active query. To wait for its completion, wait for
the application's worker future or thread. Do not interpret disposal as a query
deadline or assume that the native `timeout_ms` argument enforces cancellation.

Use a context manager or explicit `dispose()` for deterministic ownership.
A best-effort finalizer handles forgotten agents, but garbage collection is
not a substitute for an application shutdown sequence. An agent keeps the
library instance that created it for execution and cleanup.

`GopherAgent.shutdown()` resets Python initialization bookkeeping. It does not
dispose existing agents or unload the native library; callers still own their
agents. Restarting initialization uses the same loaded library wrapper.

## Parallel and asynchronous applications

Use independent agents for parallel queries. Calls on different agents do not
share an SDK-wide execution lock. Keep shared configuration read-only while
workers use it, and separately synchronize any mutable application state.

```python
from concurrent.futures import ThreadPoolExecutor

from gopher_mcp_python import GopherAgent


def ask(provider, model, url, question):
    with GopherAgent.create_with_url(provider, model, url) as agent:
        return agent.run(question)


def ask_many(provider, model, url, questions):
    with ThreadPoolExecutor(max_workers=4) as workers:
        futures = [
            workers.submit(ask, provider, model, url, question)
            for question in questions
        ]
        return [future.result() for future in futures]
```

Agent construction and execution are synchronous. In an async application,
run synchronous SDK work in a worker through `loop.run_in_executor()` or an
equivalent framework helper. Cancelling the Python awaiter does not stop a
native worker; let the worker finish and perform its cleanup.

Locks and native handles belong to their process. Create SDK objects inside
each worker process. Do not transfer handles between processes or reuse live
SDK objects inherited by a forked worker.

## Elicitation callbacks

Callbacks may execute on a native thread rather than the thread that called
`run()`. Callback data exposed as Python strings is copied; the wrapper retains
the callback object for the native agent lifetime and active native calls.

Synchronize shared application data accessed by a handler. A handler must not
wait for the query that invoked it, and a nested run on the same active agent
is rejected. A handler can request `agent.dispose()`: disposal is deferred
until the active query exits, allowing the handler to return without a
lifecycle-lock deadlock.

Browser interactions and handlers may still block according to their own
behavior. The SDK does not make user callbacks safe for arbitrary concurrent
application access.

## Auth objects

The following wrappers serialize native operations and destruction on each
object:

- `GopherAuthClient`
- `GopherOAuthClient`
- `GopherSessionManager`
- `GopherValidationOptions`
- `GopherAuthConfig`

The guard covers the native call and copying or freeing its results. Ordinary
`destroy()` waits for an active operation to leave the guard and then releases
the handle once. Same-thread reentrant destruction marks the object destroyed
and defers release until its active borrowed operations finish. Calls after
destruction is requested raise `RuntimeError`.

Validation borrows both its client and validation options. Auto-refresh borrows
the auth client, OAuth client, and session manager for the complete operation.
The SDK acquires these object locks in a consistent order. Independent auth
objects can execute concurrently.

`GopherAuth` also serializes its compound methods with initialization and
shutdown. Shutting down one instance does not shut down the process-wide auth
library while other SDK auth owners or calls remain active.

`gopher_shutdown_auth_library()` returns `False` while any SDK-managed native
auth object or operation remains active. Destroy the objects and wait for their
operations before retrying. It does not close other callers' handles.

Owned native strings, OAuth responses, registration responses, and temporary
configuration handles are released on their supported success and failure
paths, including empty strings and decoding errors. Use explicit cleanup or a
context manager for predictable release; wrappers also have best-effort
garbage-collection cleanup.

### Borrowing raw auth handles

`get_handle()` returns a borrowed pointer without extending its lifetime after
the method returns. Internal compound SDK operations hold the required guards.
External code performing a native call must hold `borrow_handle()` instead:

```python
with client.borrow_handle() as handle:
    result = custom_native_call(handle)
```

The pointer is valid only within the context. Keep borrowed sections short and
do not nest calls on other wrappers while holding a borrowed handle, which can
violate the SDK's lock ordering. Raw ctypes function calls bypass SDK lifecycle
coordination and must not race with auth-library shutdown.

## OAuth token stores

SDK OAuth resolution shares one refresh or acquisition per **store instance
and cache key**, across threads and event loops in the same process. Different
keys and different store instances can proceed independently. Callers for one
key use the first caller's refresh/acquisition operation and share its result.

Cancelling a waiter does not cancel the shared request. Shared work runs on
the initiating caller's event loop. Orderly shutdown that cancels the loop's
tasks (as `asyncio.run()` does) cancels the operation for all waiters and removes
it from the in-flight registry; a later request can retry. Keep that loop running
while shared work is needed, and drain or cancel tasks before closing it.

`InMemoryGopherAgentTokenStore` protects dictionary operations across threads
and event loops. Treat returned token records as read-only; replace them with
`set()` rather than mutating them in place. The store uses conditional writes
so a slow refresh cannot overwrite a newer token or reverse an external
deletion. A rejected refresh token is conditionally removed before fallback
authorization.

Custom stores must support every thread and event loop from which they are
used. Existing async `get()`, `set()`, and optional `delete()` implementations
remain supported. For atomic coordination with writers outside the SDK
resolver, implement:

```python
async def compare_and_set(key, expected, token) -> bool:
    # Atomically compare the current record with expected.
    # If it matches, store token (or delete when token is None) and return True.
    # Otherwise leave the record untouched and return False.
    ...
```

`expected` is the record previously returned by `get()`, or `None` for an
absent key. A persistent store should compare a revision or the relevant record
contents, rather than Python object identity. Legacy get/set/delete fallback
checks cannot make separate remote operations atomic. Multiple processes or
different store instances accessing shared storage need store-level
transactions or distributed coordination as well.

On refresh failure, a newer valid token is reused. Conditional publication
does not overwrite a changed record; if no valid current token can be reused,
resolution raises a cache-change error and the application can retry.

## Native requirements and validation

The SDK pins native source commit `db6dcb79`. Rebuild the native library with
`./build.sh` before relying on its native handle leases. Publishing a Python
wheel alone does not update installed native wheels. Publish the native source
commit and rebuilt platform artifacts alongside a release that includes this
fix so consumers can fetch and use the pinned revision.

Native agent FFI lookup retains an operation reference under the handle
registry lock. Final release removes the handle from the registry before
destruction, and destruction occurs outside that lock. Execution and trace
callback registration hold scoped references; overlapping native agent runs
are rejected. Direct FFI users must still balance their owned references and
avoid using a pointer after relinquishing ownership. Other low-level FFI object
APIs have not all been certified for arbitrary concurrent use.

Python regressions cover agent admission and deferred disposal, initialization,
callback retention, token refresh and cancellation, auth owner destruction,
and native allocation cleanup. The full Python suite completed with
**486 passed, 1 skipped** for this implementation.

Run the native handle registry's standalone tests with:

```bash
scripts/test-native-handle-lifetime.sh address
scripts/test-native-handle-lifetime.sh thread
```

Both sanitizer runs passed for the actual native handle implementation. The
changed agent FFI translation unit also passed a syntax compilation with the
configured native build flags. These checks cover the handle implementation;
they are not a sanitizer audit of the entire native SDK or its dependencies.
