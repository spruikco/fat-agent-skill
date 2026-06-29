# Docker / Self-Hosted -- Platform Fix Reference

Configuration reference for fixing issues flagged by FAT Agent on Docker-based,
self-hosted deployments. Covers Nginx reverse proxy, SSL, container security,
secrets management, and logging.

---

## Nginx Reverse Proxy Security Headers

When your app runs behind Nginx as a reverse proxy, set security headers at the
Nginx level rather than in the application. This covers all responses including
static assets and error pages.

```nginx
# /etc/nginx/snippets/security-headers.conf
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-XSS-Protection "0" always;
```

Include it in every `server` block and any `location` block that adds its own
headers (Nginx `add_header` in a `location` replaces all parent-level headers):

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    include snippets/security-headers.conf;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        include snippets/security-headers.conf;  # must re-include
        add_header X-Custom-Header "value" always;
        proxy_pass http://127.0.0.1:3000;
    }
}
```

### Content-Security-Policy

CSP is application-specific. Add it per-site rather than in the shared snippet:

```nginx
server {
    include snippets/security-headers.conf;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'" always;
    # ...
}
```

---

## SSL with Let's Encrypt / Certbot

### Initial setup

```bash
# Install certbot with nginx plugin
apt install certbot python3-certbot-nginx

# Obtain certificate (auto-configures nginx)
certbot --nginx -d example.com -d www.example.com

# Or obtain without modifying nginx (manual install)
certbot certonly --webroot -w /var/www/html -d example.com
```

### Auto-renewal

Certbot installs a systemd timer by default. Verify it is active:

```bash
systemctl status certbot.timer
```

If not present, create one:

```bash
# /etc/systemd/system/certbot-renewal.timer
[Unit]
Description=Certbot renewal timer

[Timer]
OnCalendar=*-*-* 02:30:00
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# /etc/systemd/system/certbot-renewal.service
[Unit]
Description=Certbot renewal

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
```

```bash
systemctl enable --now certbot-renewal.timer
```

### Recommended SSL config

```nginx
# /etc/nginx/snippets/ssl-params.conf
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
resolver 1.1.1.1 8.8.8.8 valid=300s;
resolver_timeout 5s;
```

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    include snippets/ssl-params.conf;
    # ...
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}
```

---

## Docker Compose Health Checks

Health checks let Docker (and orchestrators) know when a container is truly
ready, not just running.

```yaml
services:
  web:
    image: myapp:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

For containers without curl, use wget or a built-in check:

```yaml
# wget-based
healthcheck:
  test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000/health"]
  interval: 30s
  timeout: 5s
  retries: 3

# TCP port check (no HTTP needed)
healthcheck:
  test: ["CMD-SHELL", "nc -z localhost 3000 || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3

# PostgreSQL
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 10s
  timeout: 5s
  retries: 5

# Redis
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 3s
  retries: 5
```

Use `depends_on` with health conditions to order startup:

```yaml
services:
  db:
    image: postgres:16
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    image: myapp:latest
    depends_on:
      db:
        condition: service_healthy
```

---

## Container Restart Policies

Set a restart policy so containers recover from crashes without manual
intervention.

```yaml
services:
  web:
    image: myapp:latest
    restart: unless-stopped   # restarts on crash, respects manual stop

  worker:
    image: myapp-worker:latest
    restart: on-failure       # only restarts on non-zero exit code
    deploy:
      restart_policy:
        condition: on-failure
        max_attempts: 5
        delay: 5s
```

| Policy | Behaviour |
|---|---|
| `no` | Never restart (default) |
| `always` | Always restart, including after daemon restart |
| `unless-stopped` | Like `always` but respects manual `docker stop` |
| `on-failure` | Only restart on non-zero exit code |

**Recommendation:** Use `unless-stopped` for web services and `on-failure` for
one-shot tasks or workers that should not retry indefinitely.

---

## Environment Variable Management

Never bake secrets into the Docker image. Use external env files or Docker
secrets.

### .env file approach

```yaml
# docker-compose.yml
services:
  web:
    image: myapp:latest
    env_file:
      - .env.production
    environment:
      - NODE_ENV=production   # non-secret overrides inline
```

```bash
# .env.production  (never commit this file)
DATABASE_URL=postgres://user:pass@db:5432/myapp
SESSION_SECRET=a-long-random-string
SMTP_PASSWORD=mailgun-api-key
```

```gitignore
# .gitignore
.env*
!.env.example
```

Provide a `.env.example` with placeholder values:

```bash
# .env.example  (committed, no real secrets)
DATABASE_URL=postgres://user:password@db:5432/myapp
SESSION_SECRET=change-me
SMTP_PASSWORD=change-me
```

### Docker secrets (Swarm or Compose v2.22+)

```yaml
services:
  web:
    image: myapp:latest
    secrets:
      - db_password
      - session_secret
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
  session_secret:
    file: ./secrets/session_secret.txt
```

The app reads `/run/secrets/db_password` at runtime. Many database images
support `*_FILE` env vars natively (Postgres, MySQL, etc).

---

## Rate Limiting at Nginx Level

Protect against abuse before requests reach your application.

```nginx
# Define rate limit zones in http block
http {
    # 10 requests per second per IP
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;

    # Stricter limit for auth endpoints
    limit_req_zone $binary_remote_addr zone=auth:10m rate=3r/s;

    # API rate limit
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
}
```

```nginx
server {
    # General rate limit with small burst
    location / {
        limit_req zone=general burst=20 nodelay;
        proxy_pass http://127.0.0.1:3000;
    }

    # Strict limit on login/register
    location /auth/ {
        limit_req zone=auth burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:3000;
    }

    # API with higher burst allowance
    location /api/ {
        limit_req zone=api burst=50 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:3000;
    }
}
```

Custom 429 error page:

```nginx
error_page 429 /429.html;
location = /429.html {
    internal;
    default_type text/html;
    return 429 '<html><body><h1>429 Too Many Requests</h1><p>Please slow down.</p></body></html>';
}
```

---

## Logging Best Practices

### Log to stdout/stderr

Docker captures stdout and stderr automatically. Do not write to log files
inside the container.

```dockerfile
# Redirect app logs to stdout/stderr
CMD ["node", "server.js"]
# node already logs to stdout by default
```

For apps that insist on file logging, symlink to stdout:

```dockerfile
RUN ln -sf /dev/stdout /var/log/app/access.log \
    && ln -sf /dev/stderr /var/log/app/error.log
```

### Log rotation with Docker daemon

Configure the Docker daemon to limit log size:

```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Or per-service in docker-compose:

```yaml
services:
  web:
    image: myapp:latest
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### Nginx log rotation

If Nginx runs on the host, use logrotate:

```bash
# /etc/logrotate.d/nginx
/var/log/nginx/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
```

---

## Dockerfile Security

### Use a non-root user

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/false appuser

COPY --from=build --chown=appuser:appuser /app .

USER appuser
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

### Use minimal base images

| Base Image | Size | Use Case |
|---|---|---|
| `node:20-slim` | ~200MB | Node.js apps (good default) |
| `node:20-alpine` | ~130MB | Smaller, but musl libc can cause issues |
| `gcr.io/distroless/nodejs20` | ~130MB | No shell, most secure |
| `python:3.12-slim` | ~150MB | Python apps |
| `golang:1.22` + scratch | ~10MB | Go apps (compile then copy binary) |

### .dockerignore

Always include a `.dockerignore` to keep the build context small and avoid
leaking secrets:

```dockerignore
.git
.gitignore
node_modules
npm-debug.log
.env*
.env.example
docker-compose*.yml
Dockerfile
README.md
.claude
.vscode
coverage
tests
__tests__
*.md
```

### Avoid running as root summary

```dockerfile
# Bad -- runs as root by default
FROM node:20
COPY . .
CMD ["node", "server.js"]

# Good -- explicit non-root user
FROM node:20-slim
RUN useradd -r -s /bin/false appuser
COPY --chown=appuser:appuser . .
USER appuser
CMD ["node", "server.js"]
```

---

## Quick Checklist

| Issue | Fix |
|---|---|
| Missing security headers | Add `snippets/security-headers.conf`, include in all server/location blocks |
| No SSL / expired cert | Install certbot, enable auto-renewal timer |
| Weak TLS config | Use `ssl-params.conf` snippet with TLSv1.2+ only |
| No HTTP-to-HTTPS redirect | Add port 80 server block with `return 301` |
| No health checks | Add `healthcheck` to docker-compose services |
| No restart policy | Set `restart: unless-stopped` |
| Secrets in Docker image | Use `env_file` or Docker secrets, never `COPY .env` |
| No `.env.example` | Create one with placeholder values, commit it |
| No rate limiting | Add `limit_req_zone` and `limit_req` in Nginx |
| Logs filling disk | Set `max-size`/`max-file` in daemon.json or per-service |
| Container runs as root | Add `USER appuser` in Dockerfile |
| Large Docker image | Use `-slim` or `-alpine` base, multi-stage builds |
| No `.dockerignore` | Create one excluding `.git`, `node_modules`, `.env*`, tests |
