.PHONY: checks format clean

PACKAGE_PATH=redato_backend

format:
	@isort redato_backend/**/*.py
	@poetry run black redato_backend

checks:
	@poetry run flake8 redato_backend
	@poetry run black --check redato_backend
	@isort --check-only redato_backend/**/*.py

clean:
	find . -type f -name '*.pyc' -delete
	-rm -rf $(PACKAGE_PATH)/lib
	-rm -rf $(PACKAGE_PATH)/*.egg-info
	-rm -rf $(PACKAGE_PATH)/.coverage
	-rm -rf $(PACKAGE_PATH)/.eggs
	-rm -rf $(PACKAGE_PATH)/.tox
	-rm -rf $(PACKAGE_PATH)/__pycache__
	-rm -rf $(PACKAGE_PATH)/cover
	-rm -rf $(PACKAGE_PATH)/dist
	-rm -rf $(PACKAGE_PATH)/spark-warehouse
	-rm -rf $(PACKAGE_PATH)/*.log
