# Apache -- Platform Fix Reference

Quick-reference for the FAT Agent when a site is running on Apache (httpd).
All examples use `.htaccess` unless noted otherwise; the same directives work
inside `<VirtualHost>` blocks in `httpd.conf` / `sites-available/*.conf`.

---

## Security Headers

Use `mod_headers` to set every recommended security header. Wrap everything in
an `<IfModule>` guard so the config does not cause a 500 error if `mod_headers`
is not loaded.

```apache
<IfModule mod_headers.c>
    # HSTS -- force HTTPS for one year, include subdomains, allow preload list
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"

    # Prevent MIME-type sniffing
    Header always set X-Content-Type-Options "nosniff"

    # Clickjacking protection (use SAMEORIGIN if you embed your own iframes)
    Header always set X-Frame-Options "DENY"

    # Control referrer information sent cross-origin
    Header always set Referrer-Policy "strict-origin-when-cross-origin"

    # Disable browser features you do not use
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()"

    # Content Security Policy -- MUST be customised per site
    # The example below is restrictive; loosen as needed for your CDN, analytics, fonts, etc.
    Header always set Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
</IfModule>
```

**`Header set` vs `Header always set`:** Use `always` so the header is sent on
error responses (4xx, 5xx) too -- not just on 2xx.

**Why `IfModule` guards matter:** Shared hosts may not have every module loaded.
Without the guard, Apache refuses to start (or returns 500) when it encounters
a directive from a missing module.

---

## Redirects & Rewrites

### Enable mod_rewrite

Every rewrite rule requires the engine to be turned on first:

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
</IfModule>
```

### HTTP to HTTPS

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{HTTPS} off
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</IfModule>
```

### www to non-www

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
    RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]
</IfModule>
```

### non-www to www

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{HTTP_HOST} !^www\. [NC]
    RewriteRule ^ https://www.%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
</IfModule>
```

### Trailing Slash -- Add Trailing Slash

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    # Only add slash to paths that are not real files
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_URI} !(.*)/$
    RewriteRule ^(.*)$ $1/ [L,R=301]
</IfModule>
```

### Trailing Slash -- Remove Trailing Slash

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteCond %{REQUEST_URI} (.+)/$
    RewriteRule ^ %1 [L,R=301]
</IfModule>
```

### Custom 404 Error Page

```apache
ErrorDocument 404 /404.html
ErrorDocument 403 /403.html
ErrorDocument 500 /500.html
```

The path is relative to the `DocumentRoot`. You can also point to a full URL or
a CGI script:

```apache
ErrorDocument 404 /errors/not-found.php
```

### Common Rewrite Patterns

**Single page redirect (moved permanently):**

```apache
Redirect 301 /old-page /new-page
```

**Redirect an entire directory:**

```apache
RedirectMatch 301 ^/blog/(.*)$ /articles/$1
```

**Remove `.html` extensions (clean URLs):**

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    # Serve file.html when /file is requested
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteCond %{REQUEST_FILENAME}.html -f
    RewriteRule ^(.+)$ $1.html [L]
</IfModule>
```

**Remove `.php` extensions:**

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteCond %{REQUEST_FILENAME}.php -f
    RewriteRule ^(.+)$ $1.php [L]
</IfModule>
```

**Force lowercase URLs:**

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteMap lowercase int:tolower
    RewriteCond %{REQUEST_URI} [A-Z]
    RewriteRule ^(.*)$ ${lowercase:$1} [R=301,L]
</IfModule>
```

Note: `RewriteMap` only works inside `httpd.conf` / `<VirtualHost>`, not in
`.htaccess`.

---

## SSL / HTTPS Configuration

### Let's Encrypt with Certbot

Install Certbot and obtain a certificate:

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install certbot python3-certbot-apache

# Obtain and auto-configure
sudo certbot --apache -d example.com -d www.example.com

# Auto-renewal (certbot installs a cron/systemd timer by default)
sudo certbot renew --dry-run
```

Certbot will modify your VirtualHost config automatically, adding the SSL
directives shown below.

### VirtualHost SSL Configuration

In `/etc/apache2/sites-available/example.com-le-ssl.conf` (or equivalent):

```apache
<VirtualHost *:443>
    ServerName example.com
    ServerAlias www.example.com
    DocumentRoot /var/www/example.com/public

    SSLEngine on
    SSLCertificateFile      /etc/letsencrypt/live/example.com/fullchain.pem
    SSLCertificateKeyFile   /etc/letsencrypt/live/example.com/privkey.pem

    # Modern SSL settings (TLS 1.2+ only)
    SSLProtocol             all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
    SSLHonorCipherOrder     off
    SSLSessionTickets       off

    # OCSP Stapling
    SSLUseStapling          on
    SSLStaplingResponderTimeout 5
    SSLStaplingReturnResponderErrors off

    <Directory /var/www/example.com/public>
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/example.com-error.log
    CustomLog ${APACHE_LOG_DIR}/example.com-access.log combined
</VirtualHost>

# OCSP Stapling Cache (must be outside VirtualHost)
SSLStaplingCache shmcb:/var/run/apache2/stapling_cache(128000)
```

### Redirect All HTTP to HTTPS (VirtualHost method)

```apache
<VirtualHost *:80>
    ServerName example.com
    ServerAlias www.example.com
    Redirect permanent / https://example.com/
</VirtualHost>
```

This is more efficient than a `.htaccess` RewriteRule for the same purpose
because Apache does not need to process the rewrite engine on every request.

---

## Caching Headers

### mod_expires -- Set Expiry by File Type

```apache
<IfModule mod_expires.c>
    ExpiresActive On

    # Default: 1 week
    ExpiresDefault "access plus 1 week"

    # HTML -- short cache (content changes often)
    ExpiresByType text/html "access plus 0 seconds"

    # CSS & JavaScript -- long cache (use fingerprinted filenames to bust)
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType text/javascript "access plus 1 year"

    # Images
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/avif "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType image/x-icon "access plus 1 year"

    # Fonts
    ExpiresByType font/woff "access plus 1 year"
    ExpiresByType font/woff2 "access plus 1 year"
    ExpiresByType application/font-woff "access plus 1 year"
    ExpiresByType application/font-woff2 "access plus 1 year"
    ExpiresByType font/ttf "access plus 1 year"
    ExpiresByType font/otf "access plus 1 year"

    # Video / Audio
    ExpiresByType video/mp4 "access plus 1 year"
    ExpiresByType video/webm "access plus 1 year"
    ExpiresByType audio/mpeg "access plus 1 year"

    # Data interchange
    ExpiresByType application/json "access plus 0 seconds"
    ExpiresByType application/xml "access plus 0 seconds"
    ExpiresByType text/xml "access plus 0 seconds"

    # Manifest
    ExpiresByType application/manifest+json "access plus 1 week"
    ExpiresByType text/cache-manifest "access plus 0 seconds"
</IfModule>
```

### Cache-Control Headers

`mod_expires` generates `Cache-Control: max-age=...` automatically, but you can
add more granularity with `mod_headers`:

```apache
<IfModule mod_headers.c>
    # HTML -- no cache (always revalidate)
    <FilesMatch "\.(html|htm)$">
        Header set Cache-Control "no-cache, no-store, must-revalidate"
        Header set Pragma "no-cache"
        Header set Expires 0
    </FilesMatch>

    # Static assets with fingerprinted names -- immutable cache
    <FilesMatch "\.(css|js|woff2|woff|ttf|otf|svg|png|jpe?g|gif|webp|avif|ico|mp4|webm)$">
        Header set Cache-Control "public, max-age=31536000, immutable"
    </FilesMatch>
</IfModule>
```

### ETags Configuration

ETags can cause problems behind load balancers (different servers generate
different ETags for the same file). Disable them if you set explicit
`Cache-Control` / `Expires` headers:

```apache
# Disable ETags entirely
FileETag None

<IfModule mod_headers.c>
    Header unset ETag
</IfModule>
```

If you want ETags (single-server setups), ensure they are based on file content
only:

```apache
FileETag MTime Size
```

### Gzip / Brotli Compression with mod_deflate

```apache
<IfModule mod_deflate.c>
    # Compress text-based content
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE text/javascript
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/json
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/atom+xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE application/x-javascript
    AddOutputFilterByType DEFLATE image/svg+xml
    AddOutputFilterByType DEFLATE font/ttf
    AddOutputFilterByType DEFLATE font/otf
    AddOutputFilterByType DEFLATE application/font-woff
    AddOutputFilterByType DEFLATE application/vnd.ms-fontobject

    # Do not compress already-compressed files
    SetEnvIfNoCase Request_URI \.(?:gif|jpe?g|png|webp|avif|bmp|ico|zip|gz|bz2|rar|7z|mp3|mp4|webm|ogg|flv|mov|avi|wmv|pdf|woff|woff2)$ no-gzip dont-vary

    # Fix browser bugs
    BrowserMatch ^Mozilla/4 gzip-only-text/html
    BrowserMatch ^Mozilla/4\.0[678] no-gzip
    BrowserMatch \bMSIE !no-gzip !gzip-only-text/html

    # Vary header for proxies
    <IfModule mod_headers.c>
        Header append Vary Accept-Encoding
    </IfModule>
</IfModule>
```

**Brotli compression** (Apache 2.4.26+):

```apache
<IfModule mod_brotli.c>
    AddOutputFilterByType BROTLI_COMPRESS text/html
    AddOutputFilterByType BROTLI_COMPRESS text/css
    AddOutputFilterByType BROTLI_COMPRESS text/javascript
    AddOutputFilterByType BROTLI_COMPRESS application/javascript
    AddOutputFilterByType BROTLI_COMPRESS application/json
    AddOutputFilterByType BROTLI_COMPRESS application/xml
    AddOutputFilterByType BROTLI_COMPRESS image/svg+xml
    AddOutputFilterByType BROTLI_COMPRESS font/ttf
    AddOutputFilterByType BROTLI_COMPRESS font/otf
</IfModule>
```

If both `mod_brotli` and `mod_deflate` are loaded, Apache prefers Brotli when
the client supports it (via `Accept-Encoding: br`).

---

## Apache-Specific Features

### .htaccess vs httpd.conf

| Aspect | `.htaccess` | `httpd.conf` / `sites-available/*.conf` |
|---|---|---|
| Scope | Per-directory (and subdirectories) | Server-wide or per-VirtualHost |
| Requires restart | No -- changes take effect immediately | Yes -- `sudo systemctl reload apache2` |
| Performance | Slower -- Apache reads the file on every request in that directory tree | Faster -- parsed once at startup |
| Access | Available to site owners on shared hosting | Requires root / server admin |
| AllowOverride | Must be set to `All` (or specific categories) in the server config | N/A |

**Best practice:** Use `httpd.conf` (or the `sites-available` config) for
production servers you control. Use `.htaccess` on shared hosting or when you
do not have access to the server config.

### mod_deflate (Compression)

See the [Caching Headers](#gzip--brotli-compression-with-mod_deflate) section
above. Enable the module:

```bash
sudo a2enmod deflate
sudo systemctl reload apache2
```

### mod_expires (Caching)

See the [Caching Headers](#mod_expires----set-expiry-by-file-type) section.
Enable the module:

```bash
sudo a2enmod expires
sudo systemctl reload apache2
```

### mod_security (WAF)

ModSecurity is a web application firewall that can block common attacks
(SQL injection, XSS, etc.) at the Apache level.

```bash
# Install
sudo apt install libapache2-mod-security2
sudo a2enmod security2
sudo systemctl reload apache2

# Copy the recommended config
sudo cp /etc/modsecurity/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
```

Then edit `/etc/modsecurity/modsecurity.conf`:

```apache
# Change from DetectionOnly to On to actually block threats
SecRuleEngine On
```

Install the OWASP Core Rule Set (CRS) for comprehensive protection:

```bash
sudo apt install modsecurity-crs
```

**Caution:** ModSecurity with the OWASP CRS can produce false positives. Test
in `DetectionOnly` mode first, review logs, then switch to `On`.

### Disable Directory Indexing

By default Apache shows a file listing if no index file exists. This leaks
your directory structure:

```apache
# Disable globally
Options -Indexes

# Or via mod_autoindex
<IfModule mod_autoindex.c>
    IndexIgnore *
</IfModule>
```

To disable for a specific directory:

```apache
<Directory /var/www/example.com/uploads>
    Options -Indexes
</Directory>
```

### Block Access to Sensitive Files

```apache
# Block dotfiles (.env, .git, .htpasswd, etc.)
<FilesMatch "^\.">
    Require all denied
</FilesMatch>

# Block specific files by name
<FilesMatch "(^\.env|\.sql|\.log|composer\.json|package\.json|package-lock\.json|yarn\.lock)$">
    Require all denied
</FilesMatch>

# Block access to .git directory
RedirectMatch 404 /\.git
```

---

## Common Gotchas

### AllowOverride Must Be Enabled

`.htaccess` files are silently ignored unless the server config allows them.
Ensure the `<Directory>` block for your site includes:

```apache
<Directory /var/www/example.com/public>
    AllowOverride All
    Require all granted
</Directory>
```

Without `AllowOverride All`, your `.htaccess` rewrite rules, headers, and other
directives will have no effect -- and Apache will not log a warning.

After changing this in the server config, reload Apache:

```bash
sudo systemctl reload apache2
```

### mod_rewrite Requires RewriteEngine On

Every `.htaccess` or `<VirtualHost>` section that uses `RewriteRule` must
include `RewriteEngine On`. Forgetting this line is the most common reason
rewrite rules silently fail.

### .htaccess Performance Impact

Apache checks for `.htaccess` in every directory from the filesystem root
down to the requested file's directory -- on every single request. For a file
at `/var/www/site/public/css/style.css`, Apache checks:

1. `/.htaccess`
2. `/var/.htaccess`
3. `/var/www/.htaccess`
4. `/var/www/site/.htaccess`
5. `/var/www/site/public/.htaccess`
6. `/var/www/site/public/css/.htaccess`

On high-traffic sites this adds measurable latency. Move directives into
`httpd.conf` and set `AllowOverride None` for production.

### Multiple .htaccess Files in Subdirectories

Child `.htaccess` files do **not** inherit from parent `.htaccess` files for
most directives. A `.htaccess` in `/blog/` can override rules from the root
`.htaccess`. This is a common source of bugs -- rewrite rules or headers that
work on the homepage but break in subdirectories.

The fix: place all rules in a single root `.htaccess`, or be explicit about
what each subdirectory file handles.

### Order of Rewrite Rules

Rewrite rules are processed top-to-bottom. The `[L]` flag means "last rule" --
stop processing if this rule matches. Without `[L]`, subsequent rules can
modify the URL again, causing unexpected chains.

Common correct ordering:

1. Force HTTPS first
2. Canonical domain (www vs non-www)
3. Trailing slash normalization
4. Application-specific rewrites (clean URLs, front-controller)

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On

    # 1. Force HTTPS
    RewriteCond %{HTTPS} off
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

    # 2. Remove www
    RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
    RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]

    # 3. Remove trailing slash (except for directories)
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteCond %{REQUEST_URI} (.+)/$
    RewriteRule ^ %1 [L,R=301]

    # 4. Front controller (e.g., WordPress, Laravel)
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^ index.php [L]
</IfModule>
```

### Module Not Loaded

If you get a 500 error after adding directives, check the Apache error log:

```bash
sudo tail -20 /var/log/apache2/error.log
```

Common cause: a directive references a module that is not enabled. Enable it:

```bash
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod expires
sudo a2enmod deflate
sudo a2enmod ssl
sudo systemctl reload apache2
```

Always wrap directives in `<IfModule>` guards in `.htaccess` to prevent 500
errors on hosts where you cannot control module loading.

### 301 Redirect Caching

Browsers cache 301 redirects aggressively. While testing redirects, use 302
(temporary) first, verify the behaviour, then switch to 301. If you are stuck
with a cached 301, clear the browser cache or test in an incognito window.

---

## Complete Config Example

A production-ready `.htaccess` combining security headers, caching, redirects,
and compression. Copy and adapt to your site.

```apache
# ============================================================================
# PRODUCTION .htaccess
# Drop this in your DocumentRoot. Requires: mod_rewrite, mod_headers,
# mod_expires, mod_deflate. All sections are wrapped in IfModule guards.
# ============================================================================

# --------------------------------------------------------------------------
# 1. REDIRECTS & REWRITES
# --------------------------------------------------------------------------
<IfModule mod_rewrite.c>
    RewriteEngine On

    # Force HTTPS
    RewriteCond %{HTTPS} off
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

    # Canonical domain: remove www
    RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
    RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]

    # Remove trailing slash (skip real directories)
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteCond %{REQUEST_URI} (.+)/$
    RewriteRule ^ %1 [L,R=301]

    # Front controller -- route everything to index.php (WordPress / Laravel)
    # Remove or adapt this block if you serve static HTML
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^ index.php [L]
</IfModule>

# Custom error pages
ErrorDocument 404 /404.html
ErrorDocument 403 /403.html
ErrorDocument 500 /500.html

# --------------------------------------------------------------------------
# 2. SECURITY HEADERS
# --------------------------------------------------------------------------
<IfModule mod_headers.c>
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    Header always set Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

    # Remove server version info
    Header always unset X-Powered-By
    Header always unset Server
</IfModule>

# Hide Apache version in responses
ServerSignature Off

# --------------------------------------------------------------------------
# 3. CACHING
# --------------------------------------------------------------------------
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresDefault "access plus 1 week"

    # HTML -- always revalidate
    ExpiresByType text/html "access plus 0 seconds"

    # CSS & JS -- long cache (use fingerprinted filenames)
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType text/javascript "access plus 1 year"

    # Images
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/avif "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType image/x-icon "access plus 1 year"

    # Fonts
    ExpiresByType font/woff "access plus 1 year"
    ExpiresByType font/woff2 "access plus 1 year"
    ExpiresByType font/ttf "access plus 1 year"
    ExpiresByType font/otf "access plus 1 year"

    # Data -- no cache
    ExpiresByType application/json "access plus 0 seconds"
    ExpiresByType application/xml "access plus 0 seconds"
</IfModule>

<IfModule mod_headers.c>
    # HTML -- no store
    <FilesMatch "\.(html|htm)$">
        Header set Cache-Control "no-cache, no-store, must-revalidate"
    </FilesMatch>

    # Static assets -- immutable
    <FilesMatch "\.(css|js|woff2|woff|ttf|otf|svg|png|jpe?g|gif|webp|avif|ico)$">
        Header set Cache-Control "public, max-age=31536000, immutable"
    </FilesMatch>
</IfModule>

# Disable ETags (they cause issues behind load balancers)
FileETag None
<IfModule mod_headers.c>
    Header unset ETag
</IfModule>

# --------------------------------------------------------------------------
# 4. COMPRESSION
# --------------------------------------------------------------------------
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE text/javascript
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/json
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE image/svg+xml
    AddOutputFilterByType DEFLATE font/ttf
    AddOutputFilterByType DEFLATE font/otf

    # Skip already-compressed formats
    SetEnvIfNoCase Request_URI \.(?:gif|jpe?g|png|webp|avif|zip|gz|bz2|rar|7z|mp3|mp4|webm|woff|woff2)$ no-gzip dont-vary

    <IfModule mod_headers.c>
        Header append Vary Accept-Encoding
    </IfModule>
</IfModule>

<IfModule mod_brotli.c>
    AddOutputFilterByType BROTLI_COMPRESS text/html
    AddOutputFilterByType BROTLI_COMPRESS text/css
    AddOutputFilterByType BROTLI_COMPRESS text/javascript
    AddOutputFilterByType BROTLI_COMPRESS application/javascript
    AddOutputFilterByType BROTLI_COMPRESS application/json
    AddOutputFilterByType BROTLI_COMPRESS application/xml
    AddOutputFilterByType BROTLI_COMPRESS image/svg+xml
</IfModule>

# --------------------------------------------------------------------------
# 5. SECURITY -- FILE ACCESS
# --------------------------------------------------------------------------
# Disable directory listings
Options -Indexes

# Block dotfiles (.env, .git, .htpasswd, etc.)
<FilesMatch "^\.">
    Require all denied
</FilesMatch>

# Block sensitive files
<FilesMatch "(\.env|\.sql|\.log|composer\.json|composer\.lock|package\.json|package-lock\.json|yarn\.lock)$">
    Require all denied
</FilesMatch>

# Block access to .git directory
RedirectMatch 404 /\.git

# Prevent script execution in upload directories
# Adjust the path to match your upload directory
<IfModule mod_rewrite.c>
    RewriteRule ^uploads/.*\.(php|phtml|php3|php4|php5|pl|py|cgi|shtml)$ - [F,L]
</IfModule>
```

---

## Quick Module Checklist

Before deploying, ensure these modules are enabled on the server:

```bash
sudo a2enmod rewrite   # URL rewriting
sudo a2enmod headers   # Security & cache headers
sudo a2enmod expires   # Expiry-based caching
sudo a2enmod deflate   # Gzip compression
sudo a2enmod ssl       # HTTPS / TLS
sudo a2enmod brotli    # Brotli compression (Apache 2.4.26+, optional)
sudo systemctl reload apache2
```

Verify loaded modules:

```bash
apache2ctl -M | sort
```
