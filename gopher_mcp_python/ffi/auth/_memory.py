"""Copy and release strings owned by the native auth API."""

from contextlib import contextmanager
from ctypes import byref, c_char_p


@contextmanager
def owned_string(functions):
    value = c_char_p()
    try:
        yield value
    finally:
        # Test the pointer, not value.value: an allocated empty string owns
        # memory too, and invalid UTF-8 must not skip cleanup.
        if value:
            free = functions.get("free_string")
            if free:
                free(value)


def read_owned_string(functions, name, *args, default=None):
    function = functions.get(name)
    if function is None:
        return default
    with owned_string(functions) as value:
        if function(*args, byref(value)) != 0:
            return default
        return value.value.decode("utf-8") if value.value else default
