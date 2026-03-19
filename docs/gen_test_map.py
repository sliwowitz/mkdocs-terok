# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Generate test suite map page."""

from pathlib import Path

import mkdocs_gen_files

from mkdocs_terok.test_map import TestMapConfig, generate_test_map

config = TestMapConfig(
    integration_dir=Path("tests"),
    show_markers=False,
    title="Test Suite Map",
)

markdown = generate_test_map(config=config)

with mkdocs_gen_files.open("test-map.md", "w") as f:
    f.write(markdown)
