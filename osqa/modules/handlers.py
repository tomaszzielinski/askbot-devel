import types
from utils import MODULE_LIST, call_modules_script

call_modules_script('handlers')

MODULE_HANDLERS = [
        h for h in [
            getattr(m, 'handlers') for m in MODULE_LIST
            if hasattr(m, 'handlers')
        ]
        if type(h) == types.ModuleType
]

def get_all_handlers(name):
     return [
        h for h in [
            getattr(h, name) for h in MODULE_HANDLERS
            if hasattr(h, name)
        ]

        if callable(h)
     ]

def get_handler(name, default):
    all = get_all_handlers(name)
    return len(all) and all[0] or default
