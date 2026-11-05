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
def borrow_owners(*objects):
    owners = {id(obj): obj for obj in objects if isinstance(obj, NativeHandleOwner)}
    with auth_call(), ExitStack() as stack:
        # Operations using several native objects always acquire locks in the
        # same order, including validation options and auto-refresh clients.
        for owner in sorted(owners.values(), key=id):
            stack.enter_context(owner._lifecycle_lock)
        for owner in owners.values():
            owner._ensure_not_destroyed()
        for owner in owners.values():
            owner._active_operations += 1
        try:
            yield
        finally:
            for owner in owners.values():
                owner._active_operations -= 1
                if owner._destroyed and owner._active_operations == 0:
                    owner._destroy_handle()


def native_operation(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with borrow_owners(*args, *kwargs.values()):
            return function(*args, **kwargs)

    return guarded


def native_constructor(function):
    @wraps(function)
    def guarded(self, *args, **kwargs):
        self._lifecycle_lock = threading.RLock()
        self._handle = None
        self._destroyed = True
        self._active_operations = 0
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

    @contextmanager
    def borrow_handle(self):
        """Borrow a handle for the entire duration of a native operation."""
        with borrow_owners(self):
            yield self._handle

    def _destroy_handle(self):
        lock = getattr(self, "_lifecycle_lock", None)
        if lock is None:
            return
        with auth_call(), lock:
            handle = self._handle
            if not handle:
                self._destroyed = True
                return
            # Mark before native teardown to make reentrant destruction safe.
            self._destroyed = True
            if self._active_operations:
                return
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
            return self._destroyed

    def __del__(self):
        try:
            self._destroy_handle()
        except Exception:
            pass
