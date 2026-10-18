# Local debugger dependency attribution

This original project has no new project-wide license. Extension source is
published for local builds; compiled WASM and adapters are not redistributed.
This is not an Extension Gallery release.

The WASM module incorporates the Zed extension API 0.7.0 (Apache-2.0):
https://github.com/zed-industries/zed/tree/main/crates/extension_api.
Its original license is retained in `licenses/ZED_API_LICENSE_APACHE`.
It also incorporates Rust standard/runtime and serialization dependencies;
versions/checksums are pinned in Cargo.lock. Original dependency licenses and
copyright notices remain in the local Cargo registry/toolchain installation.
Any future public binary release must package the complete applicable transitive
runtime license notices; the current local build is not a redistribution release.

Eclipse CDT GDB Adapter 1.10.0 is a separately installed EPL-2.0 dependency:
https://github.com/eclipse-cdt-cloud/cdt-gdb-adapter.
Its binaries, npm dependencies and licenses are not bundled in this extension.
Node, ARM GNU GDB, Python, Unicorn and toolchains are also external requirements.
