# Changelog

Versions follow [Semantic Versioning](https://semver.org/); 0.x — work in progress.

## [Unreleased]
- Drag-and-drop upload of folders with their whole structure (nested and empty folders included).

## [0.5.0] — 2026-11-19 — Server installation
- Installation on a server: `docker-compose.yml` and `install.sh` — works with the server's own files and users.
- Upscaled icons in "Max retina mode": xBRZ and Real-ESRGAN variants to compare (Settings → Interface).

## [0.4.0] — 2026-11-19 — Interface
- Path inputs above both panels on the top menu bar; the ▾ button slides the original menu out temporarily.
  Original breadcrumbs on the panels are kept.
- "Full path" button: full path of the selected file to the clipboard and on screen.
- Drag-and-drop upload onto a panel.
- Sharper icons on Retina/4K where a native large version of the same artwork exists; "Max retina mode" setting.
- Fast search is on by default.

## [0.3.0] — 2026-11-19 — Fast search
- Fast search: ripgrep / grep / find, locally and over SSH in one command; fallback to the original search.

## [0.2.0] — 2026-11-18 — Remote servers
- SFTP, FTP and WebDAV verified against test servers.

## [0.1.0] — 2026-11-18 — New stack
- Backend ported to Python 3.12 / Tornado 6.
- Docker Compose stand with the original and the new stack; API and Playwright E2E tests.
