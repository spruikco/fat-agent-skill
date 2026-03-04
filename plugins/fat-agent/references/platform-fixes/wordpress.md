# WordPress — Platform Fix Reference

Platform-specific configuration guide for WordPress sites. Covers security
headers, redirects, SSL, caching, and hardening — with actual code you can
hand to a client or drop into a theme.

---

## Security Headers

WordPress gives you three main approaches: PHP via `functions.php`, server
config via `.htaccess`, or a plugin. Pick one approach and stick with it to
avoid duplicate headers.

### functions.php Approach (Recommended)

Hook into `send_headers` to set headers before any output:

```php
// In your theme's functions.php or a custom plugin
function fat_security_headers() {
    // Only on frontend — avoid breaking wp-admin iframes
    if ( is_admin() ) {
        return;
    }

    header( 'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload' );
    header( 'X-Content-Type-Options: nosniff' );
    header( 'X-Frame-Options: SAMEORIGIN' );
    header( 'Referrer-Policy: strict-origin-when-cross-origin' );
    header( 'Permissions-Policy: camera=(), microphone=(), geolocation=()' );
    header( 'X-XSS-Protection: 1; mode=block' );
}
add_action( 'send_headers', 'fat_security_headers' );
```

**Why SAMEORIGIN instead of DENY?** WordPress uses iframes internally
(Customizer, media modal, some plugins). DENY will break those. Use
SAMEORIGIN unless you are certain no iframe embedding is needed.

**Why `is_admin()` guard?** The WordPress admin area relies on inline scripts
and iframes. Strict CSP or X-Frame-Options: DENY will break the dashboard.

### .htaccess Approach (Apache)

Add to the `.htaccess` file in the WordPress root, **above** the
`# BEGIN WordPress` block. Never edit inside the WordPress block — WordPress
will overwrite it.

```apache
# --- Security Headers (add ABOVE # BEGIN WordPress) ---
<IfModule mod_headers.c>
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
    Header always set X-XSS-Protection "1; mode=block"
</IfModule>

# BEGIN WordPress
# ... WordPress rewrite rules ...
# END WordPress
```

### Plugin Recommendations

If the client is not comfortable editing code:

| Plugin | Notes |
|--------|-------|
| **Headers Security Advanced & HSTS WP** | Free, lightweight, sets all major headers via UI |
| **Really Simple SSL** | Also adds HSTS and basic security headers |
| **Security Headers** (by suspended) | Minimal, does only headers — nothing else |

**Caution:** If using a plugin for headers, do not also set them in
`functions.php` or `.htaccess`. Duplicate headers cause unpredictable browser
behaviour.

### wp-config.php Security Constants

These are not HTTP headers, but they harden the WordPress application itself.
Add them to `wp-config.php` above the line `/* That's all, stop editing! */`:

```php
// Force SSL on the admin dashboard
define( 'FORCE_SSL_ADMIN', true );

// Disable the file editor in wp-admin (Appearance > Theme Editor)
define( 'DISALLOW_FILE_EDIT', true );

// Disable plugin/theme installation and updates from wp-admin
// Use only on production when deploys are handled via CI/CD
define( 'DISALLOW_FILE_MODS', true );

// Limit post revisions to reduce database bloat
define( 'WP_POST_REVISIONS', 5 );

// Set autosave interval (seconds)
define( 'AUTOSAVE_INTERVAL', 120 );

// Define the cookie domain for better cookie scoping
// define( 'COOKIE_DOMAIN', 'example.com' );
```

---

## Redirects & Rewrites

### Permalink Settings

WordPress handles URL structures through **Settings > Permalinks**. The
recommended structure is:

```
Post name: /%postname%/
```

This produces clean URLs like `/about-us/` instead of `/?p=123`.

**Important:** Changing permalinks on a live site will break existing links
unless you set up redirects for the old URL pattern.

### Trailing Slash Handling

WordPress enforces trailing slashes by default via `redirect_canonical()`.
This is generally correct behaviour. If you need to change it:

```php
// Remove trailing slashes (not recommended for most WordPress sites)
function fat_remove_trailing_slash( $redirect_url ) {
    if ( is_singular() ) {
        $redirect_url = untrailingslashit( $redirect_url );
    }
    return $redirect_url;
}
add_filter( 'redirect_canonical', 'fat_remove_trailing_slash' );
```

**Best practice:** Leave trailing slashes alone. WordPress, Yoast, and most
WordPress SEO tooling expect them.

### www vs non-www

Set in **Settings > General**:

- **WordPress Address (URL):** `https://example.com` or `https://www.example.com`
- **Site Address (URL):** Must match the WordPress Address

WordPress will redirect the non-canonical version automatically. If the URLs
are wrong in the database and you are locked out, override in `wp-config.php`:

```php
define( 'WP_HOME', 'https://example.com' );
define( 'WP_SITEURL', 'https://example.com' );
```

### Custom Redirects via functions.php

For one-off redirects:

```php
function fat_custom_redirects() {
    $redirects = array(
        '/old-page/'    => '/new-page/',
        '/legacy-post/' => '/updated-post/',
        '/products/'    => '/shop/',
    );

    $request_uri = $_SERVER['REQUEST_URI'];
    // Strip query string for matching
    $path = strtok( $request_uri, '?' );

    if ( array_key_exists( $path, $redirects ) ) {
        wp_redirect( home_url( $redirects[ $path ] ), 301 );
        exit;
    }
}
add_action( 'template_redirect', 'fat_custom_redirects' );
```

For large numbers of redirects, use a plugin instead — this approach doesn't
scale past a few dozen rules.

### Redirection Plugin

The **Redirection** plugin (by John Godley) is the standard for WordPress:

- Supports 301, 302, 307, 308 redirects
- Regex matching
- Tracks 404 errors
- Import/export CSV
- No performance impact (uses its own database table)

Install via: **Plugins > Add New > search "Redirection"**

### .htaccess Redirect Rules

For server-level redirects (faster than PHP, runs before WordPress loads):

```apache
# Single page redirect
Redirect 301 /old-page/ https://example.com/new-page/

# Redirect an entire directory
RedirectMatch 301 ^/blog/2020/(.*)$ https://example.com/archive/$1

# Force HTTPS (add above # BEGIN WordPress)
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</IfModule>

# Force non-www (add above # BEGIN WordPress)
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
RewriteRule ^(.*)$ https://%1/$1 [R=301,L]
</IfModule>
```

**Reminder:** Always place custom rules above `# BEGIN WordPress`. WordPress
regenerates everything between `# BEGIN WordPress` and `# END WordPress` when
permalinks are saved.

---

## SSL/HTTPS Configuration

### WordPress Address and Site Address

Both URLs in **Settings > General** must use `https://`:

- WordPress Address (URL): `https://example.com`
- Site Address (URL): `https://example.com`

If you cannot access the dashboard, set them in `wp-config.php`:

```php
define( 'WP_HOME', 'https://example.com' );
define( 'WP_SITEURL', 'https://example.com' );
```

### Force SSL for Admin

In `wp-config.php`:

```php
define( 'FORCE_SSL_ADMIN', true );
```

This forces HTTPS on the login page and the entire wp-admin area. If behind
a reverse proxy or load balancer, you may also need:

```php
// Trust the X-Forwarded-Proto header from your proxy
if ( isset( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https' ) {
    $_SERVER['HTTPS'] = 'on';
}
```

Add this **above** the `require_once ABSPATH . 'wp-settings.php';` line.

### Mixed Content After Migration

After migrating from HTTP to HTTPS, the database still contains hardcoded
`http://` URLs in post content, widget text, theme options, and serialized
data. Symptoms:

- Browser shows "Not Secure" despite HTTPS being active
- Console shows mixed content warnings
- Images or scripts fail to load

### Database Search-Replace

Use **WP-CLI** (preferred) or the **Better Search Replace** plugin.

**WP-CLI approach (recommended):**

```bash
# Dry run first — always
wp search-replace 'http://example.com' 'https://example.com' --dry-run

# If the dry run looks correct, run for real
wp search-replace 'http://example.com' 'https://example.com'

# Also catch www variant if needed
wp search-replace 'http://www.example.com' 'https://example.com'

# Flush caches after
wp cache flush
wp rewrite flush
```

**Important:** WP-CLI handles serialized data correctly. A raw SQL
`UPDATE ... REPLACE()` will corrupt serialized data and break your site.

**Better Search Replace plugin:**

1. Install and activate
2. Go to **Tools > Better Search Replace**
3. Search for `http://example.com`, replace with `https://example.com`
4. Select all tables
5. Run a dry run first, then run for real
6. Deactivate and delete the plugin when done

### Really Simple SSL (Quick Fix)

If the client needs HTTPS working immediately and will do a proper migration
later:

1. Install **Really Simple SSL**
2. Activate — it auto-detects the SSL certificate
3. Click "Go ahead, activate SSL!"

The plugin fixes mixed content on the fly by output buffering. This has a
small performance cost. A proper search-replace is the better long-term
solution.

---

## Caching Headers

### Browser Caching via .htaccess

Add to `.htaccess` above `# BEGIN WordPress`:

```apache
<IfModule mod_expires.c>
    ExpiresActive On

    # Images
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType image/x-icon "access plus 1 year"

    # Fonts
    ExpiresByType font/woff2 "access plus 1 year"
    ExpiresByType font/woff "access plus 1 year"
    ExpiresByType application/font-woff2 "access plus 1 year"

    # CSS and JavaScript
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType text/javascript "access plus 1 year"

    # HTML — short cache or no cache
    ExpiresByType text/html "access plus 0 seconds"
</IfModule>

<IfModule mod_headers.c>
    # Cache static assets aggressively
    <FilesMatch "\.(ico|jpg|jpeg|png|gif|webp|svg|woff|woff2|css|js)$">
        Header set Cache-Control "public, max-age=31536000, immutable"
    </FilesMatch>

    # No cache for HTML
    <FilesMatch "\.(html|php)$">
        Header set Cache-Control "no-cache, no-store, must-revalidate"
    </FilesMatch>
</IfModule>
```

**Note:** WordPress assets (via `wp_enqueue_script/style`) include a version
query string by default (`?ver=6.4.2`). This acts as a cache buster, so
aggressive caching of CSS/JS is safe.

### Page Caching Plugins

| Plugin | Type | Best For |
|--------|------|----------|
| **WP Super Cache** | File-based | Simple sites, shared hosting |
| **W3 Total Cache** | File + Object + CDN | Complex configurations |
| **WP Rocket** | File-based (paid) | Best UX, minimal config, just works |
| **LiteSpeed Cache** | Server-level | Sites on LiteSpeed servers (many hosts) |

**WP Rocket** is the easiest recommendation for clients. It handles page
cache, browser cache headers, JS/CSS minification, lazy loading, and database
optimization in one plugin.

### Object Caching (Redis/Memcached)

For dynamic sites with heavy database queries:

```php
// In wp-config.php — enable persistent object cache
define( 'WP_CACHE', true );

// If using Redis (with the Redis Object Cache plugin)
define( 'WP_REDIS_HOST', '127.0.0.1' );
define( 'WP_REDIS_PORT', 6379 );
// define( 'WP_REDIS_PASSWORD', 'your-redis-password' );
define( 'WP_REDIS_DATABASE', 0 );
```

Then install the **Redis Object Cache** plugin and enable it under
**Settings > Redis**.

Many managed WordPress hosts (WP Engine, Kinsta, Cloudways) include object
caching out of the box.

### Page Caching Best Practices

- **Exclude from cache:** Cart, checkout, account pages (WooCommerce), any
  page with user-specific content
- **Cache lifetime:** 12-24 hours for most sites; shorter for news sites
- **Purge strategy:** Purge on post publish/update, not on a timer
- **Logged-in users:** Never serve cached pages to logged-in users
- **Mobile:** Serve the same cache for mobile and desktop if using responsive
  design (most modern themes). Only use separate mobile caching if the site
  serves different markup

---

## WordPress-Specific Security

### Disable XML-RPC

XML-RPC (`xmlrpc.php`) enables remote publishing but is a common attack
vector for brute-force and DDoS amplification. Most modern sites use the
REST API instead.

**functions.php approach:**

```php
// Disable XML-RPC entirely
add_filter( 'xmlrpc_enabled', '__return_false' );

// Also remove the HTTP header that advertises it
remove_action( 'wp_head', 'rsd_link' );
```

**.htaccess approach (blocks all requests before PHP runs):**

```apache
<Files xmlrpc.php>
    Require all denied
</Files>
```

**Note:** Disable XML-RPC unless the site specifically uses Jetpack
(which requires it) or the WordPress mobile app for publishing.

### Hide the Login Page

The **WPS Hide Login** plugin lets you change `/wp-admin/` and `/wp-login.php`
to a custom URL (e.g., `/my-secret-login/`). This stops automated bots that
hammer the default login URL.

Alternatively, in `.htaccess`:

```apache
# Restrict wp-login.php to specific IPs
<Files wp-login.php>
    Require ip 203.0.113.50
    Require ip 198.51.100.0/24
</Files>
```

### Disable Directory Browsing

Prevent visitors from listing the contents of directories like `/wp-content/uploads/`:

```apache
# In .htaccess
Options -Indexes
```

Most hosts set this by default, but verify by visiting
`https://example.com/wp-content/uploads/` — you should get a 403, not a
directory listing.

### Disable File Editing

Prevent code editing from the WordPress dashboard:

```php
// In wp-config.php
define( 'DISALLOW_FILE_EDIT', true );
```

This removes **Appearance > Theme Editor** and **Plugins > Plugin Editor**.
If a site is compromised, this prevents attackers from modifying PHP files
through the dashboard.

For even stricter control:

```php
// Prevent all file modifications (installs, updates, edits) via wp-admin
define( 'DISALLOW_FILE_MODS', true );
```

Only use `DISALLOW_FILE_MODS` on production if updates are handled via
deployment pipeline or WP-CLI.

### Security Keys and Salts

WordPress uses authentication keys and salts to secure cookies and passwords.
They are defined in `wp-config.php`:

```php
define( 'AUTH_KEY',         'put your unique phrase here' );
define( 'SECURE_AUTH_KEY',  'put your unique phrase here' );
define( 'LOGGED_IN_KEY',   'put your unique phrase here' );
define( 'NONCE_KEY',       'put your unique phrase here' );
define( 'AUTH_SALT',        'put your unique phrase here' );
define( 'SECURE_AUTH_SALT', 'put your unique phrase here' );
define( 'LOGGED_IN_SALT',  'put your unique phrase here' );
define( 'NONCE_SALT',      'put your unique phrase here' );
```

Generate fresh keys at: https://api.wordpress.org/secret-key/1.1/salt/

**When to regenerate:** After a suspected compromise, after removing an admin
user, or if the defaults were never changed.

### Limit Login Attempts

Install **Limit Login Attempts Reloaded** or **Loginizer**:

- Locks out IPs after repeated failed logins
- Configurable lockout duration and attempt count
- Email notifications on lockout
- Compatible with WPS Hide Login

Alternatively, use **Wordfence** or **Solid Security** (formerly iThemes
Security) which include this feature along with firewall, malware scanning,
and two-factor authentication.

### Auto-Update Configuration

WordPress 5.5+ supports auto-updates for plugins and themes via the dashboard.
For finer control, use `wp-config.php`:

```php
// Enable auto-updates for minor core releases (security patches)
// This is ON by default — do not disable it
define( 'WP_AUTO_UPDATE_CORE', 'minor' );

// Or enable all core updates including major versions
// define( 'WP_AUTO_UPDATE_CORE', true );
```

For plugins and themes, control via filters:

```php
// Auto-update all plugins
add_filter( 'auto_update_plugin', '__return_true' );

// Auto-update all themes
add_filter( 'auto_update_theme', '__return_true' );
```

### Plugin and Theme Update Monitoring

Use **WP Updates Notifier** or **ManageWP** to get email alerts when updates
are available. For agencies managing multiple sites, **MainWP** provides a
centralized dashboard.

Check for abandoned plugins: if a plugin has not been updated in 2+ years and
is not compatible with the current WordPress version, recommend replacing it.

---

## Common Gotchas

### Plugins Can Conflict with Security Headers

Multiple plugins setting the same header will produce duplicate values.
Common offenders:

- Security plugins (Wordfence, Sucuri, Solid Security) each set their own headers
- Caching plugins may set Cache-Control headers that conflict with your rules
- SEO plugins may set X-Robots-Tag headers

**Fix:** Pick one place to manage headers (either a plugin, `functions.php`,
or `.htaccess`) and disable header output in all other plugins.

### Page Builders and CSP

Page builders like Elementor, Divi, WPBakery, and Beaver Builder heavily use:

- Inline `<style>` blocks (requires `'unsafe-inline'` in `style-src`)
- Inline `<script>` blocks (requires `'unsafe-inline'` in `script-src`)
- `eval()` in JavaScript (requires `'unsafe-eval'` in `script-src`)
- Dynamic loading of assets from CDNs

This makes a strict Content-Security-Policy nearly impossible on page-builder
sites. Pragmatic approach:

```php
// Minimal CSP that works with most page builders
header( "Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; font-src 'self' data: https:;" );
```

This is far from ideal but better than no CSP at all. Flag it as a known
tradeoff in the audit report.

### wp-cron.php Performance

WordPress uses a virtual cron system (`wp-cron.php`) that fires on every page
load. On high-traffic sites, this causes:

- Extra PHP execution on every request
- Delayed or duplicated scheduled tasks
- Unnecessary load on low-traffic sites (cron only fires on visits)

**Fix:** Disable WP-Cron and use a real server cron:

```php
// In wp-config.php
define( 'DISABLE_WP_CRON', true );
```

Then add a real cron job:

```bash
# Run WordPress cron every 5 minutes
*/5 * * * * curl -s https://example.com/wp-cron.php?doing_wp_cron > /dev/null 2>&1

# Or with WP-CLI (better — avoids HTTP overhead)
*/5 * * * * cd /var/www/html && wp cron event run --due-now > /dev/null 2>&1
```

### REST API Exposure

The WordPress REST API exposes data at `/wp-json/`. By default, it reveals:

- All published posts, pages, and custom post types
- User information at `/wp-json/wp/v2/users` (usernames, gravatar hashes)
- Site metadata

If the REST API is not needed publicly:

```php
// Require authentication for all REST API requests
add_filter( 'rest_authentication_errors', function( $result ) {
    if ( true === $result || is_wp_error( $result ) ) {
        return $result;
    }

    if ( ! is_user_logged_in() ) {
        return new WP_Error(
            'rest_not_logged_in',
            __( 'You are not currently logged in.' ),
            array( 'status' => 401 )
        );
    }

    return $result;
} );
```

**Warning:** Do not block the REST API entirely if the site uses Gutenberg
(the block editor), WooCommerce, Contact Form 7, or any plugin that depends
on it. The filter above is safe because it only blocks unauthenticated
requests — logged-in users (including the block editor) will still work.

### User Enumeration

Attackers can discover usernames by visiting `/?author=1`, `/?author=2`, etc.
WordPress redirects to `/author/admin/`, revealing the username.

**Fix:**

```php
// Block author archive enumeration
function fat_block_author_enum() {
    if ( isset( $_GET['author'] ) && is_numeric( $_GET['author'] ) ) {
        wp_redirect( home_url(), 301 );
        exit;
    }
}
add_action( 'template_redirect', 'fat_block_author_enum' );
```

Also block the REST API user endpoint if authentication filter above is not
in place:

```php
// Remove user endpoints from REST API
add_filter( 'rest_endpoints', function( $endpoints ) {
    if ( isset( $endpoints['/wp/v2/users'] ) ) {
        unset( $endpoints['/wp/v2/users'] );
    }
    if ( isset( $endpoints['/wp/v2/users/(?P<id>[\d]+)'] ) ) {
        unset( $endpoints['/wp/v2/users/(?P<id>[\d]+)'] );
    }
    return $endpoints;
} );
```

### Keep Everything Updated

- **WordPress core:** Enable minor auto-updates (on by default)
- **Plugins:** Update weekly; enable auto-updates for trusted plugins
- **Themes:** Update when available; remove unused themes
- **PHP version:** Use PHP 8.1+ (8.2 or 8.3 recommended for WordPress 6.x)
- **Remove unused plugins/themes:** Deactivated plugins can still be exploited

### wp-config.php Must Not Be Web-Accessible

`wp-config.php` contains database credentials, security keys, and other
secrets. It should never be accessible via a browser.

**Verify:** Visit `https://example.com/wp-config.php` — you should get a
blank page (PHP is executed, not displayed) or a 403. If you see PHP source
code, the server is dangerously misconfigured.

**Extra protection via .htaccess:**

```apache
<Files wp-config.php>
    Require all denied
</Files>
```

Some security guides recommend moving `wp-config.php` one directory above
the WordPress root. WordPress supports this natively — it checks the parent
directory automatically.

---

## Complete Config Examples

### functions.php — Security Snippet

Drop this into the active theme's `functions.php` or, better, into a
site-specific plugin to survive theme changes:

```php
<?php
/**
 * FAT Agent — WordPress Security Hardening
 * Add to functions.php or create as a must-use plugin in wp-content/mu-plugins/
 */

// ── Security Headers ──────────────────────────────────────────────
function fat_security_headers() {
    if ( is_admin() ) {
        return;
    }

    header( 'Strict-Transport-Security: max-age=31536000; includeSubDomains; preload' );
    header( 'X-Content-Type-Options: nosniff' );
    header( 'X-Frame-Options: SAMEORIGIN' );
    header( 'Referrer-Policy: strict-origin-when-cross-origin' );
    header( 'Permissions-Policy: camera=(), microphone=(), geolocation=()' );
    header( 'X-XSS-Protection: 1; mode=block' );
}
add_action( 'send_headers', 'fat_security_headers' );

// ── Disable XML-RPC ───────────────────────────────────────────────
add_filter( 'xmlrpc_enabled', '__return_false' );
remove_action( 'wp_head', 'rsd_link' );

// ── Block Author Enumeration ──────────────────────────────────────
function fat_block_author_enum() {
    if ( isset( $_GET['author'] ) && is_numeric( $_GET['author'] ) ) {
        wp_redirect( home_url(), 301 );
        exit;
    }
}
add_action( 'template_redirect', 'fat_block_author_enum' );

// ── Restrict REST API to Logged-In Users ──────────────────────────
add_filter( 'rest_authentication_errors', function( $result ) {
    if ( true === $result || is_wp_error( $result ) ) {
        return $result;
    }
    if ( ! is_user_logged_in() ) {
        return new WP_Error(
            'rest_not_logged_in',
            __( 'REST API access restricted.' ),
            array( 'status' => 401 )
        );
    }
    return $result;
} );

// ── Remove Unnecessary Head Output ────────────────────────────────
remove_action( 'wp_head', 'wp_generator' );               // WordPress version
remove_action( 'wp_head', 'wlwmanifest_link' );           // Windows Live Writer
remove_action( 'wp_head', 'wp_shortlink_wp_head' );       // Shortlink
remove_action( 'wp_head', 'rest_output_link_wp_head' );   // REST API link
remove_action( 'wp_head', 'wp_oembed_add_discovery_links' ); // oEmbed

// ── Disable File Editing from Dashboard ───────────────────────────
// (This is better placed in wp-config.php, but included here as a fallback)
if ( ! defined( 'DISALLOW_FILE_EDIT' ) ) {
    define( 'DISALLOW_FILE_EDIT', true );
}

// ── Auto-Update Plugins and Themes ────────────────────────────────
add_filter( 'auto_update_plugin', '__return_true' );
add_filter( 'auto_update_theme', '__return_true' );
```

**Tip:** To survive theme switches, save this as
`wp-content/mu-plugins/fat-security.php`. Must-use plugins load
automatically and cannot be deactivated from the dashboard.

### wp-config.php — Security Constants

Add these lines to `wp-config.php` above `/* That's all, stop editing! */`:

```php
<?php
// ── SSL / HTTPS ───────────────────────────────────────────────────
define( 'FORCE_SSL_ADMIN', true );

// Uncomment if behind a reverse proxy / load balancer
// if ( isset( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https' ) {
//     $_SERVER['HTTPS'] = 'on';
// }

// ── Site URLs (uncomment to override database values) ─────────────
// define( 'WP_HOME', 'https://example.com' );
// define( 'WP_SITEURL', 'https://example.com' );

// ── File System Security ──────────────────────────────────────────
define( 'DISALLOW_FILE_EDIT', true );
// define( 'DISALLOW_FILE_MODS', true );  // Uncomment for locked-down production

// ── Performance ───────────────────────────────────────────────────
define( 'DISABLE_WP_CRON', true );        // Use server cron instead
define( 'WP_POST_REVISIONS', 5 );
define( 'AUTOSAVE_INTERVAL', 120 );
define( 'WP_CACHE', true );               // Required for most caching plugins

// ── Database ──────────────────────────────────────────────────────
// Use a unique table prefix (not wp_)
$table_prefix = 'fxq_';

// ── Security Keys ─────────────────────────────────────────────────
// Generate fresh keys: https://api.wordpress.org/secret-key/1.1/salt/
define( 'AUTH_KEY',         'generate-a-unique-key-here' );
define( 'SECURE_AUTH_KEY',  'generate-a-unique-key-here' );
define( 'LOGGED_IN_KEY',   'generate-a-unique-key-here' );
define( 'NONCE_KEY',       'generate-a-unique-key-here' );
define( 'AUTH_SALT',        'generate-a-unique-key-here' );
define( 'SECURE_AUTH_SALT', 'generate-a-unique-key-here' );
define( 'LOGGED_IN_SALT',  'generate-a-unique-key-here' );
define( 'NONCE_SALT',      'generate-a-unique-key-here' );

// ── Debug (disable on production) ─────────────────────────────────
define( 'WP_DEBUG', false );
define( 'WP_DEBUG_LOG', false );
define( 'WP_DEBUG_DISPLAY', false );
define( 'SCRIPT_DEBUG', false );

/* That's all, stop editing! Happy publishing. */
```

### .htaccess — Complete Security Block

Place this entire block **above** `# BEGIN WordPress`:

```apache
# ── Security Headers ──────────────────────────────────────────────
<IfModule mod_headers.c>
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
</IfModule>

# ── Block Sensitive Files ─────────────────────────────────────────
<FilesMatch "^(wp-config\.php|\.htaccess|readme\.html|license\.txt)$">
    Require all denied
</FilesMatch>

# ── Block XML-RPC ─────────────────────────────────────────────────
<Files xmlrpc.php>
    Require all denied
</Files>

# ── Disable Directory Browsing ────────────────────────────────────
Options -Indexes

# ── Block PHP in Uploads ──────────────────────────────────────────
<Directory "/var/www/html/wp-content/uploads">
    <FilesMatch "\.php$">
        Require all denied
    </FilesMatch>
</Directory>

# ── Force HTTPS ───────────────────────────────────────────────────
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
</IfModule>

# ── Browser Caching ──────────────────────────────────────────────
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType font/woff2 "access plus 1 year"
    ExpiresByType font/woff "access plus 1 year"
</IfModule>

# BEGIN WordPress
# ... (managed by WordPress — do not edit) ...
# END WordPress
```

---

## Quick Audit Checklist

Use this to verify a WordPress site's configuration at a glance:

| Check | How to Verify | Priority |
|-------|---------------|----------|
| HTTPS active on all pages | Visit site, check browser padlock | P0 |
| Security headers present | `curl -I https://example.com` | P1 |
| WordPress and plugins updated | Dashboard > Updates | P1 |
| XML-RPC disabled | Visit `/xmlrpc.php` — should be 403 or empty | P2 |
| File editor disabled | Check Appearance menu — no Theme Editor | P2 |
| Directory browsing off | Visit `/wp-content/uploads/` — should be 403 | P2 |
| wp-config.php not accessible | Visit `/wp-config.php` — blank or 403 | P1 |
| Login page protected | Check for brute-force protection plugin | P2 |
| REST API restricted | Visit `/wp-json/wp/v2/users` — should be 401 | P3 |
| Author enumeration blocked | Visit `/?author=1` — should redirect to home | P3 |
| Debug mode off in production | Confirm `WP_DEBUG` is `false` | P1 |
| Caching active | Check response headers for `x-cache` or plugin | P2 |
| PHP version current | Dashboard > Tools > Site Health | P2 |
| Unused themes removed | Appearance > Themes — only active + one default | P3 |
| Unused plugins removed | Plugins — no deactivated plugins | P3 |
