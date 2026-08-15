from __future__ import annotations

import io
import json
from typing import Final

import pytest

from comment_density import Density, count_density, main

PYTHON_DIFF: Final[str] = """\
diff --git a/app/spa.py b/app/spa.py
--- a/app/spa.py
+++ b/app/spa.py
@@ -10,0 +11,9 @@
+def serve_spa(*, app: FastAPI) -> None:
+    \"\"\"Serve the built frontend from the API's origin.
+
+    With no build, serve the API alone.
+    \"\"\"
+    build: Path = Path(os.environ.get(SPA_DIR_ENV, DEFAULT_SPA_DIR))
+    # Router default, not Mount("/"): a route registered later still wins.
+    app.router.default = _SpaFallback(directory=build)
-    old_line = 1
"""


def test_python_docstring_and_hash_lines_count_as_comments() -> None:
    # Blank lines count on neither side, inside a docstring or out.
    density: Density = count_density(diff=PYTHON_DIFF)
    assert density.comment_lines_added == 4
    assert density.code_lines_added == 3


TS_DIFF: Final[str] = """\
diff --git a/src/cart.ts b/src/cart.ts
--- a/src/cart.ts
+++ b/src/cart.ts
@@ -0,0 +1,7 @@
+/** Total after discount. */
+export function total(cart: Cart): number {
+  /* Cents, not dollars:
+     rounding happens once. */
+  const cents = cart.items.reduce((sum, item) => sum + item.cents, 0);
+  return cents; // one return
+}
"""


LITERAL_DIFF: Final[str] = """\
diff --git a/app/fixture.py b/app/fixture.py
--- a/app/fixture.py
+++ b/app/fixture.py
@@ -0,0 +1,4 @@
+SAMPLE: Final[str] = \"\"\"\\
+first line
+second line
+\"\"\"
"""


def test_a_string_literal_assigned_to_a_name_is_code_not_a_docstring() -> None:
    density: Density = count_density(diff=LITERAL_DIFF)
    assert density.comment_lines_added == 0
    assert density.code_lines_added == 4


def test_slash_and_block_comments_count_in_c_style_languages() -> None:
    # A trailing `// ...` on a code line stays a code line.
    density: Density = count_density(diff=TS_DIFF)
    assert density.comment_lines_added == 3
    assert density.code_lines_added == 4


def test_cli_prints_the_density_as_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(PYTHON_DIFF))
    main()
    printed: dict[str, int] = json.loads(capsys.readouterr().out)
    assert printed == {"comment_lines_added": 4, "code_lines_added": 3}


def test_any_diff_prefix_is_accepted() -> None:
    # `diff.mnemonicPrefix` (i/ w/ c/) changes the header, not the count.
    density: Density = count_density(diff=PYTHON_DIFF.replace("+++ b/", "+++ w/"))
    assert density.comment_lines_added == 4
