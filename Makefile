# TunaCode - Deprecated Makefile
# 
# ⚠️  DEPRECATION NOTICE ⚠️
# 
# This Makefile is deprecated and will be removed in the next minor version.
# Please migrate to using Hatch commands for better cross-platform support:
#
#   make install     → hatch run install
#   make run         → hatch run run  
#   make clean       → hatch run clean
#   make lint        → hatch run lint
#   make lint-check  → hatch run lint-check
#   make test        → hatch run test
#   make coverage    → hatch run coverage
#   make build       → hatch build
#   make vulture     → hatch run vulture
#   make dead-code-* → hatch run dead-code-*
#   make *-playwright→ hatch run *-playwright
#
# Benefits of migrating to Hatch:
# - Cross-platform compatibility (Windows, macOS, Linux)
# - No external make dependency required
# - Better Python ecosystem integration
# - Consistent behavior across environments
#
# Documentation: https://hatch.pypa.io/latest/

.PHONY: install clean lint format test coverage build remove-playwright-binaries restore-playwright-binaries
.PHONY: vulture vulture-check dead-code-check dead-code-clean dead-code-report

define deprecation_warning
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "⚠️  DEPRECATION WARNING: Makefile is deprecated!"
	@echo ""
	@echo "Please use: hatch run $(1)"
	@echo "This Makefile will be removed in the next minor version."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
endef

install:
	$(call deprecation_warning,install)

run:
	$(call deprecation_warning,run)

clean:
	$(call deprecation_warning,clean)

lint:
	$(call deprecation_warning,lint)

lint-check:
	$(call deprecation_warning,lint-check)

vulture:
	$(call deprecation_warning,vulture)

vulture-check:
	$(call deprecation_warning,vulture-check)

dead-code-check:
	$(call deprecation_warning,dead-code-check)

dead-code-clean:
	$(call deprecation_warning,dead-code-clean)

dead-code-report:
	$(call deprecation_warning,dead-code-report)

test:
	$(call deprecation_warning,test)

coverage:
	$(call deprecation_warning,coverage)

build:
	$(call deprecation_warning,build)

remove-playwright-binaries:
	$(call deprecation_warning,remove-playwright)

restore-playwright-binaries:
	$(call deprecation_warning,restore-playwright)