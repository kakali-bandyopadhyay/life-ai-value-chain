"""README content, link and data-derived count checks."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

from ai_value_chain.data import DATA_DIR, REPO_ROOT, load_controls, load_use_cases


README = REPO_ROOT / "README.md"
GITHUB_PREFIX = "https://github.com/kakali-bandyopadhyay/life-ai-value-chain/"
PAGES_URL = "https://kakali-bandyopadhyay.github.io/life-ai-value-chain/"
LABEL_LINE = "Simulated scenario · synthetic data · illustrative, not legal advice"


def test_readme_sections_commands_boundaries_and_data_counts():
    readme = README.read_text(encoding="utf-8")
    headings = re.findall(r"^(#{1,2})\s+(.+?)\s*$", readme, re.MULTILINE)
    assert headings == [
        ("#", "Life and protection AI value-chain assessment"),
        ("##", "What it is"),
        ("##", "How the assessment works"),
        ("##", "Worked governance"),
        ("##", "Quickstart"),
        ("##", "File map"),
        ("##", "Boundaries"),
        ("##", "Licence"),
    ]
    assert LABEL_LINE in readme
    assert PAGES_URL in readme
    for command in (
        "python -m venv .venv",
        r".\.venv\Scripts\Activate.ps1",
        'pip install -e ".[dev]"',
        "python -m pytest",
        "python -m ai_value_chain validate",
        "python -m ai_value_chain assess --appetite high --weights 5,3,2",
        "python -m ai_value_chain build",
    ):
        assert command in readme
    assert "export_diagram" not in readme
    assert "docs/diagrams" not in readme
    assert not re.search(r"<\s*/?\s*[A-Za-z][^>]*>", readme)
    assert "![" not in readme
    assert not re.search(r"^\s*Personal prototype\b", readme, re.IGNORECASE | re.MULTILINE)

    cases = load_use_cases()
    controls = load_controls()
    for use_case_id in ("VC-01", "VC-05"):
        rows = [row for row in controls if row["use_case_id"] == use_case_id]
        counts = Counter(row["test_result"] for row in rows)
        exceptions = sum(bool(row.get("exception_id")) for row in rows)
        expected = (
            f"Its controls record {counts['pass']} pass, {counts['fail']} fail, "
            f"{counts['not tested']} not tested and {exceptions} exception"
        )
        assert expected in readme
    assert len([row for row in cases if row["worked_governance"]]) == 2
    assert len(cases) == 14


def test_readme_links_are_absolute_and_repository_paths_exist():
    readme = README.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
    assert links
    for link in links:
        assert link.startswith(GITHUB_PREFIX) or link == PAGES_URL
        if link == PAGES_URL:
            continue
        parsed = urlparse(link)
        assert parsed.netloc == "github.com"
        path_parts = parsed.path.strip("/").split("/")
        assert len(path_parts) >= 5
        assert path_parts[0:2] == ["kakali-bandyopadhyay", "life-ai-value-chain"]
        assert path_parts[2] in {"blob", "tree"} and path_parts[3] == "main"
        relative = unquote("/".join(path_parts[4:]))
        assert relative
        assert (REPO_ROOT / relative).exists(), relative
    assert all(link.startswith(GITHUB_PREFIX) for link in links if "github.com" in link)
