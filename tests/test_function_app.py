"""The Azure Function file must import and wire up the shared collector."""

import importlib
import sys
import types
from pathlib import Path


def test_function_app_registers_timer(monkeypatch, tmp_path):
    # Minimal stand-in for the azure.functions package (only needed in Azure).
    registered = {}

    class FunctionApp:
        def timer_trigger(self, **kwargs):
            def wrap(fn):
                registered.update(kwargs, fn=fn)
                return fn

            return wrap

    azure = types.ModuleType("azure")
    functions = types.ModuleType("azure.functions")
    functions.FunctionApp = FunctionApp
    functions.TimerRequest = object
    azure.functions = functions
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.functions", functions)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'f.db'}")
    monkeypatch.syspath_prepend(str(Path(__file__).parent.parent / "function_app"))

    sys.modules.pop("function_app", None)
    importlib.import_module("function_app")

    assert registered["schedule"] == "0 */2 * * * *"
    assert registered["fn"].__name__ == "collect"
