# Changelog

## 2.0.0 (2026-03-11)

Modernized fork for Django 5.x+ and Python 3.10+.

### Breaking Changes

- Dropped support for Django < 5.0 and Python < 3.10.
- Renamed `http_status` class to `HttpStatus` (PEP 8).
- Removed `is_authenticated()` callable fallback (Django < 2.0).

### Changes

- Added proper `AppConfig` with `default_auto_field = BigAutoField`.
- Replaced `super(ClassName, self)` with `super()`.
- Replaced `%`-formatting with f-strings.
- Used `gettext_lazy` for model field choices.
- Removed dead `DateTimeAwareJSONEncoder` import fallback.
- Fixed `ContentFile('')` to `ContentFile(b"")` (explicit bytes).
- Simplified storage class resolution logic.
- Fixed duplicate `search_fields` in admin.
- Management command uses `self.stdout.write()` instead of `print()`.
- Uses `src/` layout for proper packaging.
- Added `py.typed` marker for type checker support.
