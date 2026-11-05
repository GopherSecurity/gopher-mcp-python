# Threading and ownership

This document describes the Python implementation in this checkout. Installing
an older published Python SDK does not provide these changes.

The Python wrappers coordinate agent and auth-object lifetimes while using the
existing compatible native library. These protections do not require changes
to `gopher-orch` or newly built native binaries.

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

## Scope and validation

Agent lifetime protection is enforced by `GopherAgent`: native release is
deferred until its active query finishes. Auth wrappers similarly hold their
own guards during native execution and result cleanup. Updating the Python
package is sufficient for these wrapper protections; no native source update
or native rebuild is part of this change.

These rules apply when operations and cleanup go through the supported Python
agent and auth objects. Direct calls through ctypes, the internal
`GopherOrchLibrary` FFI wrapper, another language SDK, or the native C API bypass
the agent's Python lifecycle guard. Concurrent raw-handle operations require
their own coordination. Do not create multiple independent owners for one
native reference or use a pointer after its owner releases it. Protecting
arbitrary native FFI callers would require a separate native-library change.

Python regressions cover agent admission and deferred disposal, initialization,
callback retention, token refresh and cancellation, auth owner destruction,
and native allocation cleanup. The full Python suite completed with
**486 passed, 1 skipped** for this implementation.

These Python tests include controlled concurrency and allocation-ownership
checks and tests against the existing native library. They are not a sanitizer
audit of the native SDK or its dependencies, and do not prove that arbitrary
native code is memory-safe.
