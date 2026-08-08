"""CAPT UI Foundation.

Thin presentation and operator-control surfaces (CLI/TUI/Desktop) over CAPT
RuntimeService. All surfaces share `capt_ui.operator` — a single operator
abstraction. No duplicated runtime logic; authority stays in RuntimeService.
"""
