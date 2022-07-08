# Almost all operations in wasmtime require a contextual "store" argument to be
# shared amongst objects
store = wasmtime.Store()

# Here we can compile a `Module` which is then ready for instantiation
# afterwards
module = wasmtime.Module(store.engine, '''(module
  (func $hello (import "" "hello"))
  (func (export "run") (call $hello))
)''')

# Our module needs one import, so we'll create that here.


def say_hello():
    print("Hello from Python!")


hello = wasmtime.Func(store, wasmtime.FuncType([], []), say_hello)

# And with all that we can instantiate our module and call the export!
instance = wasmtime.Instance(store, module, [hello])
instance.exports(store)["run"](store)

