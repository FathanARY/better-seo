.PHONY: check test install clean

PY ?= python

check: test
	@echo "all checks passed"

test:
	@$(PY) scripts/trigger_check.py
	@$(PY) tests/test_audit.py
	@$(PY) tests/test_install.py

# Resolve a real bash first: on Windows the `bash` on PATH can be the WSL stub.
install:
	@$(PY) -c "import subprocess,sys;sys.path.insert(0,'tests');from test_install import find_bash;b=find_bash() or 'bash';sys.exit(subprocess.call([b,'install.sh']))"

clean:
	@rm -rf __pycache__ tests/__pycache__ scripts/__pycache__ .pytest_cache
