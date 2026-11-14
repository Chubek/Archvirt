import pathlib
import struct
import subprocess
import sys
import tempfile

binary, source, build = sys.argv[1:]
def run(*args):
    return subprocess.run([binary, "--headless", *args], input="exit\n", text=True,
                          capture_output=True, timeout=20)

assert run("--list-machines").returncode == 0
for name in ("x86_64", "aarch64"):
    profile = pathlib.Path(build) / "src/generated/machines" / f"{name}.aml"
    result = run("--machine", name, "--archml", str(profile), "-V", "--max-instructions", "3000000")
    assert result.returncode == 0, result.stdout + result.stderr
for machine in ("riscv64", "nvptx", "wasm", "spirv"):
    result = run("--machine", machine)
    assert result.returncode != 0 and "Unsupported machine" in result.stderr
for memory in ("0", "39", "1025", "-1", "bogus"):
    assert run("--memory", memory).returncode != 0
assert run("--machine", "aarch64", "--backend", "kvm").returncode != 0
assert run("--archml", str(pathlib.Path(source) / "third_party/libstone/sandstone/archml/stdspec/amd64.aml")).returncode != 0
assert run("--machine", "aarch64", "--os", str(pathlib.Path(build) / "domix/x86_64/domix.img")).returncode != 0
with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "bad.img"
    image = bytearray((pathlib.Path(build) / "domios/domios.img").read_bytes())
    image[-1] ^= 1
    path.write_bytes(image)
    result = run("--bios", str(path))
    assert result.returncode != 0 and "checksum" in result.stderr
    image = bytearray((pathlib.Path(build) / "domix/x86_64/domix.img").read_bytes())
    struct.pack_into("<Q", image, 16, 2**64 - 1)
    path.write_bytes(image)
    assert run("--os", str(path)).returncode != 0
    # Unsupported guest instructions must produce an error, not successful halt.
    image = bytearray((pathlib.Path(build) / "domix/x86_64/kernel").read_bytes())
    phoff = struct.unpack_from("<Q", image, 32)[0]
    textoff = struct.unpack_from("<Q", image, phoff + 8)[0]
    image[textoff:textoff + 2] = b"\x0f\x0b"  # UD2
    path.write_bytes(image)
    result = run("-V", "-k", str(path))
    assert result.returncode != 0 and "Unsupported guest instruction" in result.stderr, result.stderr
print("Machine selection, image validation and unsupported-instruction diagnostics passed")
