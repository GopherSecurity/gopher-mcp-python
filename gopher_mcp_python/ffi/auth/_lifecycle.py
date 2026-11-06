"""Internal auth object ownership and process-local lifecycle coordination."""

import threading
import weakref
from contextlib import ExitStack, contextmanager
from functools import wraps

library_lock = threading.RLock()
_active_calls = 0
_owners = weakref.WeakSet()


@contextmanager
def auth_call():
    global _active_calls
    with library_lock:
        _active_calls += 1
    try:
        yield
    finally:
        with library_lock:
            _active_calls -= 1


def can_shutdown():
    """Called with library_lock held; never acquire object locks here."""
    return _active_calls == 0 and not _owners


def library_state(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with library_lock:
            return function(*args, **kwargs)

    return guarded


@contextmanager
def borrow_owners(*objects, concurrent=False):
    owners = {id(obj): obj for obj in objects if isinstance(obj, NativeHandleOwner)}
    with auth_call(), ExitStack() as stack:
        # Admit dependent handles in a stable order. Concurrent readers retain
        # lifetime references without holding the state lock in native code.
        for owner in sorted(owners.values(), key=id):
            stack.enter_context(
                owner._borrow_operation(concurrent and owner._concurrent_reads)
            )
        yield


def native_operation(function):
    return _guard_operation(function, concurrent=False)


def concurrent_native_operation(function):
    return _guard_operation(function, concurrent=True)


def _guard_operation(function, concurrent):
    @wraps(function)
    def guarded(*args, **kwargs):
        with borrow_owners(*args, *kwargs.values(), concurrent=concurrent):
            return function(*args, **kwargs)

    return guarded


def native_constructor(function):
    @wraps(function)
    def guarded(self, *args, **kwargs):
        self._lifecycle_lock = threading.RLock()
        self._operation_condition = threading.Condition(self._lifecycle_lock)
        self._handle = None
        self._destroyed = True
        self._active_operations = 0
        self._active_threads = {}
        self._exclusive_operations = 0
        self._waiting_writers = 0
        self._closing = False
        with auth_call():
            try:
                function(self, *args, **kwargs)
                if self._handle:
                    with library_lock:
                        _owners.add(self)
            except BaseException:
                self._destroy_handle()
                raise

    return guarded


def synchronized(function):
    """Serialize compound high-level auth operations on one Python object."""

    @wraps(function)
    def guarded(self, *args, **kwargs):
        with self._lifecycle_lock:
            return function(self, *args, **kwargs)

    return guarded


class NativeHandleOwner:
    _destroy_function = ""
    _concurrent_reads = False

    @contextmanager
    def _borrow_operation(self, concurrent):
        thread = threading.get_ident()
        with ExitStack() as stack:
            if not concurrent:
                # OAuth clients share a curl easy handle. Keep their calls
                # exclusive, as well as mutations of read-concurrent objects.
                stack.enter_context(self._operation_condition)
            with self._operation_condition:
                self._check_admission(thread)
                own_calls = self._active_threads.get(thread, 0)
                if not concurrent and own_calls and not self._exclusive_operations:
                    raise RuntimeError(
                        "Cannot mutate an auth object inside a shared operation"
                    )
                if not concurrent:
                    self._waiting_writers += 1
                try:
                    while True:
                        busy = (
                            self._active_operations > own_calls
                            if not concurrent
                            else (self._exclusive_operations or self._waiting_writers)
                            and not own_calls
                        )
                        if not busy:
                            break
                        self._operation_condition.wait()
                        self._check_admission(thread)
                    self._active_operations += 1
                    self._active_threads[thread] = own_calls + 1
                    if not concurrent:
                        self._exclusive_operations += 1
                finally:
                    if not concurrent:
                        self._waiting_writers -= 1
                        self._operation_condition.notify_all()
            try:
                yield
            finally:
                with self._operation_condition:
                    self._active_operations -= 1
                    self._active_threads[thread] -= 1
                    if not self._active_threads[thread]:
                        del self._active_threads[thread]
                    if not concurrent:
                        self._exclusive_operations -= 1
                    release = self._destroyed and not self._active_operations
                    self._operation_condition.notify_all()
                if release:
                    self._destroy_handle()

    def _check_admission(self, thread):
        self._ensure_not_destroyed()
        if self._closing and not self._active_threads.get(thread):
            raise RuntimeError(f"{type(self).__name__} has been destroyed")

    @contextmanager
    def borrow_handle(self):
        """Borrow a handle for the entire duration of a native operation."""
        with borrow_owners(self):
            yield self._handle

    def _destroy_handle(self):
        lock = getattr(self, "_lifecycle_lock", None)
        if lock is None:
            return
        with auth_call(), self._operation_condition:
            self._closing = True
            self._operation_condition.notify_all()
            if self._active_threads.get(threading.get_ident()):
                self._destroyed = True
                return
            while self._active_operations:
                self._operation_condition.wait()
            handle = self._handle
            if not handle:
                self._destroyed = True
                return
            # Mark before native teardown to make reentrant destruction safe.
            self._destroyed = True
            self._handle = None
            try:
                from .loader import get_auth_functions

                destroy = get_auth_functions().get(self._destroy_function)
                if destroy:
                    destroy(handle)
            finally:
                with library_lock:
                    _owners.discard(self)

    def _is_handle_destroyed(self):
        with self._lifecycle_lock:
            return self._closing or self._destroyed

    def __del__(self):
        try:
            self._destroy_handle()
        except Exception:
            pass
