# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Generate quality report page with graceful degradation for missing tools."""

import mkdocs_gen_files

from mkdocs_terok.quality_report import generate_quality_report

result = generate_quality_report()

with mkdocs_gen_files.open("quality-report.md", "w") as f:
    f.write(result.markdown)

for path, content in result.companion_files.items():
    with mkdocs_gen_files.open(path, "w") as f:
        f.write(content)
