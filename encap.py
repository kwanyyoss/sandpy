#! /usr/bin/env python3

from IPython.terminal.embed import InteractiveShellEmbed
import IPython.core.error as IPython_error
import IPython.core.display
import ast
import string, _string
import functools, inspect

import types, math, random, datetime, re, json

from urllib.parse import urlparse

import textwrap

import os

from bases import ReadOnly_meta, ReadOnly2_meta, Freeze_meta, Object, Dict
from bases import HideBases, RException


try:
    gBuiltIns = Dict(vars(__builtins__))
except TypeError:
    gBuiltIns = Dict(dict(__builtins__))

del gBuiltIns['__import__']
del gBuiltIns['__loader__']
del gBuiltIns['__spec__']
del gBuiltIns['open']
del gBuiltIns['exec']
del gBuiltIns['eval']
del gBuiltIns['globals']
del gBuiltIns['type']


# loophole - reach global scope by walking an exception's traceback stack
for name in list(gBuiltIns.keys()):
    try:
        if issubclass(gBuiltIns[name], BaseException):
            del gBuiltIns[name]
    except TypeError:
        pass
del name

# loophole - use of "types.CodeType" bypasses parser filtering
del gBuiltIns['compile']

def LockedFn(orig: types.FunctionType):
    "Returns a wrapped function that can only be '__call__'ed"
    class fnwrapper(metaclass=Freeze_meta):
        "wrapped function usage of which is limited to just calling it"
        __signature__ = inspect.signature(orig)
        def __init__(self):
            super().__init__()
        def __call__(self, *argv, **kwargs):
            return orig.__call__(*argv, **kwargs)
        def __repr__(self):
            return self.__signature__.__repr__().replace('Signature',
                                                         'function', 1)
        @property
        def __dict__(self):
            return None
        def __setattr__(self, key, val):
            raise RuntimeError('Cannot modify - function is locked.')
        def __delattr__(self, key):
            raise RuntimeError('Cannot modify - function is locked.')

    functools.update_wrapper(fnwrapper, orig,
                             assigned=functools.WRAPPER_ASSIGNMENTS +
                                      ('__kwdefaults__',),
                             updated=())
    del fnwrapper.__wrapped__
    fnwrapper.lock()
    return fnwrapper()

try:                                    # wrap IPython utility functions as well
    if gBuiltIns['display'] == IPython.core.display.display:
        gBuiltIns['display'] = LockedFn(gBuiltIns['display'])
except KeyError:
    pass
if 'get_ipython' in gBuiltIns:
    del gBuiltIns['get_ipython']

class Globals(dict):
    def __init__(self, *argv, **kwargs):
        super().__init__(*argv, **kwargs)
        self.__locked__ = False
        if '__name__' in self:
            self.__name__ = self['__name__']
        if '__builtins__' in self and self['__builtins__'] != None:
            self.__builtins__ = self['__builtins__']

    def copy(self):
        return __class__(self)

    def __setitem__(self, item, val):
        if item.startswith('__') and getattr(self, '__locked__', False):
            return None
        return super().__setitem__(item, val)
    def __delitem__(self, item):
        if item.startswith('__') and getattr(self, '__locked__', False):
            return None
        return super().__delitem__(item)
    def pop(self, key, *argv):
        if key in self and key.startswith('__') and\
           getattr(self, '__locked__', False):
            return self[key]
        return super().pop(key, *argv)

    def __setattr__(self, attr, val):
        if not getattr(self, '__locked__', False):
            return super().__setattr__(attr, val)
        raise AttributeError(f"'{self.__class__.__name__}' attribute " +
                             f"'{attr}' is read-only")
    def __delattr__(self, attr):
        if not getattr(self, '__locked__', False):
            return super().__delattr__(attr)
        raise AttributeError(f"'{self.__class__.__name__}' attribute " +
                             f"'{attr}' is read-only")

    def lock(self):
        if not self.__locked__:
            if '__name__' in self:
                self.__name__ = self['__name__']
            if '__builtins__' in self and self['__builtins__'] != None:
                self.__builtins__ = self['__builtins__']
            self.__locked__ = True
        return self

    @property
    def __dict__(self):                 # also kills "vars(self)"
        return None

    @staticmethod
    def check(g):
        if not '__builtins__' in g or g['__builtins__'] == None:
            return __class__(dict(g, __builtins__ = {}))
        elif not isinstance(g, Globals):
            return __class__(g)
        return g

    def restore_builtins(self):
        builtins = getattr(self, '__builtins__', None)
        if builtins != None:
            super().__setitem__('__builtins__', builtins)
        if hasattr(self, '__name__'):
            super().__setitem__('__name__', self.__name__)

    def publish(self, mkapi):
        return Globals_pub(self).as_dict(mkapi)

class Globals_pub(metaclass = ReadOnly_meta):
    __repr__ = object.__repr__

    def __init__(self, d: Globals):
        self.g = d

    def __getitem__(self, item):
        return self.g[item]
    def __setitem__(self, item, val):
        self.g[item] = val
    def __delitem__(self, item):
        del self.g[item]

    def __contains__(self, key):
        return key in self.g
    def len(self):
        return len(self.g)
    def iter(self):
        return self.g.iter()
    def clear(self):
        self.g.clear()
        self.g.restore_builtins()
    def get(self, key, *argv):
        return self.g.get(key, *argv)
    def items(self):
        return self.g.items();
    def keys(self):
        return self.g.keys();
    def pop(self, key, *argv):
        return self.g.pop(key, *argv)
    def popitem(self):
        ret = self.g.popitem()
        self.g.restore_builtins()
        return ret
    def setdefault(self, key, *argv):
        return self.g.setfault(key, *argv)
    def update(self, *argv, **kwargs):
        self.g.update(*argv, **kwargs)
        self.g.restore_builtins()
    def values(self):
        return self.g.values()

    def make_interface(self, makeapi):
        "Returns an Object instance containing only the interface (methods)"
        intf = Object()
        intf.__contains__ = makeapi('fn = lambda self, k: contains(k)',
                                    contains = self.__contains__).__get__(intf)
        intf.__getitem__ = makeapi('fn = lambda self, i: getitem(i)',
                                   getitem = self.__getitem__).__get__(intf)
        intf.__setitem__ = makeapi('fn = lambda self, i, v: setitem(i, v)',
                                   setitem = self.__setitem__).__get__(intf)
        intf.__delitem__ = makeapi('fn = lambda self, i: delitem(i)',
                                   delitem = self.__delitem__).__get__(intf)
        intf.iter = makeapi('fn = lambda self: i()',
                            i = self.iter).__get__(intf)
        intf.clear = makeapi('fn = lambda self: clear()',
                             clear = self.clear).__get__(intf)
        intf.len = makeapi('fn = lambda self: l()', l = self.len).__get__(intf)
        intf.get = makeapi("""
def fn(self, key, *argv):
  return get(key, *argv)
""",                       get = self.get).__get__(intf)
        intf.items = makeapi('fn = lambda self: items()',
                             items = self.items).__get__(intf)
        intf.keys = makeapi('fn = lambda self: keys()',
                            keys = self.keys).__get__(intf)
        intf.pop = makeapi("""
def fn(self, key, *argv):
  return pop(key, *argv)
""",                       pop = self.pop).__get__(intf)
        intf.popitem = makeapi('fn = lambda self: popi()',
                               popi = self.popitem).__get__(intf)
        intf.setdefault = makeapi("""
def fn(self, key, *argv):
  return setdefault(key, *argv)
""",                              setdefault = self.setdefault).__get__(intf)
        intf.update = makeapi("""
def fn(self, key, *argv, **kwargs):
  return update(key, *argv, **kwargs)
""",                          update = self.update).__get__(intf)
        intf.values = makeapi('fn = lambda self: values()',
                              values = self.values).__get__(intf)
        intf.lock()
        return intf

    def as_dict(self, mkapi):
        def blocked(a):
            raise AttributeError("'dict' object has no attribute '" + a + "'")
        w = self.make_interface(mkapi).wrap()
        w.__class__.__setattr__ = mkapi("fn = lambda self, attr, v: b(attr)",
                                        b=blocked)
        w.__class__.__delattr__ = mkapi("fn = lambda self, attr: b(attr)",
                                        b=blocked)
        w.__class__.lock()
        return w


random.seed()


def restring(s):
    return re.subn('\\\\', '\\\\\\\\', s)[0]

def IPythonShellInteract(**kwargs):
    from IPython.terminal.interactiveshell import InteractiveShell

    prog = Interact.prog = InteractiveShellEmbed
    kwargs['__return__'] = { 'prog': prog,
                             'exec': exec }
                             
    level = 0
    if '_NESTLVL' in kwargs and type(kwargs['_NESTLVL']) == int and\
       kwargs['_NESTLVL'] > 0:
        level = kwargs['_NESTLVL']

    def Final_body(ns):
        ns['__doc__'] = "Base class for when the class itself is immutable"
        ns['__repr__'] = object.__repr__
    g = Globals({ '__builtins__': gBuiltIns.copy(),
                  '__name__': '__?none?__',
                  'fn': LockedFn(LockedFn),
                  'types': Rtypes,
                  'math': Rmath,
                  'random': Rrandom,
                  'datetime': Rdatetime,
                  're': Rre,
                  'json': Rjson,
                  'pyjwt': Rjwt_exp,
                  'wasmtime': Rwasmtime_exp,
                  'Exception': RException,
                  'ImportError': RImportError,
                  'ModuleNotFoundError': RModuleNotFoundError,
                  'istype': makeapi("""
def fn(v):
  'Whether the argument is a type (e.g. class) instead of a term'
  return cl(v)
  """,                              cl = lambda x: isinstance(x, type)),
                  'Final': types.new_class('Final', (),
                                           { 'metaclass': ReadOnly_meta },
                                           Final_body),
                  'raiseStopIteration': makeapi("""
def fn(v=None):
  '''""" + '"raise StopIteration(v)"' + """'''
  raise e(v)
 """,                                                 e=StopIteration),
                  'raiseStopAsyncIteration': makeapi("""
def fn(v=None):
  '''""" + '"raise StopAsyncIteration(v)"' + """'''
  raise e(v)
 """,                                                 e=StopAsyncIteration) })
    del Final_body

    ipython_capture = Globals({ 'ipython': None, '__builtins__': {} })
    ipython_proxy = Object()
    def run_line_magic(magic_name, line, stack_depth=1):
        if magic_name.startswith('pinfo'):
            return ipython_capture['ipython'].run_line_magic(magic_name, line,
                                                             stack_depth)
        raise RuntimeError('forbidden magic - ' + "'" + magic_name + "'")
        return None
    def set_next_input(s, replace=False):
        return ipython_capture['ipython'].set_next_input(s, replace)
    ipython_proxy.run_line_magic = makeapi("""
def fn(magic_name, line, stack_depth=1):
  '''
""" + restring(textwrap.dedent('        ' +
                               InteractiveShell.run_line_magic.__doc__)) + """
  '''
  return o(magic_name, line, stack_depth)
""",                                       o = run_line_magic)._c
    ipython_proxy.set_next_input = makeapi("""
def fn(s, replace=False):
  '''
""" + restring(textwrap.dedent('        ' +
                               InteractiveShell.set_next_input.__doc__)) + """
  '''
  return o(s, replace)
""",                                       o = set_next_input)._c
    ipython_proxy.lockdown(makeapi)
    prog.get_ipython = makeapi("""def fn(instance):
  '''
""" + restring(textwrap.dedent('        ' +
                               InteractiveShell.get_ipython.__doc__)) + """
  '''
  global ipython
  if ipython == None:
    ipython = instance
  return proxy""",             globals=ipython_capture, proxy=ipython_proxy)

    g['__builtins__']['type'] = makeapi('''def fn(obj, *argv, **kwargs):
  return real(obj, *argv, **kwargs)''', real=Rtype)._c
    g['__builtins__']['setattr'] = makeapi('''def fn(obj, attr, val):
  return real(obj, attr, val)''',          real=Rsetattr)._c

    # Test case for the DMZ shim code
#    g['test_dmz'] = makeapi("""
#def fn():
#  nonlocal __builtins__
#  del __builtins__
#  global open
#  return open
#""",                        )

    localmod = types.SimpleNamespace()
    cauterize(g)
    with Importer(g.copy(), cauterize).remote_repo(["__init__"],
                                                    "file:") as importer:
        def file_prot_filter(imp, fullname):
            if fullname.startswith(os.sep):
                raise ValueError("'" + fullname + "' is not a valid path")
            return imp(fullname)
        ldr = makeapi("fn = lambda _=None: ldr",
                      ldr=file_prot_filter.__get__(importer.get_loader("__init__"))
                     )._c
    localmod.__loader__ = g['__loader__'] = ldr
    localmod.__file__ = g['__file__'] = 'file:__init__.py'
    localmod.__path__ = g['__path__'] = 'file:'
    del ldr, importer

    # "hackme" is married to the shell instance.  It is an example of things
    # that are not available to an imported module.  If needed by a module
    # function, it should be passed in parameters originating from a shell
    # instance.
    if level > 0:
        g['hackme'] = g['makeapi'](f'''
def fn(**kwargs) -> object:
  "nest another interactive shell"
  kwargs["_NESTLVL"] = {level + 1}
  return real(**kwargs)
''',                               real=hackme)._c
    else:
        g['hackme'] = g['makeapi']('def fn(**kwargs): return real(**kwargs)',
                                   real=hackme)._c

    g['__mod'] = localmod
    g.lock()                            # done changing contents of "globals()"


    levelstr = str(level) if level > 0 else ''
    try:
        g['astxfmr'] = [ RNodeTransformer(IPython_error.InputRejected,
                                          IPython_error.InputRejected) ]
        ret = eval(f'''(__return__["prog"](banner1="Nest IPython {levelstr}",
                                           exit_msg="Unnest IPython {levelstr}",
                                           ast_transformers=astxfmr),
                        __return__["exec"]("""global astxfmr\\ndel astxfmr"""),
                        __return__["exec"]("__return__ = None"),
                       )[0]()''', g, kwargs)
    except RException as r_exc:
        if level == 1:
            r_exc.access_verify = prog
        raise r_exc
    finally:
        del levelstr

    if ret != None:
        return ret
    try:
        return getattr(localmod, '__return__', kwargs['__return__'])
    except KeyError:
        pass
    return None

def cauterize(g: Globals):
    """
    Adjusts and seals __builtins__ in a Globals object
    """
    g['__builtins__']['safe_format'] = makeapi('''def fn(self, *argv, **kwargs):
  "Fix Python's unsafe formatspec.format(...)"
  return real(self, *argv, **kwargs)''',       real=Rsafe_format.__get__(
                                                      g['__builtins__']))._c
    g['__builtins__']['safe_format_map'] = makeapi('''def fn(self, map):
  "Fix Python's unsafe formatspec.format_map(...)"
  return real(self, map)''',                   real=Rsafe_format_map.__get__(
                                                      g['__builtins__']))._c
    g['__builtins__']['super'] = makeapi('''def fn(T, *argv):
  return real(T, *argv)''',              real=Rsuper.__get__(g['__builtins__']))._c
    g['__builtins__']['getattr'] = makeapi('''
def fn(obj, attr, *argv, binder=None):
  return real(obj, attr, *argv, binder=binder)
''',                                       real=Rgetattr.__get__(
                                                  g['__builtins__']))._c

    g['__builtins__']['globals'] = (lambda : g.publish(makeapi)).__call__
    g['__builtins__']['exec'] = makeapi("""
def fn(code, globals=None, locals=None):
  '''
  Replacement for a restricted scope.  The only difference is when locals
  is given but not globals, in which case this version will default to only
  the __builtins__.  For the original behavior, pass in globals=globals().
  '''
  if globals == None:
    if locals == None:
      return real(code, 'exec', g)
    else:
      return real(code, 'exec', { '__builtins__': g['__builtins__'] }, locals)
  return real(code, 'exec', globals, locals)
""",                                    real=Rexec, g=g)._c
    g['__builtins__']['eval'] = makeapi("""
def fn(code, globals=None, locals=None):
  '''
  Replacement for a restricted scope.  The only difference is when locals
  is given but not globals, in which case this version will default to only
  the __builtins__.  For the original behavior, pass in globals=globals().
  '''
  if globals == None:
    if locals == None:
      return real(code, 'eval', g)
    else:
      return real(code, 'eval', { '__builtins__': g['__builtins__'] }, locals)
  return real(code, 'eval', globals, locals)
""",                                    real=Rexec, g=g)._c

    importer = None                     # (forward) declaration
    def generic_repo_context(ctxtmgr):
        def pt():
            y = ctxtmgr.__enter__()
            return y.get_loader.__get__(y)
        class mgr(metaclass=Freeze_meta):
            __enter__ = makeapi("""def fn(self):
  loader = f()
  return (lambda fullname: loader(fullname)).__call__""",
                                f=pt)
            __exit__ = makeapi("""
def fn(self, exc_type, exc_value, exc_tb):
  return f(exc_type, exc_value, exc_tb)
""",                           f = ctxtmgr.__exit__.__get__(ctxtmgr))
            @property
            def __dict__(self):
                return None
            def __setattr__(self, key, val):
                raise RuntimeError('Cannot modify - context object is read-only.')
        mgr.lock()
        return mgr()

    def remote_repo(modules, base_url, zip_pwd=None):
        scheme = urlparse(base_url).scheme
        if not (scheme and scheme in [ 'http', 'https', 'ftp', 'scp', 'sftp',
                                       'gopher', 'tftp' ]):
            scheme = scheme or '<schemeless>'
            raise ValueError(f"'{scheme}' URL not permitted")
        cm = importer.remote_repo(modules, base_url, zip_pwd)
        return generic_repo_context(cm)
    def github_repo(username=None, repo=None, module=None, branch=None,
                    commit=None):
        cm = importer.github_repo(username, repo, module, branch, commit)
        return generic_repo_context(cm)
    def gitlab_repo(username=None, repo=None, module=None, branch=None,
                    commit=None, domain='gitlab.com'):
        cm = importer.gitlab_repo(username, repo, module, branch, commit, domain)
        return generic_repo_context(cm)
    def bitbucket_repo(username=None, repo=None, module=None, branch=None,
                       commit=None):
        cm = importer.bitbucket_repo(username, repo, module, branch, commit)
        return generic_repo_context(cm)

    importer_proxy = Object()
    builtins = g['__builtins__']
    importer_proxy.remote_repo = makeapi("""
def fn(modules: [str], base_url: str, zip_pwd=None):
  return real(modules, base_url, zip_pwd)
""",                                     globals={ '__builtins__': builtins },
                                         real=remote_repo)._c
    importer_proxy.github_repo = makeapi("""
def fn(username=None, repo=None, module=None, branch=None, commit=None):
  return real(username, repo, module, branch, commit)
""",                                     globals={ '__builtins__': builtins },
                                         real=github_repo)._c
    importer_proxy.gitlab_repo = makeapi("""
def fn(username=None, repo=None, module=None, branch=None, commit=None,
       domain='gitlab.com'):
  return real(username, repo, module, branch, commit, domain)
""",                                     globals={ '__builtins__': builtins },
                                         real=gitlab_repo)._c
    importer_proxy.bitbucket_repo = makeapi("""
def fn(username=None, repo=None, module=None, branch=None, commit=None):
  return real(username, repo, module, branch, commit)
""",                                     globals={ '__builtins__': builtins },
                                         real=bitbucket_repo)._c
    del builtins
    g['__builtins__']['importer'] = importer_proxy.lockdown(makeapi)
    del importer_proxy
    g['__builtins__']['__import__'] = makeapi("""
def fn(names, __loader__, module=None, level=0):
  return imp(names, __loader__, glbs, module, level)
""",                                          imp=Rimport, glbs=g)._c

    # new '__builtins__' is now final - regenerate 'makeapi'
    g['__builtins__'].lock()
    g['__builtins__'] = g['__builtins__'].as_dict(makeapi)
    g['makeapi'] = makeapi("""
def def_invoke(fn: str, globals=glbs, __fname__='fn', **kwargs):
  '''
  Wraps a function as an API by divorcing it from the global scope.  Its
  closure is secured by denying access to __closure__.

  Usage
  Write a thin wrapper to the function in the (multiline) string fn.
  The name of the wrapper is __fname__.  The globals' content is
  accessible to the API's clients.  Usually what the framework already
  provides to all client scopes can be included.  But it is recommended
  to reduce exposure as much as possible and the wrapper should also be
  minimal.  So it is empty in most situations, except for an occasional
  type symbol or two that is already available to all clients.  The
  expression of the function's invocation has the function itself and
  bound variables, which constitute the closure.  It is given as keyword
  arguments (kwargs).  The framework denies clients' access to the closure.

  In the following example, Interpret (the API's function) and debugging
  are the closure.  The default __fname__ (fn) and empty globals are taken.

  Ex.: makeapi(""" + '"""' + '''
def fn(input, optim=2):
  if debug():
    return f(input, 0)
  return f(input, optim)
""",''' + """           f=Interpret, debug=debugging)
  '''
  return real(fn, globals, __fname__, **kwargs)
""",                       globals={ '__builtins__': g['__builtins__'] },
                           glbs={ '__builtins__': g['__builtins__'] },
                           __fname__='def_invoke', real=API_FnBind)._c

    # things in "globals()" that require the full "__builtins__" as an example
    g['hidebases'] = g['makeapi']('''def fn(to_hide: tuple, *bases):
  """
  Creates a class where some base class(es) will be hidden from access
  --
  Care must be taken when writing constructors, and various methods for classes
  derived using this utility, as super(T, o) will skip the hidden base class(es).
  """
  return h(to_hide, *bases)''',   h=HideBases)._c
    # also published "class Freeze_meta" - returned by "hidebases(()).__base__"

    importer = Importer(g.copy(), cauterize)

class RNodeTransformer(ast.NodeTransformer):
    def __init__(self, eclass1: BaseException, eclass2: BaseException,
                 *argv, **kwargs):
        super().__init__(*argv, **kwargs)
        self.aexc_class = eclass1
        self.sexc_class = eclass2
        self.writing_nodes = []
        self.first_arg = None

    def visit_FunctionDef(self ,node):
        self.first_arg = None
        if len(node.args.args) > 0:
            self.first_arg = node.args.args[0].arg
        self.generic_visit(node)
        self.first_arg = None
        return node

    def visit_Attribute(self, node):
        if node in self.writing_nodes:
            self.generic_visit(node)
            return node

        if node.attr in [ '__code__', 'gi_code', 'f_code', 'ag_code',
                          '__class__' ]:
            raise self.aexc_class(f"forbidden keyword: '{node.attr}'")

        if type(node.ctx) == ast.Load:
            if node.attr in [ '__getattribute__', '__setattr__', '__delattr__',
                              'gi_frame', 'ag_frame',
                              '__closure__', '__globals__', '__subclasses__' ]:
                raise self.aexc_class(f"forbidden keyword: '{node.attr}'")

        self.generic_visit(node)
        return node

    def visit_Call(self, node):
        def is_super(node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'super':
                    return True
            return False

        if is_super(node) and len(node.args) == 0:
            # fill in "super()" -> "super(__class__, self)"
            self.generic_visit(node)
            thisname = self.first_arg if self.first_arg else 'self'
            node.args = [ ast.Name(id='__class__', ctx=ast.Load()),
                          ast.Name(id=thisname, ctx=ast.Load()) ]
            ast.fix_missing_locations(node)
            return node

        if isinstance(node.func, ast.Attribute):
            if node.func.attr == '__setattr__':
                # rewrite "???.__setattr__(...)"
                self.writing_nodes.append(node.func)
                self.generic_visit(node)
                self.writing_nodes.remove(node.func)

                if is_super(node.func.value):
                    return node         # except if "super(...).__setattr__("

                newcall = ast.Name(id='setattr', ctx=ast.Load())
                if len(node.args) > 2:  # unbound '__setattr__' - can't do that!
                    newcall = ast.copy_location(
                                 ast.Call(func=newcall, args=node.args,
                                 keywords=[]),
                                 node)
                    ast.fix_missing_locations(newcall)
                    return newcall
                newcall = ast.copy_location(
                            ast.Call(func=newcall,
                                     args=[ node.func.value ] + node.args,
                                     keywords=[]),
                            node)
                ast.fix_missing_locations(newcall)
                return newcall
            elif node.func.attr == '__getattribute__' and len(node.args) > 0:
                # rewrite "???.__getattribute__(...)"
                obj = node.func.value
                parm = node.args[0]
                if len(node.args) > 1:	# unbound '__getattribute__'
                    obj = node.args[0]
                    parm = node.args[1]
                self.writing_nodes.append(node.func)
                self.generic_visit(node)
                self.writing_nodes.remove(node.func)

                if is_super(node.func.value):
                    return node         # except if "super(...).__getattribu"

                newcall = ast.copy_location(
                            ast.Call(func=ast.Name(id='getattr',
                                                   ctx=ast.Load()),
                                     args=[ obj, parm ],
                                     keywords=[ ast.keyword(arg='binder',
                                                  value=node.func.value) ]),
                            node)
                ast.fix_missing_locations(newcall)
                return newcall
            elif node.func.attr == '__delattr__' and len(node.args) > 0:
                # rewrite "???.__delattr(...)"
                obj = node.func.value
                parm = node.args[0]
                if len(node.args) > 1:  # unbound '__delattr__'
                    obj = node.args[0]
                    parm = node.args[1]
                self.writing_nodes.append(node.func)
                self.generic_visit(node)
                self.writing_nodes.remove(node.func)

                if is_super(node.func.value):
                    return node         # except if "super(...).__delattr__("

                newcall = ast.copy_location(
                            ast.Call(func=ast.Name(id='delattr',
                                                   ctx=ast.Load()),
                                     args=[ obj, parm ], keywords=[]),
                            node)
                ast.fix_missing_locations(newcall)
                return newcall
            elif node.func.attr == 'format':
                # rewrite "???.format(...)"
                newcall = ast.copy_location(
                            ast.Call(func=ast.Name(id='safe_format',
                                                   ctx=ast.Load()),
                                     args=[ node.func.value ] + node.args,
                                     keywords=node.keywords),
                            node)
                ast.fix_missing_locations(newcall)
                return newcall
            elif node.func.attr == 'format_map':
                # rewrite "???.format_map(...)"
                newcall = ast.copy_location(
                            ast.Call(func=ast.Name(id='safe_format_map',
                                                   ctx=ast.Load()),
                                     args=[ node.func.value ] + node.args,
                                     keywords=[]),
                            node)
                ast.fix_missing_locations(newcall)
                return newcall
        self.generic_visit(node)
        return node

    @staticmethod
    def _imports_to_aliases(names):
        array = []
        for alias in names:
            item = ast.Dict(keys=[ ast.Constant(value='name'),
                                   ast.Constant(value='asname') ],
                            values=[ ast.Constant(value=alias.name),
                                     ast.Constant(value=alias.asname or\
                                                  alias.name.split('.')[-1]) ]
                           )
            array.append(item)
        return ast.List(elts=array, ctx=ast.Load())
    def visit_Import(self, node):
        self.generic_visit(node)
        new_call = ast.Call(func=ast.Name(id='__import__', ctx=ast.Load()),
                            args=[ __class__._imports_to_aliases(node.names),
                                   ast.Name(id='__loader__', ctx=ast.Load()) ],
                            keywords=[])
        new_call = ast.copy_location(new_call, node)
        ast.fix_missing_locations(new_call)
        return ast.copy_location(ast.Expr(value=new_call), node)
                          
    def visit_ImportFrom(self, node):
        self.generic_visit(node)
        new_call = ast.Call(func=ast.Name(id='__import__', ctx=ast.Load()),
                            args=[ __class__._imports_to_aliases(node.names),
                                   ast.Name(id='__loader__', ctx=ast.Load()),
                                   ast.Constant(value=node.module),
                                   ast.Constant(value=node.level) ],
                            keywords=[])
        new_call = ast.copy_location(new_call, node)
        ast.fix_missing_locations(new_call)
        return ast.copy_location(ast.Expr(value=new_call), node)

    def visit_Global(self, node):
        raise self.sexc_class("forbidden keyword: 'global'")

def API_FnBind(fn: str, globals={ '__builtins__':{} }, __fname__='fn',
               **kwargs):
    """
    Wraps a function as an API by divorcing it from the global scope.  Its
    closure is secured by denying access to '__closure__'.  This design permits,
    in limited cases, access to '__globals__'.
    """
    code = f"""def _({','.join(kwargs.keys())}):
""" +      textwrap.indent(fn, '  ') + f'\n  return {__fname__}'
    output = {}
    exec(code, Globals.check(globals), output)
    rtn = output['_'](*tuple(kwargs.values()))
    rtn._c = LockedFn(rtn)
    return rtn

# temporary 'makeapi' for convenience only - security hole
makeapi = API_FnBind("""
def def_invoke(fn: str, globals={ '__builtins__':{} }, __fname__='fn',
               **kwargs):
  return real(fn, globals, __fname__, **kwargs)
  """,               globals={ '__builtins__': gBuiltIns.copy() },
                     __fname__='def_invoke',
                     real=API_FnBind)


import Rwasmtime_git.wasmtime as Rwasmtime
from ISPy_importer import Importer

RException.lock()
class RValueError(RException):
    def __init__(self, *argv, **kwargs):
        super().__init__(*argv, **kwargs)
RValueError.lock()

class RImportError(RException):
    def __init__(self, name='', path=''):
        super().__init__()
        self.name = name
        self.path = path
RImportError.lock()
class RModuleNotFoundError(RImportError):
    def __init__(self, name='', path=''):
        super().__init__()
RModuleNotFoundError.lock()

# standard libraries
# filter out some "types" packages
Rtypes = Object()
for name in types.__all__:
    try:
        if issubclass(vars(types)[name], Exception):
            continue
    except TypeError:
        pass
    if not name in [ 'CodeType', 'prepare_class' ]:
        orig = vars(types)[name]
        if isinstance(orig, types.FunctionType):
            Rtypes.__setattr__(name, LockedFn(orig))
        else:
            Rtypes.__setattr__(name, orig)
        del orig
def Rprepare_class(name, bases=(), kwds=None):
    meta, ns, kwds = types.prepare_class(name, bases, kwds)
    return meta.__name__, ns, kwds
Rtypes.prepare_class = makeapi("""
def fn(name, bases=(), kwds=None):
  return real(name, bases, kwds)
""",                           real=Rprepare_class)._c
del Rprepare_class
Rtypes.__doc__ = "Access to Python's built-in 'types' module"
Rtypes = Rtypes.lockdown(makeapi)
Rmath = Object()
for name in vars(math):
    try:
        if issubclass(vars(math)[name], Exception):
            continue
    except TypeError:
        pass
    if not name.startswith('_'):
        orig = vars(math)[name]
        if isinstance(orig, types.FunctionType):
            Rmath.__setattr__(name, LockedFn(orig))
        else:
            Rmath.__setattr__(name, orig)
        del orig
Rmath.__doc__ = "Access to Python's built-in 'math' module"
Rmath.lockdown(makeapi)
Rrandom = Object()
for name in random.__all__:
    try:
        if issubclass(vars(random)[name], Exception):
            continue
    except TypeError:
        pass
    if not name in [ 'seed' ]:
        orig = vars(random)[name]
        if isinstance(orig, types.FunctionType):
            Rrandom.__setattr__(name, LockedFn(orig))
        else:
            Rrandom.__setattr__(name, orig)
        del orig
Rrandom.__doc__ = "Access to Python's built-in 'random' module"
Rrandom.lockdown(makeapi)
Rdatetime = Object()
for name in vars(datetime):
    try:
        if issubclass(vars(datetime)[name], Exception):
            continue
    except TypeError:
        pass
    if not name.startswith('_') and not name in [ 'sys', 'datetime_CAPI' ]:
        orig = vars(datetime)[name]
        if isinstance(orig, types.FunctionType):
            Rdatetime.__setattr__(name, LockedFn(orig))
        else:
            Rdatetime.__setattr__(name, orig)
        del orig
Rdatetime.__doc__ = "Access to Python's built-in 'datetime' module"
Rdatetime.lockdown(makeapi)
Rre = Object()
for name in re.__all__:
    try:
        if issubclass(vars(re)[name], Exception):
            continue
    except TypeError:
        pass
    orig = vars(re)[name]
    if isinstance(orig, types.FunctionType):
        Rre.__setattr__(name, LockedFn(orig))
    else:
        Rre.__setattr__(name, orig)
    del orig
Rre.__doc__ = "Access to Python's built-in 're' module"
Rre.lockdown(makeapi)
Rjson = Object()
for name in json.__all__:
    try:
        if issubclass(vars(json)[name], Exception):
            continue
    except TypeError:
        pass
    if not name in [ 'JSONEncoder', 'JSONDecoder' ]:
        orig = vars(json)[name]
        if isinstance(orig, types.FunctionType):
            Rjson.__setattr__(name, LockedFn(orig))
        else:
            Rjson.__setattr__(name, orig)
        del orig
Rjson.__doc__ = "Access to Python's built-in 'json' module"
class RJSONDecodeError(RValueError):
    def __init__(self, orig: json.JSONDecodeError):
        super().__init__()
        self.msg = orig.msg
        self.doc = orig.doc
        self.pos = orig.pos
        self.lineno = orig.lineno
        self.colno = orig.colno

    @staticmethod
    def create(orig: json.JSONDecodeError):
        return RJSONDecodeError(orig).with_traceback(orig.__traceback__)
RJSONDecodeError.lock()

class RJSONDecoder_impl(json.JSONDecoder):
    def __init__(self, *argv, **kwargs):
        super().__init__(*argv, **kwargs)

    def decode(self, s):
        try:
            return super().decode(s)
        except json.JSONDecodeError as exc:
            raise RJSONDecodeError.create(exc)


Rjson.JSONDecodeError = RJSONDecodeError
doc = textwrap.dedent('    ' + json.JSONDecoder.__doc__) +\
      textwrap.dedent('        ' + json.JSONDecoder.__init__.__doc__)
Rjson.JSONDecoder = makeapi("""
def fn(*argv, object_hook=None, parse_float=None, parse_int=None,
       parse_constant=None, strict=True, object_pairs_hook=None):
  '''
""" + restring(doc) + """
This wrapped API is only the parameterized constructor as documented
above, that returns a decoder.  The underlying Python class and its 
methods cannot be used by a derived class as they do not observe the
encapsulation boundaries.
  '''
  return ctr(*argv, object_hook=object_hook, parse_float=parse_float,
             parse_int=parse_int, parse_constant=parse_constant,
             strict=strict, object_pairs_hook=object_pairs_hook)
""",                        ctr=RJSONDecoder_impl)._c
del doc

class RJSONEncoder(json.JSONEncoder,
                   metaclass=HideBases((json.JSONEncoder,)).metalock()):
    def __init__(self, *argv, skipkeys=False, ensure_ascii=True,
                 check_circular=True, allow_nan=True, sort_keys=False,
                 indent=None, separators=None, default=None):
        super().__init__(*argv, skipkeys=skipkeys, ensure_ascii=ensure_ascii,
                         check_circular=check_circular, allow_nan=allow_nan,
                         sort_keys=sort_keys, indent=indent,
                         separators=separators, default=default)
    __init__.__doc__ = json.JSONEncoder.__init__.__doc__

RJSONEncoder.__doc__ = json.JSONEncoder.__doc__
RJSONEncoder.lock()
Rjson.JSONEncoder = RJSONEncoder
Rjson.lockdown(makeapi)
json._default_decoder = RJSONDecoder_impl()

import Rjwt
Rjwt.patch(RException, makeapi)
Rjwt_exp = Object()
for name in Rjwt.__all__:
    orig = vars(Rjwt)[name]
    if isinstance(orig, types.FunctionType):
        Rjwt_exp.__setattr__(name, LockedFn(orig))
    elif isinstance(orig, type):
        orig.lock()
        Rjwt_exp.__setattr__(name, orig)
    del orig
Rjwt_exp.exceptions = Object()
Rjwt_exp.exceptions.__proxydict__.update(Rjwt.exceptions.__dict__)
Rjwt_exp.lockdown(makeapi)

Rwasmtime_exp = Object()
for name in Rwasmtime.__all__:
    orig = vars(Rwasmtime)[name]
    if isinstance(orig, types.FunctionType):
        Rwasmtime_exp.__setattr__(name, LockedFn(orig))
    else:
        Rwasmtime_exp.__setattr__(name, orig)
    del orig
Rwasmtime_exp.lockdown(makeapi)
del name

def Rtype(obj_or_name, *argv, **kwargs):
    if isinstance(obj_or_name, type) and\
       getattr(obj_or_name, '__class__', None) == obj_or_name:
        raise RuntimeError(f"access to {type} blocked!")
    result = type(obj_or_name, *argv, **kwargs)
    if result in [ type, types.CodeType ]:
        raise RuntimeError(f"access to {result} blocked!")
    return result

# loophole - some attributes/properties leak higher scopes
def Rgetattr(builtins, obj, attr, *argv, binder=None):
    if binder == None:
        result = getattr(obj, attr, *argv)
    elif isinstance(binder.__getattribute__, types.MethodType) or\
         isinstance(binder.__getattribute__, types.MethodWrapperType):
        result = binder.__getattribute__(attr)
    else:
        result = binder.__getattribute__(obj, attr)

    def bind(func):
        if binder == None or\
           not isinstance(binder.__getattribute__, types.MethodType):
            return func
        # bind to obj
        return types.MethodType(func, obj)
    if attr == '__subclasses__':
        return makeapi("fn = lambda : []")
    if attr == '__getattribute__':
        return bind(builtins['getattr'])
    if attr == '__setattr__':
        return bind(builtins['setattr'])
    if attr == '__delattr__':
        return bind(builtins['delattr'])

    if attr == 'format' and\
       (str.format == obj.format or str.format.__get__(obj) == obj.format):
        return bind(builtins['safe_format'])
    if attr == 'format_map' and\
       (str.format_map == obj.format_map or\
        str.format_map.__get__(obj) == obj.format_map):
        return bind(builtins['safe_format_map'])

    if result == type:
        raise RuntimeError(f"access to {type} blocked!")
    if result == globals():
        raise RuntimeError("access to '__main__.globals()' blocked!")
    if isinstance(result, types.CodeType):
        raise RuntimeError(f"access to {types.CodeType} blocked!")
    if isinstance(result, types.CellType):
        raise RuntimeError("access to 'cell' type blocked!")
    if isinstance(result, types.FrameType):
        raise RuntimeError(f"access to {types.FrameType} blocked!")
    if (isinstance(result, list) or isinstance(result, tuple)) and\
       len(result) > 0:
        if isinstance(result[0], types.CellType):
            raise RuntimeError("access to 'cell' type blocked!")

    return result

# forbid changing '__code__'
def Rsetattr(obj, attr, val):
    if type(val) == types.CodeType:
        raise RuntimeError(f"access to {types.CodeType} blocked!")
    return setattr(obj, attr, val)

def Rexec(code: str, m='exec', gl={ '__builtins__': {} }, loc=None):
    if type(code) != str:
        raise TypeError(m + "(): 'code' must be of type 'str'")
    gl = Globals.check(gl).lock()
    tree = RNodeTransformer(AttributeError,
                            SyntaxError).visit(ast.parse(code, mode=m))
    if m == 'exec':
        return exec(compile(tree, filename='<unknown>', mode=m), gl, loc)
    elif m == 'eval':
        return eval(compile(tree, filename='<unknown>', mode=m), gl, loc)
    raise RuntimeError(m + "(): mode must be 'exec' or 'eval'")

def Rsuper(builtins, T, *obj_or_type):
    if len(obj_or_type) == 0:
        raise RuntimeError("super(): single argument form not supported")
    
    oclass = term = obj_or_type[0]
    if not isinstance(oclass, type):
        oclass = oclass.__class__
    if isinstance(type(oclass), ReadOnly2_meta) and\
       hasattr(oclass, '__Rsupermap__') and T in oclass.__Rsupermap__:
        res = oclass.__Rsupermap__[T](term)
    else:
        res = super(T, *obj_or_type)

    class proxy(metaclass=Freeze_meta):
        def __getattribute__(self, attr):
            # our AST parser add-in made sure this will just be a call
            if attr == '__getattribute__':
                # "super(...).__getattribute__(...)"
                if isinstance(term, type):
                    def binder_getattr(anchor, key):
                        return builtins['getattr'](anchor, key, binder=res)
                    return binder_getattr
                # calling "__getattribute__" on a super() interface for term?
                #   - this super() is ignored
                def binder_getattr(key):
                    return builtins['getattr'](term, key)
                return binder_getattr

            ret = getattr(res, attr)
            if issubclass(oclass, Object) or issubclass(oclass, Dict):
                m= { '__setattr__': (builtins['setattr'], term.__setattr__),
                     '__delattr__': (builtins['delattr'], term.__delattr__), }
                # our AST parser add-in made sure these will just be calls
                if attr in m:
                    if term.__locked__:
                        return m[attr][0 if isinstance(term, type) else 1]
                    if isinstance(term, type):
                        return makeapi("""def fn(t, *argv):
  if not isinstance(t, oc):
      raise TypeError(f"term/object must be an instance of {oc.__name__}")
  if t.__locked__:
      return t.""" + attr + """(*argv)
  return r(t, *argv)""",               globals={ '__builtins__': builtins },
                                       oc=oclass, r=ret)
            else:                       # translate as "RNodeTransformer" does
                m= { '__setattr__': builtins['setattr'],
                     '__delattr__': builtins['delattr'], }
                if attr in m:
                    if isinstance(term, type):
                        return m[attr]
                    return types.MethodType(m[attr], term)

            return ret
        def __setattr__(self, attr, val):
            raise AttributeError(f"'super' object has no attribute '{attr}'")
    proxy.lock()

    return proxy()


def SafeFormatter(builtins):
    class formatter(string.Formatter):
        """
        credits to Armin Ronacher
        (https://lucumr.pocoo.org/2016/12/29/careful-with-str-format/)
        """
        def __init__(self):
            super().__init__()

        def get_field(self, field_name, args, kwargs):
            first, rest = _string.formatter_field_name_split(field_name)
            obj = self.get_value(first, args, kwargs)
            for is_attr, i in rest:
                if is_attr:
                    obj = Rgetattr(builtins, obj, i)
                else:
                    obj = obj[i]
            return obj, first

    return formatter()

def Rsafe_format(builtins, invoker, *argv, **kwargs):
    if str.format == invoker.format:
        invoker = argv[0]
        argv = argv[1:]
    elif str.format.__get__(invoker) != invoker.format:
        return invoker.format(*argv, **kwargs)
    return SafeFormatter(builtins).vformat(invoker, argv, kwargs)

def Rsafe_format_map(builtins, invoker, map, *extra):
    if str.format_map == invoker.format_map:
        invoker = map
        map = extra[0]
    elif str.format_map.__get__(invoker) != invoker.format_map:
        return invoker.format_map(map)
    return SafeFormatter(builtins).vformat(invoker, (), map)

def Rimport(aliases, __loader, __glbs, fr=None, level: int=0):
    lcls = __glbs['__mod']
    pathcomp = __glbs['__name__'].split('.')
    # input sanitization
    if not aliases:
        raise SyntaxError("'import' what?")
    try:
        for i in aliases:
            if 'name' not in i:
                raise SyntaxError("'import' - 'aliases' must be a list of " +
                                  "'{'name':<n>, 'asname':<a>}'")
            elif i['name'] == '*':
                break;
        if i['name'] == '*':
            if not fr:
                raise SyntaxError("'import *' from what?")
            aliases = [ {'name': '*'} ]
    except TypeError:
        if isinstance(aliases, str):
            aliases = [ { 'name': aliases } ]
        else:
            raise SyntaxError("'import' - 'aliases' must be a list of " +
                              "'{'name':<n>, 'asname':<a>}'")
    if level > 0:			# relative path must use current
        ___loader = __glbs['__loader__']# '__loader__'
    if not fr and level == len(pathcomp):
        level = 0                       # legacy "from .. import ???"
        fr = None
        del pathcomp
    if level > 0 or fr:
        # find ancestral root
        if len(pathcomp) <= level:
            raise ValueError(f'path retraction beyond base (level = {level})')
        pathcomp = pathcomp[:(-level)]
        if fr:
            pathcomp.append(fr)
        fr = '.'.join(pathcomp)
        del pathcomp
        importer = __loader(fr)
        if not importer:
            raise ValueError("Importer not found for '" + fr.split('.')[0] +
                             "'.  Is '__loader__' set properly?")
        mod = importer(fr)
        if not mod:
            raise RModuleNotFoundError(fr)
        if aliases[0]['name'] == '*':	# rebuild aliases[]
            if hasattr(mod, '__all__'):
                aliases = [ {'name':n} for n in mod.__all__ ]
            else:
                aliases = [ {'name':n} for n in dir(mod)
                            if not n.startswith('_') ]
        for i in aliases:
            if not 'asname' in i:
                i['asname'] = i['name'].split('.')[-1]
            parse = ast.parse(i['asname'])
            if not parse.body or not isinstance(parse.body[0], ast.Expr) or\
               not isinstance(parse.body[0].value, ast.Name) or\
               parse.body[0].value.id != i['asname']:
                raise ValueError("'" + i['asname'] + "' is not a valid name")
            for component in i['name'].split('.'):
                parse = ast.parse(component)
                if not parse.body or not isinstance(parse.body[0], ast.Expr) or\
                   not isinstance(parse.body[0].value, ast.Name):
                    raise ValueError(name=i['name'])
            if hasattr(lcls, i['asname']):
                raise RuntimeError("'" + i['asname'] + "' is already assigned")
            try:
                setattr(lcls, i['asname'], eval('lambda o: o.' + i['name'])(mod))
            except AttributeError:
                raise RImportError(name=i['name'])
    else:
        for i in aliases:
            if not 'asname' in i:
                i['asname'] = i['name'].split('.')[-1]
            parse = ast.parse(i['asname'])
            if not parse.body or not isinstance(parse.body[0], ast.Expr) or\
               not isinstance(parse.body[0].value, ast.Name) or\
               parse.body[0].value.id != i['asname']:
                raise ValueError("'" + i['asname'] + "' is not a valid name")
            if hasattr(lcls, i['asname']):
                raise RuntimeError("'" + i['asname'] + "' is already assigned")
            importer = __loader(i['name'].split('.')[0])
            if not importer:
                raise ValueError("Importer not found for '" + 
                                 i['name'].split('.')[0] +
                                 "'.  Is '__loader__' set properly?")
            mod = importer(i['name'])
            if not mod:
                raise RModuleNotFoundError(name=i['name'])
            setattr(lcls, i['asname'], mod)
    return None

Interact = None
def hackme(**kwargs):
    global Interact
    Interact = IPythonShellInteract
    return Interact(**kwargs.copy())

gBuiltIns['Object'] = Object
gBuiltIns['Dict'] = Dict


class getset:
    def __init__(self):
        self.priv = 123
    def getter(self):
        return self.priv
    def setter(self, val):
        self.priv = val
    def interface_factory(self):
        obj = Object()
        obj.access = makeapi('fn = lambda: f()', f=self.getter)._c
        obj.incr = makeapi('fn = lambda: (s(g() + 1), g())[1]',
                           s=self.setter, g=self.getter)._c
        obj.decr = makeapi('fn = lambda: (s(g() - 1), g())[1]',
                           s=self.setter, g=self.getter)._c
        #obj.lockdown(makeapi)
        return obj

obj = getset()
print(
"""You are launched into an IPython (sub-)shell, executed in a 'jailed'
scope/environment.  Your challenge is to find any loophole that
lets you""", '"break out".', """

You have been passed one parameter, an object (obj) that encapsulates
a single (private) integer variable.  It has methods to read, increment
and decrement the integer.  One way to demonstrate a loophole is by
showing that you can change obj's private variable into a Python 'str'
(string).
""")
hackme(_NESTLVL=1, obj = obj.interface_factory())
print("In the end, 'obj' has the value:")
print(f'{obj.priv}: {type(obj.priv)}')

