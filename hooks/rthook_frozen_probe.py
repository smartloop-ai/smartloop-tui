"""PyInstaller runtime hook: skip LlmFactory subprocess probe when frozen.

In a PyInstaller bundle sys.executable points to the bundled binary (slp),
not a Python interpreter.  The probe subprocess therefore fails with a CLI
parse error.  Monkey-patching _probe_model_load to return True causes the
factory to proceed directly to in-process model loading.
"""
import sys

if getattr(sys, "frozen", False):

    def _patch_probe():
        from smartloop.llms.llm_factory import LlmFactory

        _original = LlmFactory._probe_model_load

        @staticmethod
        def _skip_probe(path, config, logger):
            logger.info("PyInstaller bundle detected — skipping subprocess probe")
            return True

        LlmFactory._probe_model_load = _skip_probe

    try:
        _patch_probe()
    except Exception:
        pass
