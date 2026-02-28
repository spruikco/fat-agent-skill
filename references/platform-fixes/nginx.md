# Nginx -- Platform Fix Reference

Configuration reference for fixing issues flagged by FAT Agent on Nginx-hosted
sites. All directives go in your Nginx config (typically
`/etc/nginx/sites-available/example.com` or `/etc/nginx/conf.d/example.conf`).

---

## Security Headers

Add these inside the `server` block. The `always` parameter ensures headers are
sent on ALL response codes (including 4xx and 5xx errors -- without it, Nginx
only adds headers to 2xx and 3xx responses).

```nginx
server {
    # ...

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'" always;
    add_header X-XSS-Protection "0" always;
}
```

**Why `X-XSS-Protection: 0`?** The XSS auditor in older browsers could
actually *introduce* vulnerabilities. Modern browsers have removed it. Setting
it to `0` explicitly disables it. Rely on CSP instead.

### The `add_header` Inheritance Gotcha

This is the single most common Nginx misconfiguration. If you use `add_header`
inside a `location` block, it **completely replaces** all `add_header`
directives from the parent `server` block. Your security headers silently
vanish.

```nginx
# BROKEN -- the location block wipes out all server-level headers
server {
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    location /api/ {
        add_header X-Custom "value" always;
        # X-Content-Type-Options and X-Frame-Options are GONE here
        proxy_pass http://backend;
    }
}
```

**Fix: Use an `include` snippet.** Put your shared headers in a file and
include it wherever you need them.

Create `/etc/nginx/snippets/security-headers.conf`:
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-XSS-Protection "0" always;
```

Then include it in every context that needs headers:
```nginx
server {
    include /etc/nginx/snippets/security-headers.conf;

    location /api/ {
        include /etc/nginx/snippets/security-headers.conf;
        add_header X-Custom "value" always;
        proxy_pass http://backend;
    }
}
```

---

## Redirects & Rewrites

### HTTP to HTTPS Redirect

Use a dedicated server block. Do NOT use `if` statements for this.

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    return 301 https://$host$request_uri;
}
```

### www to non-www (canonical domain)

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    return 301 https://example.com$request_uri;
}
```

### non-www to www (if you prefer www)

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    return 301 https://www.example.com$request_uri;
}
```

### Trailing Slash Consistency

Remove trailing slashes (except for root):
```nginx
rewrite ^(.+)/$ $1 permanent;
```

Add trailing slashes:
```nginx
rewrite ^([^.]*[^/])$ $1/ permanent;
```

Place these inside the main `server` block, before your `location` directives.

### Custom 404 Error Page

```nginx
server {
    error_page 404 /404.html;

    location = /404.html {
        root /var/www/example.com/html;
        internal;  # prevents direct access to /404.html
    }
}
```

### SPA Routing with try_files

For single-page apps (React, Vue, Angular) where the client handles routing:

```nginx
location / {
    root /var/www/example.com/html;
    try_files $uri $uri/ /index.html;
}
```

**How it works:** Nginx tries to serve the literal file (`$uri`), then a
directory (`$uri/`), then falls back to `/index.html` for client-side routing.

**Caution:** This means actual 404s (mistyped asset paths, etc.) will silently
serve `index.html` instead of returning a 404 status. For API routes behind a
reverse proxy, define a separate `location /api/` block above this one so API
404s are returned correctly.

### Location Block Rewrites

Redirect specific old URLs:
```nginx
location = /old-page {
    return 301 /new-page;
}
```

Redirect an entire path prefix:
```nginx
location /blog/old-section/ {
    rewrite ^/blog/old-section/(.*)$ /blog/new-section/$1 permanent;
}
```

Regex-based location:
```nginx
location ~* ^/products/([0-9]+)$ {
    return 301 /shop/item/$1;
}
```

---

## SSL/HTTPS Configuration

### Let's Encrypt with Certbot

Install and run Certbot with the Nginx plugin:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Obtain and install certificate (auto-configures Nginx)
sudo certbot --nginx -d example.com -d www.example.com

# Test auto-renewal
sudo certbot renew --dry-run
```

Certbot automatically sets up a cron job or systemd timer for renewal. Verify:
```bash
sudo systemctl list-timers | grep certbot
```

### SSL Certificate & Key Configuration

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
}
```

**Note:** Use `fullchain.pem` (not `cert.pem`) so the full certificate chain is
sent. Missing intermediates cause trust failures on some devices.

### Modern TLS Protocols

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

**Why `ssl_prefer_server_ciphers off`?** With only modern ciphers listed, the
client is better positioned to choose the fastest cipher for its hardware. This
is the Mozilla "Intermediate" recommendation.

### SSL Session Caching & OCSP Stapling

```nginx
# Session caching reduces TLS handshake overhead for returning visitors
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;

# OCSP stapling -- server fetches certificate revocation status so
# the client doesn't have to, improving TLS handshake speed
ssl_stapling on;
ssl_stapling_verify on;
resolver 1.1.1.1 8.8.8.8 valid=300s;
resolver_timeout 5s;
```

### Diffie-Hellman Parameters

Generate strong DH parameters for key exchange:
```bash
sudo openssl dhparam -out /etc/nginx/dhparam.pem 2048
```

Then reference in config:
```nginx
ssl_dhparam /etc/nginx/dhparam.pem;
```

**Note:** 2048-bit is sufficient and generates in seconds. 4096-bit is stronger
but takes much longer to generate and slightly increases handshake time.

### SSL Snippet File

Store these in `/etc/nginx/snippets/ssl-params.conf` and include them:

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
resolver 1.1.1.1 8.8.8.8 valid=300s;
resolver_timeout 5s;
ssl_dhparam /etc/nginx/dhparam.pem;
```

Usage:
```nginx
server {
    listen 443 ssl http2;
    include /etc/nginx/snippets/ssl-params.conf;
    # ...
}
```

### Mozilla SSL Configuration Generator

For the most up-to-date cipher suites and protocol recommendations, use:
https://ssl-config.mozilla.org/

Select "Nginx" and your target compatibility level (Modern, Intermediate, or
Old). The generator produces a complete, copy-paste config.

---

## Caching Headers

### Expires Directive by File Type

```nginx
# Images -- cache for 1 year (hashed filenames)
location ~* \.(jpg|jpeg|png|gif|ico|svg|webp|avif)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}

# CSS and JS -- cache for 1 year (if using hashed filenames)
location ~* \.(css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}

# Fonts
location ~* \.(woff|woff2|ttf|otf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}

# HTML -- short cache or no cache (content changes)
location ~* \.html$ {
    expires 1h;
    add_header Cache-Control "public, no-cache";
}
```

**Remember the `add_header` gotcha:** Each of these location blocks will lose
your security headers. Include your security headers snippet in every location
block that uses `add_header`:

```nginx
location ~* \.(jpg|jpeg|png|gif|ico|svg|webp|avif)$ {
    include /etc/nginx/snippets/security-headers.conf;
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}
```

### Cache-Control for Dynamic Content

```nginx
# API responses -- no caching
location /api/ {
    add_header Cache-Control "no-store, no-cache, must-revalidate";
    proxy_pass http://backend;
}

# Service worker -- must never be cached
location = /sw.js {
    add_header Cache-Control "no-store";
    expires off;
}

# Manifest and favicons
location ~* \.(json|webmanifest)$ {
    expires 1d;
    add_header Cache-Control "public";
}
```

### Gzip Compression

```nginx
# Enable gzip (usually in http block or server block)
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 256;
gzip_types
    text/plain
    text/css
    text/javascript
    application/javascript
    application/json
    application/xml
    application/xml+rss
    image/svg+xml
    font/woff2;
```

**Notes:**
- `gzip_comp_level 5` is a good balance. Levels 6-9 give diminishing returns
  for increasing CPU cost.
- `gzip_vary on` sends `Vary: Accept-Encoding` so caches store both compressed
  and uncompressed versions.
- Do NOT gzip images (jpeg, png, gif) or already-compressed formats (woff2).
  They gain nothing and waste CPU.
- `gzip_min_length 256` skips tiny responses where gzip overhead exceeds savings.

### Brotli Compression (ngx_brotli module)

Brotli delivers 15-25% better compression than gzip for text assets. It requires
the `ngx_brotli` module (not included in default Nginx).

```bash
# Check if brotli module is available
nginx -V 2>&1 | grep -o brotli
```

```nginx
# Enable Brotli (alongside gzip as fallback)
brotli on;
brotli_comp_level 6;
brotli_types
    text/plain
    text/css
    text/javascript
    application/javascript
    application/json
    application/xml
    image/svg+xml
    font/woff2;
```

If the module is not available, consider pre-compressing static files and
serving them with `brotli_static on` (similar to `gzip_static`).

### Static File Serving Optimization

```nginx
# Enable sendfile for efficient static file delivery
sendfile on;
tcp_nopush on;
tcp_nodelay on;

# Open file cache -- avoids repeated filesystem lookups
open_file_cache max=1000 inactive=20s;
open_file_cache_valid 30s;
open_file_cache_min_uses 2;
open_file_cache_errors on;
```

`sendfile` lets the kernel transfer files directly from disk to network socket,
bypassing userspace. `tcp_nopush` batches headers with the first data chunk,
reducing packet count. These are safe defaults for any static site.

---

## Nginx-Specific Features

### Reverse Proxy Configuration

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:3000/;
    proxy_http_version 1.1;

    # Pass original client information
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support (if needed)
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

**Trailing slash matters on `proxy_pass`:**
- `proxy_pass http://backend/;` (with trailing slash) -- strips the matching
  prefix. Request `/api/users` is forwarded as `/users`.
- `proxy_pass http://backend;` (no trailing slash) -- keeps the full URI.
  Request `/api/users` is forwarded as `/api/users`.

### Upstream Configuration (Load Balancing)

```nginx
upstream backend {
    least_conn;  # or: ip_hash, random, round-robin (default)

    server 127.0.0.1:3000 weight=3;
    server 127.0.0.1:3001;
    server 127.0.0.1:3002 backup;

    keepalive 32;
}

server {
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

### Rate Limiting

```nginx
# Define rate limit zone (in http block)
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;

server {
    # Apply with burst allowance
    location / {
        limit_req zone=general burst=20 nodelay;
    }

    # Strict rate limit on login/auth endpoints
    location /api/auth/ {
        limit_req zone=login burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://backend;
    }
}
```

**Parameters:**
- `zone=name:size` -- shared memory zone. 10m holds ~160,000 IP addresses.
- `rate=10r/s` -- 10 requests per second per IP.
- `burst=20` -- allows bursts up to 20 requests (queued).
- `nodelay` -- burst requests are served immediately rather than queued.
- `limit_req_status 429` -- returns proper 429 Too Many Requests (default is 503).

### Connection Limits

```nginx
# Define connection limit zone (in http block)
limit_conn_zone $binary_remote_addr zone=addr:10m;

server {
    limit_conn addr 100;  # max 100 simultaneous connections per IP
}
```

### Logging Configuration

```nginx
# Custom log format with timing info
log_format main '$remote_addr - $remote_user [$time_local] '
                '"$request" $status $body_bytes_sent '
                '"$http_referer" "$http_user_agent" '
                '$request_time $upstream_response_time';

server {
    access_log /var/log/nginx/example.com.access.log main;
    error_log  /var/log/nginx/example.com.error.log warn;

    # Turn off access logging for static assets to reduce I/O
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|woff2)$ {
        access_log off;
    }
}
```

### Security Best Practices

```nginx
# Hide Nginx version from response headers and error pages
server_tokens off;

# Prevent access to hidden files (.git, .env, .htaccess)
location ~ /\. {
    deny all;
    access_log off;
    log_not_found off;
}

# Block access to sensitive file types
location ~* \.(sql|bak|log|ini|sh|env|git)$ {
    deny all;
}

# Limit request body size (prevents large upload abuse)
client_max_body_size 10m;

# Disable unwanted HTTP methods
if ($request_method !~ ^(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)$) {
    return 405;
}
```

---

## Common Gotchas

### 1. add_header in location blocks replaces ALL parent headers

This is covered in detail in the Security Headers section above, but it bears
repeating. Any `add_header` in a `location` block -- even a single one -- wipes
out every `add_header` from the parent `server` block. Use `include` snippets.

### 2. Always test before reload

```bash
# Test configuration syntax
sudo nginx -t

# Reload only if test passes
sudo nginx -t && sudo systemctl reload nginx
```

Never run `systemctl reload nginx` without `nginx -t` first. A syntax error
will take down your server on reload.

### 3. worker_processes and worker_connections

```nginx
# In the main (top-level) context of nginx.conf
worker_processes auto;  # one worker per CPU core

events {
    worker_connections 1024;  # connections per worker
    multi_accept on;
}
```

**Max simultaneous connections** = `worker_processes` x `worker_connections`.
With `auto` on a 4-core server and 1024 connections, that is 4096 concurrent
connections. Increase `worker_connections` if you expect high traffic. Each
idle keepalive connection consumes ~2.5 KB of memory.

### 4. Buffering settings for proxied responses

```nginx
# Prevent buffering issues with server-sent events or streaming
location /api/events/ {
    proxy_buffering off;
    proxy_cache off;
    proxy_pass http://backend;
}

# For standard proxied content, tune buffer sizes
location /api/ {
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;
    proxy_pass http://backend;
}
```

If users report incomplete responses or timeouts with large JSON payloads,
increase `proxy_buffer_size` and `proxy_buffers`.

### 5. if is Evil (mostly)

Nginx's `if` directive does not work like a programming language `if`. Inside a
`location` block, it creates an implicit nested location, which can cause
unexpected behaviour. Prefer `map`, `try_files`, and separate `server`/
`location` blocks where possible.

```nginx
# BAD -- error-prone and hard to debug
if ($host = www.example.com) {
    return 301 https://example.com$request_uri;
}

# GOOD -- dedicated server block
server {
    server_name www.example.com;
    return 301 https://example.com$request_uri;
}
```

### 6. Permissions and ownership

```bash
# Nginx typically runs as www-data (Debian/Ubuntu) or nginx (RHEL/CentOS)
# Your web root must be readable by this user
sudo chown -R www-data:www-data /var/www/example.com
sudo chmod -R 755 /var/www/example.com
```

### 7. Config file locations

| Distribution | Main config | Sites | Snippets |
|---|---|---|---|
| Debian/Ubuntu | `/etc/nginx/nginx.conf` | `/etc/nginx/sites-available/` + symlink to `sites-enabled/` | `/etc/nginx/snippets/` |
| RHEL/CentOS | `/etc/nginx/nginx.conf` | `/etc/nginx/conf.d/` | `/etc/nginx/conf.d/` |

---

## Complete Config Example

Production-ready config covering security headers, SSL, caching, compression,
and SPA routing.

### /etc/nginx/snippets/security-headers.conf

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-XSS-Protection "0" always;
```

### /etc/nginx/snippets/ssl-params.conf

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;

ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;

ssl_stapling on;
ssl_stapling_verify on;
resolver 1.1.1.1 8.8.8.8 valid=300s;
resolver_timeout 5s;

ssl_dhparam /etc/nginx/dhparam.pem;
```

### /etc/nginx/sites-available/example.com

```nginx
# -------------------------------------------------------------------
# HTTP -> HTTPS redirect
# -------------------------------------------------------------------
server {
    listen 80;
    listen [::]:80;
    server_name example.com www.example.com;

    # Let's Encrypt challenge directory
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://example.com$request_uri;
    }
}

# -------------------------------------------------------------------
# www -> non-www redirect (HTTPS)
# -------------------------------------------------------------------
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    return 301 https://example.com$request_uri;
}

# -------------------------------------------------------------------
# Main server block
# -------------------------------------------------------------------
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name example.com;

    root /var/www/example.com/html;
    index index.html;

    # --- SSL ---
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    include /etc/nginx/snippets/ssl-params.conf;

    # --- Security headers ---
    include /etc/nginx/snippets/security-headers.conf;

    # --- Security hardening ---
    server_tokens off;
    client_max_body_size 10m;

    # Block hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # --- Gzip ---
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 256;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/xml
        image/svg+xml
        font/woff2;

    # --- Static file performance ---
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;

    # --- Logging ---
    access_log /var/log/nginx/example.com.access.log;
    error_log  /var/log/nginx/example.com.error.log warn;

    # --- Static assets with long cache ---
    location ~* \.(jpg|jpeg|png|gif|ico|svg|webp|avif)$ {
        include /etc/nginx/snippets/security-headers.conf;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location ~* \.(css|js)$ {
        include /etc/nginx/snippets/security-headers.conf;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location ~* \.(woff|woff2|ttf|otf|eot)$ {
        include /etc/nginx/snippets/security-headers.conf;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # --- Reverse proxy for API ---
    location /api/ {
        include /etc/nginx/snippets/security-headers.conf;
        add_header Cache-Control "no-store";

        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # --- SPA fallback (must be last) ---
    location / {
        try_files $uri $uri/ /index.html;
    }

    # --- Custom error pages ---
    error_page 404 /404.html;
    location = /404.html {
        internal;
    }

    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        internal;
    }
}
```

### Enable the site and apply

```bash
# Symlink to sites-enabled (Debian/Ubuntu)
sudo ln -s /etc/nginx/sites-available/example.com /etc/nginx/sites-enabled/

# Remove default site if present
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload
sudo nginx -t && sudo systemctl reload nginx
```

### Verify the result

```bash
# Check headers
curl -I https://example.com

# Check SSL grade
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=example.com

# Check security headers
# Visit: https://securityheaders.com/?q=example.com
```
