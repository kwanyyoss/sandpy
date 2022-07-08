# Test case for httpimport
# https://github.com/operatorequals/httpimport/

# Added sandboxing adaptation
if not '__mod' in globals():
    import sys
    globals()['__mod'] = sys.modules[__name__]

def hello():
    print("Hello world")
__mod.hello = hello

