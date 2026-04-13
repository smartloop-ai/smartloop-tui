"""PyInstaller runtime hook: default pathlib.Path.read_text to UTF-8 on Windows.

trl.chat_template_utils reads jinja files via Path.read_text() without
specifying encoding. On Windows the default is cp1252, which fails on
UTF-8 content. Monkey-patching here runs before any application imports.
"""
import sys

if sys.platform == "win32":
    import pathlib

    _original_read_text = pathlib.Path.read_text

    def _read_text_utf8(self, encoding=None, errors=None):
        if encoding is None:
            encoding = "utf-8"
        return _original_read_text(self, encoding=encoding, errors=errors)

    pathlib.Path.read_text = _read_text_utf8
