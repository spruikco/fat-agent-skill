# AWS — Platform Fix Reference

Quick reference for fixing FAT Agent findings on AWS-hosted sites. AWS offers
multiple hosting paths — S3 + CloudFront (most common for static/JAMstack sites),
Amplify Hosting (managed CI/CD), EC2/Lightsail (self-managed servers). This guide
focuses on **S3 + CloudFront** and **Amplify**, since those are what most static
sites and SPAs land on. If you are on EC2 or Lightsail with Nginx/Apache, see the
server config examples in `references/security-headers.md` instead.

---

## Security Headers (CloudFront)

CloudFront does not pass S3 response headers through by default. You must
configure headers at the CloudFront layer.

### Option 1 — Response Headers Policy (Recommended)

The simplest approach. Create a policy in the CloudFront console or via
CloudFormation and attach it to your distribution's cache behaviour.

**AWS Console:**
1. CloudFront > Policies > Response headers
2. Create custom policy
3. Add each header under "Custom headers" or use the built-in Security headers section
4. Attach the policy to your distribution's cache behaviour

**Response Headers Policy JSON (CloudFormation):**

```yaml
# CloudFormation
SecurityHeadersPolicy:
  Type: AWS::CloudFront::ResponseHeadersPolicy
  Properties:
    ResponseHeadersPolicyConfig:
      Name: security-headers-policy
      SecurityHeadersConfig:
        StrictTransportSecurity:
          AccessControlMaxAgeSec: 31536000
          IncludeSubdomains: true
          Preload: true
          Override: true
        ContentTypeOptions:
          Override: true
        FrameOptions:
          FrameOption: DENY
          Override: true
        ReferrerPolicy:
          ReferrerPolicy: strict-origin-when-cross-origin
          Override: true
      CustomHeadersConfig:
        Items:
          - Header: Permissions-Policy
            Value: "camera=(), microphone=(), geolocation=()"
            Override: true
          - Header: Content-Security-Policy
            Value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
            Override: true
```

**CDK (TypeScript):**

```typescript
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';

const responseHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
  responseHeadersPolicyName: 'security-headers-policy',
  securityHeadersBehavior: {
    strictTransportSecurity: {
      accessControlMaxAge: Duration.seconds(31536000),
      includeSubdomains: true,
      preload: true,
      override: true,
    },
    contentTypeOptions: { override: true },
    frameOptions: {
      frameOption: cloudfront.HeadersFrameOption.DENY,
      override: true,
    },
    referrerPolicy: {
      referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
      override: true,
    },
  },
  customHeadersBehavior: {
    customHeaders: [
      {
        header: 'Permissions-Policy',
        value: 'camera=(), microphone=(), geolocation=()',
        override: true,
      },
    ],
  },
});
```

Then attach it to your distribution's default behaviour:

```typescript
const distribution = new cloudfront.Distribution(this, 'Distribution', {
  defaultBehavior: {
    origin: new origins.S3BucketOrigin(bucket),
    responseHeadersPolicy,
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
  },
});
```

### Option 2 — CloudFront Functions (Lightweight)

Use when you need conditional logic (e.g., different headers per path) but
don't need external network calls. CloudFront Functions run at the edge, are
cheaper than Lambda@Edge, and have sub-millisecond overhead.

```javascript
// cloudfront-function-headers.js
// Associate with: Viewer Response event
function handler(event) {
  var response = event.response;
  var headers = response.headers;

  headers['strict-transport-security'] = {
    value: 'max-age=31536000; includeSubDomains; preload'
  };
  headers['x-content-type-options'] = { value: 'nosniff' };
  headers['x-frame-options'] = { value: 'DENY' };
  headers['referrer-policy'] = { value: 'strict-origin-when-cross-origin' };
  headers['permissions-policy'] = {
    value: 'camera=(), microphone=(), geolocation=()'
  };
  headers['content-security-policy'] = {
    value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
  };

  return response;
}
```

**Deploy via CLI:**

```bash
aws cloudfront create-function \
  --name security-headers \
  --function-config Comment="Add security headers",Runtime=cloudfront-js-2.0 \
  --function-code fileb://cloudfront-function-headers.js

# After testing:
aws cloudfront publish-function \
  --name security-headers \
  --if-match <ETAG>
```

### Option 3 — Lambda@Edge (Advanced)

Use only when you need external API calls, complex logic, or request body
manipulation. Lambda@Edge runs in regional edge caches, has higher latency,
and costs more. Attach to the **Origin Response** event.

```javascript
// lambda-edge-headers.js
exports.handler = async (event) => {
  const response = event.Records[0].cf.response;
  const headers = response.headers;

  headers['strict-transport-security'] = [{
    key: 'Strict-Transport-Security',
    value: 'max-age=31536000; includeSubDomains; preload',
  }];
  headers['x-content-type-options'] = [{
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  }];
  headers['x-frame-options'] = [{
    key: 'X-Frame-Options',
    value: 'DENY',
  }];
  headers['referrer-policy'] = [{
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  }];
  headers['permissions-policy'] = [{
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=()',
  }];

  return response;
};
```

**Important:** Lambda@Edge functions must be deployed in **us-east-1**. They
replicate to edge locations automatically.

---

## Security Headers (Amplify)

### customHttp.yml (Amplify Hosting Gen 1)

Place a `customHttp.yml` file in the root of your repository:

```yaml
customHeaders:
  - pattern: "**/*"
    headers:
      - key: Strict-Transport-Security
        value: "max-age=31536000; includeSubDomains; preload"
      - key: X-Content-Type-Options
        value: "nosniff"
      - key: X-Frame-Options
        value: "DENY"
      - key: Referrer-Policy
        value: "strict-origin-when-cross-origin"
      - key: Permissions-Policy
        value: "camera=(), microphone=(), geolocation=()"
      - key: Content-Security-Policy
        value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
```

### Custom Headers in amplify.yml

You can also define headers inline in `amplify.yml`:

```yaml
version: 1
frontend:
  phases:
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: build
    files:
      - '**/*'
  customHeaders:
    - pattern: "**/*"
      headers:
        - key: Strict-Transport-Security
          value: "max-age=31536000; includeSubDomains; preload"
        - key: X-Content-Type-Options
          value: "nosniff"
        - key: X-Frame-Options
          value: "DENY"
        - key: Referrer-Policy
          value: "strict-origin-when-cross-origin"
        - key: Permissions-Policy
          value: "camera=(), microphone=(), geolocation=()"
```

### Amplify Console (Manual)

1. App settings > Custom headers
2. Paste the YAML from above
3. Redeploy (headers update on next deploy, not retroactively)

---

## Redirects & Rewrites

### HTTP to HTTPS — CloudFront Viewer Protocol Policy

The easiest redirect. Set it on the distribution's cache behaviour.

**AWS Console:**
CloudFront > Distribution > Behaviours > Edit > Viewer Protocol Policy >
**Redirect HTTP to HTTPS**

**CloudFormation:**

```yaml
Distribution:
  Type: AWS::CloudFront::Distribution
  Properties:
    DistributionConfig:
      DefaultCacheBehavior:
        ViewerProtocolPolicy: redirect-to-https
        # ...
```

### www to non-www (or reverse) — Route 53 + CloudFront

You need two CloudFront distributions or a CloudFront Function.

**Option A — CloudFront Function redirect:**

```javascript
// www-redirect.js
// Associate with: Viewer Request event
function handler(event) {
  var request = event.request;
  var host = request.headers.host.value;

  if (host.startsWith('www.')) {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: {
          value: 'https://' + host.replace('www.', '') + request.uri
        }
      }
    };
  }

  return request;
}
```

**Option B — S3 redirect bucket (simpler, no CloudFront Function needed):**

1. Create a second S3 bucket named `www.example.com`
2. Enable static website hosting
3. Set redirect: protocol = https, hostname = `example.com`
4. Create a CloudFront distribution pointing to this bucket
5. Route 53 ALIAS record for `www.example.com` pointing to this distribution

### CloudFront Functions for Path Redirects

```javascript
// redirects.js
// Associate with: Viewer Request event
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  var redirects = {
    '/old-page': '/new-page',
    '/blog/old-post': '/blog/new-post',
    '/legacy': '/modern',
  };

  if (redirects[uri]) {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: { value: redirects[uri] }
      }
    };
  }

  return request;
}
```

### S3 Website Hosting Redirect Rules (XML)

If you are using S3 static website hosting (not recommended with CloudFront OAC),
you can set redirects in the bucket's website configuration:

```xml
<RoutingRules>
  <RoutingRule>
    <Condition>
      <KeyPrefixEquals>old-path/</KeyPrefixEquals>
    </Condition>
    <Redirect>
      <Protocol>https</Protocol>
      <HostName>example.com</HostName>
      <ReplaceKeyPrefixWith>new-path/</ReplaceKeyPrefixWith>
      <HttpRedirectCode>301</HttpRedirectCode>
    </Redirect>
  </RoutingRule>
</RoutingRules>
```

### Amplify Redirects

In `amplify.yml` or the Amplify console (Rewrites and redirects):

```yaml
redirects:
  - source: /old-page
    target: /new-page
    status: '301'

  - source: /blog/<*>
    target: /articles/<*>
    status: '301'

  # SPA catch-all — serves index.html for all routes (client-side routing)
  - source: </^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>
    target: /index.html
    status: '200'

  # Trailing slash normalisation
  - source: /<*>/
    target: /<*>
    status: '301'
```

**Important:** Amplify processes redirects top-to-bottom. More specific rules go
first. A `200` status is a **rewrite** (URL stays the same); `301`/`302` is a
visible redirect.

---

## SSL/HTTPS Configuration

### ACM — AWS Certificate Manager

ACM provides free, auto-renewing SSL certificates. Two critical rules:

1. **CloudFront requires the certificate be in us-east-1** regardless of where
   your other resources live
2. **Amplify handles certificates automatically** — no manual ACM setup needed

**Request a certificate (CLI):**

```bash
aws acm request-certificate \
  --domain-name example.com \
  --subject-alternative-names "*.example.com" \
  --validation-method DNS \
  --region us-east-1
```

**Validate via Route 53 (CLI):**

```bash
# Get the CNAME validation records
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/abc-123 \
  --region us-east-1 \
  --query 'Certificate.DomainValidationOptions'

# Create the validation DNS records in Route 53
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "_acme-validation.example.com",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{ "Value": "_validation.acm-validations.aws." }]
      }
    }]
  }'
```

### Attach Certificate to CloudFront

**CloudFormation:**

```yaml
Distribution:
  Type: AWS::CloudFront::Distribution
  Properties:
    DistributionConfig:
      ViewerCertificate:
        AcmCertificateArn: !Ref Certificate
        SslSupportMethod: sni-only
        MinimumProtocolVersion: TLSv1.2_2021
      Aliases:
        - example.com
        - www.example.com
```

### Minimum TLS Protocol Version

Always set `MinimumProtocolVersion` to `TLSv1.2_2021` or newer. Older versions
(TLSv1, TLSv1.1) are insecure and penalised by security scanners.

**AWS Console:**
CloudFront > Distribution > General > Edit > Custom SSL Certificate >
Security Policy > **TLSv1.2_2021 (recommended)**

### Route 53 DNS Configuration

Point your domain to CloudFront using an ALIAS record (not a CNAME at the apex):

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890 \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "example.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z2FDTNDATAQYW2",
          "DNSName": "d111111abcdef8.cloudfront.net",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

**Note:** `Z2FDTNDATAQYW2` is the fixed hosted zone ID for all CloudFront
distributions — it never changes.

---

## Caching Headers

### S3 Metadata for Cache-Control

Set `Cache-Control` headers on S3 objects. This tells both CloudFront and
browsers how long to cache files.

**Per-file (CLI):**

```bash
# HTML — short cache, always revalidate
aws s3 cp index.html s3://my-bucket/index.html \
  --cache-control "public, max-age=0, must-revalidate" \
  --content-type "text/html"

# Hashed assets (JS, CSS) — cache forever
aws s3 cp static/ s3://my-bucket/static/ --recursive \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "*.html"

# Images — cache for 1 week
aws s3 sync images/ s3://my-bucket/images/ \
  --cache-control "public, max-age=604800"
```

**In a deploy script (common pattern):**

```bash
#!/bin/bash
BUCKET="my-site-bucket"
DISTRIBUTION_ID="E1234567890"

# Upload HTML with no-cache
aws s3 sync build/ s3://$BUCKET/ \
  --exclude "static/*" \
  --cache-control "public, max-age=0, must-revalidate"

# Upload hashed static assets with long cache
aws s3 sync build/static/ s3://$BUCKET/static/ \
  --cache-control "public, max-age=31536000, immutable"

# Invalidate HTML files in CloudFront
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/index.html" "/"
```

### CloudFront Cache Policies

Cache policies control what CloudFront uses as cache keys and how long it caches
objects. Use managed policies when possible.

| Policy | Use Case |
|--------|----------|
| `CachingOptimized` (658327ea-...) | Static assets — maximises cache hits |
| `CachingOptimized-for-Uncompressed` | Same but skips Accept-Encoding normalisation |
| `CachingDisabled` (4135ea2d-...) | API routes, dynamic content — never cache |
| `Amplify` | Amplify-managed distributions |

**CloudFormation — separate behaviours for static vs dynamic:**

```yaml
Distribution:
  Type: AWS::CloudFront::Distribution
  Properties:
    DistributionConfig:
      DefaultCacheBehavior:
        CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # CachingOptimized
        ViewerProtocolPolicy: redirect-to-https
        TargetOriginId: S3Origin
      CacheBehaviors:
        - PathPattern: "/api/*"
          CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad  # CachingDisabled
          ViewerProtocolPolicy: redirect-to-https
          TargetOriginId: ApiOrigin
```

### Cache Invalidation

After deploying new content, invalidate the CloudFront cache so users see
updates immediately.

```bash
# Invalidate specific paths
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/index.html" "/about" "/blog/*"

# Nuclear option — invalidate everything
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/*"
```

**Cost:** The first 1,000 invalidation paths per month are free. After that,
$0.005 per path. A wildcard (`/*`) counts as one path.

---

## AWS-Specific Features

### S3 Bucket Policies — CloudFront OAC (Origin Access Control)

Never make your S3 bucket public. Use CloudFront OAC to give only your
CloudFront distribution read access.

**Step 1 — Block all public access on the bucket:**

```json
{
  "BlockPublicAcls": true,
  "IgnorePublicAcls": true,
  "BlockPublicPolicy": true,
  "RestrictPublicBuckets": true
}
```

**Step 2 — Create an OAC:**

```bash
aws cloudfront create-origin-access-control \
  --origin-access-control-config '{
    "Name": "my-site-oac",
    "OriginAccessControlOriginType": "s3",
    "SigningBehavior": "always",
    "SigningProtocol": "sigv4"
  }'
```

**Step 3 — Bucket policy allowing CloudFront OAC:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipal",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::my-site-bucket/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::123456789012:distribution/E1234567890"
        }
      }
    }
  ]
}
```

**Note:** OAC replaces the older OAI (Origin Access Identity). Use OAC for new
setups — it supports SSE-KMS, additional S3 features, and is the AWS-recommended
approach.

### WAF Integration with CloudFront

AWS WAF (Web Application Firewall) attaches directly to CloudFront distributions
to block bots, SQL injection, XSS, and more.

```yaml
# CloudFormation — attach WAF to CloudFront
WebACL:
  Type: AWS::WAFv2::WebACL
  Properties:
    Name: site-protection
    Scope: CLOUDFRONT  # Must be CLOUDFRONT, not REGIONAL
    DefaultAction:
      Allow: {}
    Rules:
      - Name: AWSManagedRulesCommonRuleSet
        Priority: 1
        OverrideAction:
          None: {}
        Statement:
          ManagedRuleGroupStatement:
            VendorName: AWS
            Name: AWSManagedRulesCommonRuleSet
        VisibilityConfig:
          SampledRequestsEnabled: true
          CloudWatchMetricsEnabled: true
          MetricName: CommonRuleSet
      - Name: RateLimitRule
        Priority: 2
        Action:
          Block: {}
        Statement:
          RateBasedStatement:
            Limit: 2000
            AggregateKeyType: IP
        VisibilityConfig:
          SampledRequestsEnabled: true
          CloudWatchMetricsEnabled: true
          MetricName: RateLimit
    VisibilityConfig:
      SampledRequestsEnabled: true
      CloudWatchMetricsEnabled: true
      MetricName: SiteProtection
```

**Important:** WAF WebACLs for CloudFront must be created in **us-east-1**, just
like ACM certificates.

### Amplify CI/CD

Amplify builds and deploys automatically on git push. Key settings:

```yaml
# amplify.yml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: build    # or dist, out, .next — depends on framework
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

**Branch previews:** Amplify creates preview deployments for feature branches
automatically. Enable under App settings > Previews.

### Route 53 Health Checks

Monitor your site's availability and failover to a backup if it goes down:

```bash
aws route53 create-health-check --caller-reference "$(date +%s)" \
  --health-check-config '{
    "Type": "HTTPS",
    "FullyQualifiedDomainName": "example.com",
    "Port": 443,
    "ResourcePath": "/",
    "RequestInterval": 30,
    "FailureThreshold": 3,
    "EnableSNI": true
  }'
```

### CloudWatch Monitoring

Key metrics to watch for CloudFront:

| Metric | Alarm Threshold | Meaning |
|--------|-----------------|---------|
| `4xxErrorRate` | > 5% | Broken links, missing pages |
| `5xxErrorRate` | > 1% | Origin failures |
| `CacheHitRate` | < 80% | Cache misconfiguration |
| `BytesDownloaded` | Spike | Possible abuse or misconfigured assets |

```bash
# Create alarm for 5xx errors
aws cloudwatch put-metric-alarm \
  --alarm-name "CloudFront-5xx-Errors" \
  --namespace "AWS/CloudFront" \
  --metric-name "5xxErrorRate" \
  --dimensions Name=DistributionId,Value=E1234567890 \
  --statistic Average \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:alerts
```

---

## Common Gotchas

### S3 bucket must NOT be public if using CloudFront OAC

If you enable "Block all public access" on S3 (correct) but forget to set up OAC
and the bucket policy, CloudFront will return **403 Access Denied**. You need both
the OAC on the distribution AND the bucket policy granting CloudFront access.

### CloudFront cache invalidation costs money after first 1,000/month

Each path in an invalidation request counts toward the 1,000 free paths. After
that, it's $0.005 per path. Use wildcard invalidations (`/*`) to count as a
single path, or set proper `Cache-Control` headers so you rarely need to
invalidate.

### ACM certificates must be in us-east-1 for CloudFront

Even if your S3 bucket is in `ap-southeast-2`, your CloudFront certificate must
be in `us-east-1`. This catches people every single time. If you see "The
certificate must be in US East (N. Virginia)", this is why.

### S3 website endpoint vs REST endpoint

S3 has two URL formats for static hosting:

| Type | URL Format | Supports Index Documents | Use With OAC |
|------|-----------|-------------------------|--------------|
| Website endpoint | `bucket.s3-website-region.amazonaws.com` | Yes | No |
| REST endpoint | `bucket.s3.region.amazonaws.com` | No | Yes |

**If using CloudFront + OAC** (recommended): use the REST endpoint as origin. You
lose S3's built-in index document routing, so configure CloudFront's Default Root
Object instead.

**If using S3 website hosting** (simpler but less secure): use the website
endpoint as a custom origin (not S3 origin type) in CloudFront. You cannot use
OAC with this setup.

### Default Root Object only works for root, not subdirectories

CloudFront's "Default Root Object" setting (e.g., `index.html`) only works for
the root path (`/`). It does NOT work for `/about/` mapping to `/about/index.html`.

**Fix — CloudFront Function to append index.html:**

```javascript
// uri-rewrite.js
// Associate with: Viewer Request event
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  // If URI ends with '/' append index.html
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }
  // If URI doesn't have a file extension, assume it's a directory
  else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
```

This is one of the most common issues with S3 + CloudFront static sites. Without
this function, any navigation to `/about` or `/about/` returns a 403 or an XML
access-denied error.

### Amplify rewrites vs redirects — different syntax and behaviour

In Amplify, the `status` field determines whether a rule is a redirect or a rewrite:

| Status | Type | Browser URL changes? |
|--------|------|---------------------|
| `200` | Rewrite | No — URL stays the same |
| `301` | Permanent redirect | Yes |
| `302` | Temporary redirect | Yes |
| `404` | Custom 404 | Shows custom page with 404 status |

Common mistake: using `301` for SPA catch-all routes. Use `200` for rewrites
(client-side routing) or your app will redirect every deep link to `/index.html`
in the address bar.

### CloudFront distribution changes are slow

Changes to CloudFront distributions take **5-15 minutes** to propagate globally.
Do not make rapid successive changes thinking the previous one failed. Check
the distribution status in the console — it should say "Deployed" before making
more changes.

---

## Complete Config Examples

### Example 1 — CloudFront Response Headers Policy (AWS CLI JSON)

Full policy covering all FAT Agent security header checks:

```json
{
  "ResponseHeadersPolicyConfig": {
    "Name": "fat-agent-security-headers",
    "Comment": "Security headers recommended by FAT Agent audit",
    "SecurityHeadersConfig": {
      "XSSProtection": {
        "Override": true,
        "Protection": true,
        "ModeBlock": true
      },
      "FrameOptions": {
        "Override": true,
        "FrameOption": "DENY"
      },
      "ReferrerPolicy": {
        "Override": true,
        "ReferrerPolicy": "strict-origin-when-cross-origin"
      },
      "ContentTypeOptions": {
        "Override": true
      },
      "StrictTransportSecurity": {
        "Override": true,
        "IncludeSubdomains": true,
        "Preload": true,
        "AccessControlMaxAgeSec": 31536000
      }
    },
    "CustomHeadersConfig": {
      "Items": [
        {
          "Header": "Permissions-Policy",
          "Value": "camera=(), microphone=(), geolocation=()",
          "Override": true
        },
        {
          "Header": "Content-Security-Policy",
          "Value": "default-src 'self'; script-src 'self' https://www.googletagmanager.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://www.google-analytics.com",
          "Override": true
        }
      ]
    }
  }
}
```

**Create it:**

```bash
aws cloudfront create-response-headers-policy \
  --response-headers-policy-config file://response-headers-policy.json
```

**Attach it to a distribution (update the cache behaviour):**

```bash
# Get the current distribution config
aws cloudfront get-distribution-config --id E1234567890 > dist-config.json

# Edit the JSON: add ResponseHeadersPolicyId to DefaultCacheBehavior
# Then update:
aws cloudfront update-distribution \
  --id E1234567890 \
  --distribution-config file://dist-config-updated.json \
  --if-match <ETAG>
```

### Example 2 — Amplify Complete customHttp.yml

Full configuration for an Amplify-hosted SPA:

```yaml
customHeaders:
  - pattern: "**/*"
    headers:
      - key: Strict-Transport-Security
        value: "max-age=31536000; includeSubDomains; preload"
      - key: X-Content-Type-Options
        value: "nosniff"
      - key: X-Frame-Options
        value: "DENY"
      - key: Referrer-Policy
        value: "strict-origin-when-cross-origin"
      - key: Permissions-Policy
        value: "camera=(), microphone=(), geolocation=()"
      - key: Content-Security-Policy
        value: "default-src 'self'; script-src 'self' https://www.googletagmanager.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://www.google-analytics.com"

  - pattern: "/static/**"
    headers:
      - key: Cache-Control
        value: "public, max-age=31536000, immutable"

  - pattern: "*.html"
    headers:
      - key: Cache-Control
        value: "public, max-age=0, must-revalidate"
```

### Example 3 — Complete amplify.yml with Headers, Redirects, and Build

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: build
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
  customHeaders:
    - pattern: "**/*"
      headers:
        - key: Strict-Transport-Security
          value: "max-age=31536000; includeSubDomains; preload"
        - key: X-Content-Type-Options
          value: "nosniff"
        - key: X-Frame-Options
          value: "DENY"
        - key: Referrer-Policy
          value: "strict-origin-when-cross-origin"
        - key: Permissions-Policy
          value: "camera=(), microphone=(), geolocation=()"
redirects:
  - source: /old-page
    target: /new-page
    status: '301'
  - source: </^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>
    target: /index.html
    status: '200'
```

### Example 4 — CloudFormation Full Stack (S3 + CloudFront + OAC + Headers)

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Static site with S3 + CloudFront, security headers, and OAC

Parameters:
  DomainName:
    Type: String
    Default: example.com
  CertificateArn:
    Type: String
    Description: ACM certificate ARN (must be in us-east-1)

Resources:
  SiteBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref DomainName
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  BucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref SiteBucket
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Sid: AllowCloudFrontOAC
            Effect: Allow
            Principal:
              Service: cloudfront.amazonaws.com
            Action: s3:GetObject
            Resource: !Sub '${SiteBucket.Arn}/*'
            Condition:
              StringEquals:
                AWS:SourceArn: !Sub 'arn:aws:cloudfront::${AWS::AccountId}:distribution/${Distribution}'

  OriginAccessControl:
    Type: AWS::CloudFront::OriginAccessControl
    Properties:
      OriginAccessControlConfig:
        Name: !Sub '${DomainName}-oac'
        OriginAccessControlOriginType: s3
        SigningBehavior: always
        SigningProtocol: sigv4

  SecurityHeadersPolicy:
    Type: AWS::CloudFront::ResponseHeadersPolicy
    Properties:
      ResponseHeadersPolicyConfig:
        Name: !Sub '${DomainName}-security-headers'
        SecurityHeadersConfig:
          StrictTransportSecurity:
            AccessControlMaxAgeSec: 31536000
            IncludeSubdomains: true
            Preload: true
            Override: true
          ContentTypeOptions:
            Override: true
          FrameOptions:
            FrameOption: DENY
            Override: true
          ReferrerPolicy:
            ReferrerPolicy: strict-origin-when-cross-origin
            Override: true
        CustomHeadersConfig:
          Items:
            - Header: Permissions-Policy
              Value: 'camera=(), microphone=(), geolocation=()'
              Override: true

  IndexRewriteFunction:
    Type: AWS::CloudFront::Function
    Properties:
      Name: !Sub '${DomainName}-index-rewrite'
      AutoPublish: true
      FunctionConfig:
        Comment: 'Rewrite directory paths to index.html'
        Runtime: cloudfront-js-2.0
      FunctionCode: |
        function handler(event) {
          var request = event.request;
          var uri = request.uri;
          if (uri.endsWith('/')) {
            request.uri += 'index.html';
          } else if (!uri.includes('.')) {
            request.uri += '/index.html';
          }
          return request;
        }

  Distribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        DefaultRootObject: index.html
        Aliases:
          - !Ref DomainName
        ViewerCertificate:
          AcmCertificateArn: !Ref CertificateArn
          SslSupportMethod: sni-only
          MinimumProtocolVersion: TLSv1.2_2021
        Origins:
          - Id: S3Origin
            DomainName: !GetAtt SiteBucket.RegionalDomainName
            OriginAccessControlId: !GetAtt OriginAccessControl.Id
            S3OriginConfig:
              OriginAccessIdentity: ''
        DefaultCacheBehavior:
          TargetOriginId: S3Origin
          ViewerProtocolPolicy: redirect-to-https
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # CachingOptimized
          ResponseHeadersPolicyId: !Ref SecurityHeadersPolicy
          FunctionAssociations:
            - EventType: viewer-request
              FunctionARN: !GetAtt IndexRewriteFunction.FunctionARN
          Compress: true
        CustomErrorResponses:
          - ErrorCode: 403
            ResponseCode: 404
            ResponsePagePath: /404.html
            ErrorCachingMinTTL: 60
          - ErrorCode: 404
            ResponseCode: 404
            ResponsePagePath: /404.html
            ErrorCachingMinTTL: 60

  DNSRecord:
    Type: AWS::Route53::RecordSet
    Properties:
      HostedZoneName: !Sub '${DomainName}.'
      Name: !Ref DomainName
      Type: A
      AliasTarget:
        HostedZoneId: Z2FDTNDATAQYW2  # CloudFront fixed hosted zone ID
        DNSName: !GetAtt Distribution.DomainName

Outputs:
  DistributionId:
    Value: !Ref Distribution
  DistributionDomainName:
    Value: !GetAtt Distribution.DomainName
  BucketName:
    Value: !Ref SiteBucket
```

---

## Quick Reference — What to Change for Each FAT Finding

| FAT Finding | Where to Fix | Effort |
|-------------|-------------|--------|
| Missing HSTS | Response Headers Policy or CloudFront Function | 5 min |
| Missing X-Content-Type-Options | Response Headers Policy | 5 min |
| Missing X-Frame-Options | Response Headers Policy | 5 min |
| Missing Referrer-Policy | Response Headers Policy | 5 min |
| Missing Permissions-Policy | Response Headers Policy (custom header) | 5 min |
| Missing CSP | Response Headers Policy (custom header) | 30 min+ |
| HTTP not redirecting to HTTPS | Viewer Protocol Policy | 5 min |
| www/non-www not redirecting | CloudFront Function + Route 53 | 30 min |
| No SSL certificate | ACM + CloudFront config | 15 min |
| Weak TLS version | CloudFront security policy | 5 min |
| No caching on static assets | S3 metadata or cache policy | 15 min |
| 403 on subpaths | CloudFront Function (index.html rewrite) | 10 min |
| S3 bucket publicly accessible | Enable Block Public Access + OAC | 30 min |
