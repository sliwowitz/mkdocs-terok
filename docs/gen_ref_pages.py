# SPDX-FileCopyrightText: 2026 Jiri Vyskocil
# SPDX-License-Identifier: 0BSD

"""Generate API reference pages and copy brand CSS into the virtual filesystem."""

import mkdocs_gen_files

from mkdocs_terok import brand_css_path
from mkdocs_terok.ref_pages import RefPagesConfig, generate_ref_pages

nav = mkdocs_gen_files.Nav()

config = RefPagesConfig(skip_patterns=("__main__", "resources", "_assets"))


def write_file(doc_path: str, content: str) -> None:
    """Write a documentation page into the virtual filesystem."""
    with mkdocs_gen_files.open(doc_path, "w") as f:
        f.write(content)


def set_edit_path(doc_path: str, source_path: str) -> None:
    """Map a doc page back to its source file for edit links."""
    mkdocs_gen_files.set_edit_path(doc_path, source_path)


entries = generate_ref_pages(config, write_file=write_file, set_edit_path=set_edit_path)

prefix = config.output_prefix + "/"
for parts, doc_path in entries:
    nav[parts] = doc_path.removeprefix(prefix)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

# Copy brand CSS into the virtual filesystem
css_content = brand_css_path().read_text()
with mkdocs_gen_files.open("_assets/extra.css", "w") as css_file:
    css_file.write(css_content)
