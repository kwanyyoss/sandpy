# Example of instantiating two modules which link to each other.

engine = wasmtime.Engine()

# Load and compile our two modules
linking1 = wasmtime.Module(engine, '''(module
  (import "linking2" "double" (func $double (param i32) (result i32)))
  (import "linking2" "log" (func $log (param i32 i32)))
  (import "linking2" "memory" (memory 1))
  (import "linking2" "memory_offset" (global $offset i32))

  (func (export "run")
    ;; Call into the other module to double our number, and we could print it
    ;; here but for now we just drop it
    i32.const 2
    call $double
    drop

    ;; Our `data` segment initialized our imported memory, so let's print the
    ;; string there now.
    global.get $offset
    i32.const 14
    call $log
  )

  (data (global.get $offset) "Hello, world!\\n")
)''')
linking2 = wasmtime.Module(engine, '''(module
  (type $fd_write_ty (func (param i32 i32 i32 i32) (result i32)))
  (import "wasi_snapshot_preview1" "fd_write" (func $fd_write (type $fd_write_ty)))

  (func (export "double") (param i32) (result i32)
    local.get 0
    i32.const 2
    i32.mul
  )

  (func (export "log") (param i32 i32)
    ;; store the pointer in the first iovec field
    i32.const 4
    local.get 0
    i32.store

    ;; store the length in the first iovec field
    i32.const 4
    local.get 1
    i32.store offset=4

    ;; call the `fd_write` import
    i32.const 1     ;; stdout fd
    i32.const 4     ;; iovs start
    i32.const 1     ;; number of iovs
    i32.const 0     ;; where to write nwritten bytes
    call $fd_write
    drop
  )

  (memory (export "memory") 2)
  (global (export "memory_offset") i32 (i32.const 65536))
)''')

# Set up our linker which is going to be linking modules together. We
# want our linker to have wasi available, so we set that up here as well.
linker = wasmtime.Linker(engine)
linker.define_wasi()

# Create a `Store` to hold instances, and configure wasi state
store = wasmtime.Store(engine)
wasi = wasmtime.WasiConfig()
wasi.inherit_stdout()
store.set_wasi(wasi)

# Instantiate our first module which only uses WASI, then register that
# instance with the linker since the next linking will use it.
linking2 = linker.instantiate(store, linking2)
linker.define_instance(store, "linking2", linking2)

# And with that we can perform the final link and the execute the module.
linking1 = linker.instantiate(store, linking1)
run = linking1.exports(store)["run"]
run(store)

