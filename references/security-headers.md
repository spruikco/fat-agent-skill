# Security Headers Reference

Quick reference for the FAT Agent security header audit.

## Required Headers

### Strict-Transport-Security (HSTS)
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```
**Why:** Forces browsers to use HTTPS for all future requests. Without this,
users can be downgraded to HTTP via man-in-the-middle attacks.

**Fix (Netlify `_headers` file):**
```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### X-Content-Type-Options
```
X-Content-Type-Options: nosniff
```
**Why:** Prevents browsers from MIME-sniffing a response away from the declared
content-type, which can lead to XSS attacks.

### X-Frame-Options
```
X-Frame-Options: DENY
```
or
```
X-Frame-Options: SAMEORIGIN
```
**Why:** Prevents your site from being embedded in an iframe on another domain
(clickjacking protection). Use SAMEORIGIN if you need iframes on your own domain.

**Modern alternative:** Use `Content-Security-Policy: frame-ancestors 'none'` or
`frame-ancestors 'self'` instead.

### Referrer-Policy
```
Referrer-Policy: strict-origin-when-cross-origin
```
**Why:** Controls how much referrer information is sent with requests. The
recommended value sends the origin (domain) for cross-origin requests but the
full URL for same-origin requests.

### Permissions-Policy
```
Permissions-Policy: camera=(), microphone=(), geolocation=()
```
**Why:** Restricts which browser features your site can use. Disable features
you don't need to reduce attack surface.

### Content-Security-Policy (CSP)
```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.example.com; style-src 'self' 'unsafe-inline'
```
**Why:** Specifies which sources of content are allowed. This is the single most
effective header for preventing XSS attacks — but also the hardest to configure.

**Note:** CSP is complex and highly site-specific. FAT Agent flags its absence
but doesn't recommend a specific policy without understanding the site's dependencies.

---

## Platform-Specific Implementation

### Netlify

Create a `_headers` file in your publish directory:

```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Or in `netlify.toml`:

```toml
[[headers]]
  for = "/*"
  [headers.values]
    Strict-Transport-Security = "max-age=31536000; includeSubDomains; preload"
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "DENY"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=()"
```

### Vercel

In `vercel.json`:

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains; preload" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

### Cloudflare Pages

In `_headers` file (same format as Netlify):

```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Apache (.htaccess)

```apache
<IfModule mod_headers.c>
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    Header always set Permissions-Policy "camera=(), microphone=(), geolocation=()"
</IfModule>
```

### Nginx

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

### Next.js (next.config.js)

```js
const nextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains; preload' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ];
  },
};
```

### WordPress (functions.php or security plugin)

```php
function add_security_headers() {
    header('Strict-Transport-Security: max-age=31536000; includeSubDomains; preload');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
}
add_action('send_headers', 'add_security_headers');
```

## Scoring

| Header | Present | Missing |
|--------|---------|---------|
| HSTS | ✅ +20 | 🟠 P1 |
| X-Content-Type-Options | ✅ +10 | 🟡 P2 |
| X-Frame-Options / CSP frame-ancestors | ✅ +15 | 🟡 P2 |
| Referrer-Policy | ✅ +10 | 🟡 P2 |
| Permissions-Policy | ✅ +10 | 🟢 P3 |
| Content-Security-Policy | ✅ +35 | 🟠 P1 |
