# An example of how to interact with wasm memory.
#
# Here a small wasm module is used to show how memory is initialized, how to
# read and write memory through the `Memory` object, and how wasm functions
# can trap when dealing with out-of-bounds addresses.

# Create our `Store` context and then compile a module and create an
# instance from the compiled module all in one go.
store = wasmtime.Store()
module = wasmtime.Module(store.engine, '''(module
  (memory (export "memory") 2 3)

  (func (export "size") (result i32) (memory.size))
  (func (export "load") (param i32) (result i32)
    (i32.load8_s (local.get 0))
  )
  (func (export "store") (param i32 i32)
    (i32.store8 (local.get 0) (local.get 1))
  )

  (data (i32.const 0x1000) "\\01\\02\\03\\04")
)''')

instance = wasmtime.Instance(store, module, [])

# Load up our exports from the instance
exports = instance.exports(store)
memory = exports["memory"]
size_fn = exports["size"]
load_fn = exports["load"]
store_fn = exports["store"]

print("Checking memory...")
assert(memory.size(store) == 2)
assert(memory.data_len(store) == 0x20000)

# Note that usage of `data_ptr` is unsafe! This is a raw C pointer which is not
# bounds checked at all. We checked our `data_len` above but you'll want to be
# very careful when accessing data through `data_ptr()`
assert(memory.data_ptr(store)[0] == 0)
assert(memory.data_ptr(store)[0x1000] == 1)
assert(memory.data_ptr(store)[0x1003] == 4)

assert(size_fn(store) == 2)
assert(load_fn(store, 0) == 0)
assert(load_fn(store, 0x1000) == 1)
assert(load_fn(store, 0x1003) == 4)
assert(load_fn(store, 0x1ffff) == 0)


def assert_traps(func):
    try:
        func()
        assert(False)
    except wasmtime.Trap:
        pass
    except wasmtime.WasmtimeError:
        pass

__mod.local = {}
__mod.local['load_fn'] = load_fn
__mod.local['store_fn'] = store_fn
__mod.local['store'] = store
__mod.local['memory'] = memory

# out of bounds trap
assert_traps(lambda: __mod.local['load_fn'](__mod.local['store'], 0x20000))

print("Mutating memory...")
memory.data_ptr(store)[0x1003] = 5
store_fn(store, 0x1002, 6)
# out of bounds trap
assert_traps(lambda: __mod.local['store_fn'](__mod.local['store'], 0x20000, 0))

assert(memory.data_ptr(store)[0x1002] == 6)
assert(memory.data_ptr(store)[0x1003] == 5)
assert(load_fn(store, 0x1002) == 6)
assert(load_fn(store, 0x1003) == 5)

# Grow memory.
print("Growing memory...")
assert(memory.grow(store, 1))
assert(memory.size(store) == 3)
assert(memory.data_len(store) == 0x30000)

assert(load_fn(store, 0x20000) == 0)
store_fn(store, 0x20000, 0)
assert_traps(lambda: __mod.local['load_fn'](__mod.local['store'], 0x30000))
assert_traps(lambda: __mod.local['store_fn'](__mod.local['store'], 0x30000, 0))

# Memory can fail to grow
assert_traps(lambda: __mod.local['memory'].grow(__mod.local['store'], 1))
assert(memory.grow(store, 0))

print("Creating stand-alone memory...")
memorytype = wasmtime.MemoryType(wasmtime.Limits(5, 5))
memory2 = wasmtime.Memory(store, memorytype)
__mod.local['memory2'] = memory2
assert(memory2.size(store) == 5)
assert_traps(lambda: __mod.local['memory2'].grow(__mod.local['store'], 1))
assert(memory2.grow(store, 0))

