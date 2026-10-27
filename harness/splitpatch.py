"""Run a harness script over an env's EASY split without touching the adapters: while the context is open, navital_gym.envs.<name>.load_env() defaults to
splits=("easy",), and the adapters' cached env loaders are cleared. Envs whose load_env takes no `splits` (or have no tasks_easy.jsonl) are skipped."""
import contextlib, functools, importlib, inspect, os

def has_easy(name):
    try:
        mod = importlib.import_module(f"navital_gym.envs.{name}")
        return "splits" in inspect.signature(mod.load_env).parameters and os.path.exists(os.path.join(os.path.dirname(mod.__file__), "tasks_easy.jsonl"))
    except Exception:
        return False

def _clear():
    for modname, attr in (("navital_gym.adapters.verifiers_env", "_navital_env"),):
        try:
            getattr(importlib.import_module(modname), attr).cache_clear()
        except Exception:
            pass

@contextlib.contextmanager
def easy_only(name):
    mod = importlib.import_module(f"navital_gym.envs.{name}")
    orig = mod.load_env
    mod.load_env = functools.partial(orig, splits=("easy",))
    _clear()
    try:
        yield
    finally:
        mod.load_env = orig
        _clear()

def apply_from_env(envs):
    """If HARNESS_SPLIT=easy: keep only envs that have an easy split and make their load_env() default to it for the rest of the process. Otherwise return envs unchanged."""
    if os.environ.get("HARNESS_SPLIT") != "easy":
        return envs
    keep = [e for e in envs if has_easy(e)]
    for name in keep:
        mod = importlib.import_module(f"navital_gym.envs.{name}")
        mod.load_env = functools.partial(mod.load_env, splits=("easy",))
    _clear()
    print(f"[HARNESS_SPLIT=easy] envs with an easy split: {keep}")
    return keep
