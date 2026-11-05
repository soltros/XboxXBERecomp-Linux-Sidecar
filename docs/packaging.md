# Linux title bundles

`xbe-sidecar bundle` turns a staged XboxXBERecomp Windows release into a Linux launcher archive. The Windows VM/build host is outside this packaging step: build the release there, place its release files in a Linux workspace, and register the player with `xbe-sidecar init`.

```sh
xbe-sidecar init /path/to/staged-release --name "Title" --exe Title.exe
xbe-sidecar doctor /path/to/staged-release
xbe-sidecar bundle /path/to/staged-release --output ~/Releases/title-linux.tar.gz
```

The bundle builder expects the player executable and `compiler/` in the configured working directory. The compiler directory must contain Windows `clang.exe` and `lld-link.exe`, which XboxXBERecomp uses to compile guest code on the player's first launch. It packages that directory except `compiler/work`, includes the player and the Visual C++ runtime DLLs used by the release recipe, and copies available `README.md`, `THIRD_PARTY.txt`, and license notices.

It creates an empty `assets/` directory and does not copy game files, user settings, crash dumps, local prefixes, or logs. Recipients add their own legally acquired game files to `assets/` according to the title's instructions.

The archive includes the Linux Sidecar Python launcher and a `run.sh` entry point. It currently requires Python 3.11+, `umu-launcher` for Proton (recommended), or Wine installed on the host. Proton and the Steam Linux Runtime are downloaded/managed by UMU on first launch unless preconfigured. This archive is a portable title bundle, not yet a fully self-contained runtime blob; Wine/Proton, UMU, Python, host Vulkan drivers, and Linux system libraries are not inside it.

Prefixes and logs use XDG data/state directories, so the extracted bundle can live in a read-only location. The bundle's sanitized manifest intentionally omits host-specific runner executable paths, custom environment variables, and absolute Proton paths.
