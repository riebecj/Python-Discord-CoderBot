class _DynamicModule(object):
    def load(self, code):
        execdict = {'__builtins__': None}  # optional, to increase safety
        exec(code, execdict)
        keys = execdict.get(
            '__all__',  # use __all__ attribute if defined
            # else all non-private attributes
            (key for key in execdict if not key.startswith('_')))
        for key in keys:
            setattr(self, key, execdict[key])
# replace this module object in sys.modules with empty _DynamicModule instance
# see Stack Overflow question:
# https://stackoverflow.com/questions/5365562/why-is-the-value-of-name-changing-after-assignment-to-sys-modules-name


import sys as _sys
_ref, _sys.modules[__name__] = _sys.modules[__name__], _DynamicModule()
