from modules.utils import get_module_settings

__all__ = []

for k, v in get_module_settings().items():
    __all__.append(k)
    exec "%s = v" % k

