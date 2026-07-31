import subprocess, sys, tempfile, os, json, shutil, venv

PY = sys.argv[1] if len(sys.argv) > 1 else sys.executable
WHEEL = sys.argv[2] if len(sys.argv) > 2 else "dist/capt_solo-0.5.0-py3-none-any.whl"
SDIST = sys.argv[3] if len(sys.argv) > 3 else "dist/capt_solo-0.5.0.tar.gz"
LABEL = sys.argv[4] if len(sys.argv) > 4 else "local"

def run(cmd, cwd=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)

res = {"label": LABEL, "python": run(f"{PY} --version").stdout.strip() or run(f"{PY} --version").stderr.strip(), "checks": {}}

# fresh venv outside repo
base = tempfile.mkdtemp(prefix="captinst_")
venv_dir = os.path.join(base, "venv")
run(f"{PY} -m venv {venv_dir}")
pip = f"{venv_dir}/bin/pip"
py = f"{venv_dir}/bin/python"

# wheel install
r = run(f"{pip} install -q {WHEEL}")
res["checks"]["wheel_install"] = {"rc": r.returncode, "err": r.stderr[-200:]}

# import + version + CLI
r = run(f"{py} -c \"import capt_solo; print(capt_solo.__version__)\"")
res["checks"]["import_version"] = {"rc": r.returncode, "out": r.stdout.strip()}
r = run(f"{py} -m capt_cli --version" if False else f"{py} -m capt_cli --help")
res["checks"]["cli_help"] = {"rc": r.returncode}
r = run(f"{py} -m capt_cli doctor")
res["checks"]["doctor"] = {"rc": r.returncode, "out": (r.stdout or r.stderr)[:200]}
r = run(f"{py} -m capt_cli release validate")
res["checks"]["release_validate"] = {"rc": r.returncode, "out": (r.stdout or r.stderr)[:120]}
r = run(f"{py} -c \"import socket; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('NET')); import capt_solo\"")
res["checks"]["no_network_import"] = {"rc": r.returncode}

# sdist install in separate venv
venv2 = os.path.join(base, "venv2")
run(f"{PY} -m venv {venv2}")
pip2 = f"{venv2}/bin/pip"; py2 = f"{venv2}/bin/python"
r = run(f"{pip2} install -q {SDIST}")
res["checks"]["sdist_install"] = {"rc": r.returncode, "err": r.stderr[-200:]}
r = run(f"{py2} -c \"import capt_solo; print(capt_solo.__version__)\"")
res["checks"]["sdist_import"] = {"rc": r.returncode, "out": r.stdout.strip()}

# uninstall + reinstall
r = run(f"{pip} uninstall -y capt-solo")
res["checks"]["uninstall"] = {"rc": r.returncode}
r = run(f"{pip} install -q {WHEEL}")
res["checks"]["reinstall"] = {"rc": r.returncode}

# optional-dep degradation: ATE without external pkg
r = run(f"{py} -c \"from capt_solo.components.anti_token_extraction import AntiTokenExtractionComponent; print('ATE ok')\"")
res["checks"]["ate_import"] = {"rc": r.returncode}

# package resource access
r = run(f"{py} -c \"import capt_solo, os; p=os.path.dirname(capt_solo.__file__); print('resources ok' if os.path.isdir(p) else 'no')\"")
res["checks"]["pkg_resource"] = {"rc": r.returncode}

shutil.rmtree(base, ignore_errors=True)
print(json.dumps(res, indent=2))
sys.exit(0 if all(v.get("rc",0)==0 for v in res["checks"].values()) else 1)
