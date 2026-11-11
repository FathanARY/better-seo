.PHONY: check test check-live install clean

PY ?= python
TMPOUT ?= .live-audit.json

check: clean
	@$(MAKE) --no-print-directory test
	@echo "all checks passed"

test:
	@$(PY) tests/test_manifests.py
	@$(PY) scripts/trigger_check.py
	@$(PY) tests/test_audit.py
	@$(PY) tests/test_crawl.py
	@$(PY) tests/test_seo_build.py
	@$(PY) tests/test_seo_data.py
	@$(PY) tests/test_install.py

# Uses the network: proves the CLI still works against a live page.
check-live:
	@$(PY) skills/better-seo/scripts/audit.py https://example.com --quiet --json $(TMPOUT)
	@$(PY) tests/check_live_cli.py $(TMPOUT)
	@rm -f $(TMPOUT)

# Resolve a real bash first: on Windows the `bash` on PATH can be the WSL stub.
install:
	@$(PY) -c "import subprocess,sys;sys.path.insert(0,'tests');from test_install import find_bash;b=find_bash() or 'bash';sys.exit(subprocess.call([b,'install.sh']))"

clean:
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache
