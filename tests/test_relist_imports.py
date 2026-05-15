"""Tests for ME-01 fix — AuthManager imported at module level in relist.py.

Verifies that AuthManager is imported at module level and not inside methods.
"""

import ast
from pathlib import Path


class TestRelistImports:
    """Verify that imports are at module level, not inside methods."""

    def test_relist_py_has_no_local_auth_imports(self):
        """ME-01 fix: AuthManager must be imported at module level."""
        relist_path = Path(__file__).parent.parent / "browser" / "relist.py"
        with open(relist_path) as f:
            tree = ast.parse(f.read())

        # Check that AuthManager is imported at module level
        module_level_imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "browser.auth":
                    for alias in node.names:
                        module_level_imports.append(alias.name)

        assert "AuthManager" in module_level_imports, "AuthManager should be imported at module level from browser.auth"

        # Check that there are no imports inside function bodies
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        assert False, f"Local import found inside function {node.name}"

    def test_relist_py_imports_authmanager_at_module_level(self):
        """Verify the exact import statement exists at module level."""
        relist_path = Path(__file__).parent.parent / "browser" / "relist.py"
        with open(relist_path) as f:
            content = f.read()

        # Verify that the import is at module level (not indented)
        lines = content.split("\n")
        found_import = False
        for line in lines:
            stripped = line.strip()
            if stripped == "from browser.auth import AuthManager":
                # Check that it's at module level (no indentation)
                assert not line.startswith(" ") and not line.startswith("\t"), (
                    "AuthManager import should be at module level (no indentation)"
                )
                found_import = True
                break

        assert found_import, "from browser.auth import AuthManager not found at module level"
