# This is an example of working with mulit-value modules and dealing with
# multi-value functions.

# Configure our `Store`, but be sure to use a `Config` that enables the
# wasm multi-value feature since it's not stable yet.
print("Initializing...")
config = wasmtime.Config()
config.wasm_multi_value = True
store = wasmtime.Store(wasmtime.Engine(config))

print("Compiling module...")
module = wasmtime.Module(store.engine, '''(module
  (func $f (import "" "f") (param i32 i64) (result i64 i32))

  (func $g (export "g") (param i32 i64) (result i64 i32)
    (call $f (local.get 0) (local.get 1))
  )

  (func $round_trip_many
    (export "round_trip_many")
    (param i64 i64 i64 i64 i64 i64 i64 i64 i64 i64)
    (result i64 i64 i64 i64 i64 i64 i64 i64 i64 i64)

    local.get 0
    local.get 1
    local.get 2
    local.get 3
    local.get 4
    local.get 5
    local.get 6
    local.get 7
    local.get 8
    local.get 9)
)''')

print("Creating callback...")
callback_type = wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i64()],
                                  [wasmtime.ValType.i64(), wasmtime.ValType.i32()])


def callback(a, b):
    return [b + 1, a + 1]


callback_func = wasmtime.Func(store, callback_type, callback)

print("Instantiating module...")
instance = wasmtime.Instance(store, module, [callback_func])

print("Extracting export...")
g = instance.exports(store)["g"]

print("Calling export \"g\"...")
results = g(store, 1, 3)
print("> {} {}".format(results[0], results[1]))

assert(results[0] == 4)
assert(results[1] == 2)

print("Calling export \"round_trip_many\"...")
round_trip_many = instance.exports(store)["round_trip_many"]
results = round_trip_many(store, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)

print("Printing result...")
print(">")
for r in results:
    print("  %d" % r)
assert(len(results) == 10)
for i, r in enumerate(results):
    assert(i == r)

