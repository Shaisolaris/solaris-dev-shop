> "Missing CSRF protection in `save_settings_handler()` at `includes/admin/class-settings.php:142`. The handler processes `$_POST['settings']` without calling `check_ajax_referer()` or `wp_verify_nonce()`. The corresponding form at `templates/admin/settings.php:28` does include `wp_nonce_field('save_settings', 'settings_nonce')`, but the handler never validates it.
>
> **Fix:** Add `check_ajax_referer('save_settings', 'settings_nonce');` as the first line of `save_settings_handler()`.
>
> **Test:** See `tests/security/Nonce/SaveSettingsNonceTest.php` - verifies that requests without valid nonce return 403."
