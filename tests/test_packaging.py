import os
import stat
import subprocess
from pathlib import Path


def write_executable(path: Path, contents: str):
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_gearbox_shim_works_through_symlink(tmp_path):
    app = tmp_path / "Gearbox.app" / "Contents"
    macos = app / "MacOS"
    resources = app / "Resources"
    venv_bin = resources / "venv" / "bin"
    python_dir = resources / "python"
    homebrew_bin = tmp_path / "bin"

    macos.mkdir(parents=True)
    venv_bin.mkdir(parents=True)
    python_dir.mkdir(parents=True)
    homebrew_bin.mkdir(parents=True)

    shim_source = Path(__file__).resolve().parents[1] / "scripts" / "gearbox-shim.sh"
    shim_target = macos / "gearbox"
    shim_target.write_text(shim_source.read_text())
    shim_target.chmod(shim_target.stat().st_mode | stat.S_IXUSR)

    args_file = tmp_path / "args.txt"
    write_executable(
        venv_bin / "python3",
        "#!/bin/bash\n"
        f"printf '%s\\n' \"$@\" > \"{args_file}\"\n",
    )
    (python_dir / "cli.py").write_text("print('ok')\n")

    shim_link = homebrew_bin / "gearbox"
    shim_link.symlink_to(shim_target)

    subprocess.run([str(shim_link), "--help"], check=True)

    argv = args_file.read_text().splitlines()
    assert argv[0] == str(python_dir / "cli.py")
    assert argv[1] == "--help"


def test_packaged_app_includes_swift_resource_bundle():
    package_swift = (Path(__file__).resolve().parents[1] / "GearboxUI" / "Package.swift").read_text()
    app_swift = (Path(__file__).resolve().parents[1] / "GearboxUI" / "Sources" / "GearboxUI" / "App.swift").read_text()

    assert 'resources: [.process("Resources")]' not in package_swift
    assert "Bundle.module" not in app_swift
    assert 'Bundle.main.url(forResource: "AppIcon", withExtension: "icns")' in app_swift
