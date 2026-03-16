# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: Apache-2.0

"""Generate CI map page from GitHub Actions workflows."""

import mkdocs_gen_files

from mkdocs_terok.ci_map import generate_ci_map

markdown = generate_ci_map()

with mkdocs_gen_files.open("ci-map.md", "w") as f:
    f.write(markdown)
