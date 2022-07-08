# Test case for httpimport
# https://github.com/operatorequals/httpimport/

# Added sandboxing adaptation
if not '__mod' in globals():
    import sys
    globals()['__mod'] = sys.modules[__name__]

import hello2

# When sandboxed, 'globals()' shall be private.
tmp = __mod.hello2
del __mod.hello2
globals()['hello2'] = tmp
del tmp

def hello():
    print("Hello world")
    print(hello2)
__mod.hello = hello

