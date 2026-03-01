from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Enforce project template/static contracts: single template root, "
        "non-versioned static names, no legacy static references, no duplicate css/js payloads."
    )

    TEMPLATE_EXTENSIONS = {".html", ".txt", ".xml"}
    TEXT_EXTENSIONS = {".py", ".html", ".css", ".js"}
    LEGACY_REFERENCES = (
        "css/" + "app.css",
        "js/" + "app.js",
        "css/" + "admin_" + "topbar.css",
        "js/" + "admin_" + "topbar.js",
        "js/" + "admin_" + "user_shortcuts.js",
        "css/" + "admin_" + "v2.css",
        "js/" + "admin_" + "v2.js",
        "ENABLE_ADMIN_" + "V2",
        "admin" + "_v2",
        "admin" + "-v2",
    )
    VERSION_TOKEN_RE = re.compile(r"(^|[_-])v\d+([._-]|$)", re.IGNORECASE)

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR).resolve()
        template_root = (base_dir / "templates").resolve()
        static_root = (base_dir / "static").resolve()

        violations = []
        violations.extend(self._check_templates_outside_root(base_dir, template_root))
        violations.extend(self._check_static_version_tokens(static_root))
        violations.extend(self._check_legacy_references(base_dir))
        violations.extend(self._check_duplicate_static_payloads(static_root))

        if violations:
            details = "\n".join(f"- {entry}" for entry in violations)
            raise CommandError(
                "Project contract validation failed:\n"
                f"{details}"
            )

        self.stdout.write(self.style.SUCCESS("Project contract validation passed."))

    def _is_excluded_path(self, path: Path) -> bool:
        parts = set(path.parts)
        return ".venv" in parts or "staticfiles" in parts or "__pycache__" in parts

    def _iter_files(self, base_dir: Path, extensions: set[str]):
        for path in base_dir.rglob("*"):
            if not path.is_file():
                continue
            if self._is_excluded_path(path):
                continue
            if path.suffix.lower() not in extensions:
                continue
            yield path

    def _check_templates_outside_root(self, base_dir: Path, template_root: Path):
        violations = []
        for templates_dir in base_dir.rglob("templates"):
            if self._is_excluded_path(templates_dir):
                continue
            resolved = templates_dir.resolve()
            if resolved == template_root:
                continue
            has_project_templates = any(
                path.is_file() and path.suffix.lower() in self.TEMPLATE_EXTENSIONS
                for path in templates_dir.rglob("*")
                if not self._is_excluded_path(path)
            )
            if has_project_templates:
                violations.append(f"Project templates found outside root: {templates_dir}")
        return violations

    def _check_static_version_tokens(self, static_root: Path):
        violations = []
        for section in ("css", "js"):
            section_dir = static_root / section
            if not section_dir.exists():
                continue
            for asset in section_dir.rglob("*"):
                if not asset.is_file():
                    continue
                if self.VERSION_TOKEN_RE.search(asset.name):
                    violations.append(f"Version token in static filename: {asset}")
        return violations

    def _check_legacy_references(self, base_dir: Path):
        violations = []
        for path in self._iter_files(base_dir, self.TEXT_EXTENSIONS):
            content = path.read_text(encoding="utf-8", errors="ignore")
            violations.extend(
                f"Legacy reference '{token}' in {path}"
                for token in self.LEGACY_REFERENCES
                if token in content
            )
        return violations

    def _check_duplicate_static_payloads(self, static_root: Path):
        hash_to_paths: dict[str, list[Path]] = {}
        for section in ("css", "js"):
            section_dir = static_root / section
            if not section_dir.exists():
                continue
            for asset in section_dir.rglob("*"):
                if not asset.is_file():
                    continue
                digest = hashlib.sha256(asset.read_bytes()).hexdigest()
                hash_to_paths.setdefault(digest, []).append(asset)

        violations = []
        for paths in hash_to_paths.values():
            if len(paths) > 1:
                joined = ", ".join(str(path) for path in paths)
                violations.append(f"Duplicate static payload detected: {joined}")
        return violations
