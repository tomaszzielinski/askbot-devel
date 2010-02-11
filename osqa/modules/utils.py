import os
import types

MODULES_FOLDER = os.path.join(os.path.dirname(__file__))

MODULE_LIST = [
        __import__(f, globals(), locals(), [__name__])
        for f in os.listdir(MODULES_FOLDER)
        if os.path.isdir(os.path.join(MODULES_FOLDER, f)) and
           os.path.exists(os.path.join(MODULES_FOLDER, "%s/__init__.py" % f)) and
           not os.path.exists(os.path.join(MODULES_FOLDER, "%s/DISABLED" % f))
]

def call_modules_script(script_name):
    """
        utility function to call a certain script in all modules if exists
    """

    for m in MODULE_LIST:
        try:
            __import__('%s.%s' % (m.__name__, script_name), globals(), locals(), [m.__name__])
        except:
            pass

         
def get_module_dependencies():
    all_dependencies = []
    for m in MODULE_LIST:
        try:
            d = __import__('%s.dependencies' % m.__name__, globals(), locals(), [m.__name__])

            if hasattr(d, 'DJANGO_APPS') and getattr(d, 'DJANGO_APPS') is not None:
                all_dependencies.extend(list(getattr(d, 'DJANGO_APPS')))
                
        except:
            pass

    return all_dependencies

def get_module_settings():
    all_settings = {}

    for m in MODULE_LIST:
        try:
            s = __import__('%s.settings' % m.__name__, globals(), locals(), [m.__name__])
            defined = dict([(n, getattr(s, n)) for n in dir(s) if not n.startswith('__')])
            all_settings.update(defined)
        except:
            pass

    return all_settings

def get_module_models():
    all_models = {}

    for m in MODULE_LIST:
        try:
            m = __import__('%s.models' % m.__name__, globals(), locals(), [m.__name__])
            models = dict([
                    (n, model) for (n, model) in [(n, getattr(m, n)) for n in dir(m)]
                    if isinstance(model, (type, types.ClassType))
            ])
            all_models.update(models)
        except Exception, e:
            pass

    return all_models

def get_module_urlpatterns():
    patterns = []

    for m in MODULE_LIST:
        try:
            u = __import__('%s.urls' % m.__name__, globals(), locals(), [m.__name__])
            pattern = getattr(u, 'urlpatterns')
            patterns += pattern
        except Exception, e:
            pass

    return patterns

         
         
        