# GitHub Actions - Deploy MkDocs to Your Own Server

This guide explains how to automatically deploy your MkDocs documentation to your own web server using GitHub Actions.

## Overview

The workflow automatically:
- Builds the MkDocs static site
- Deploys it to your server via rsync over SSH
- Triggers on pushes to `main` branch when documentation files change
- Can be manually triggered via GitHub Actions UI

## Prerequisites

1. **A web server** with SSH access (Linux/Unix)
2. **SSH key pair** for authentication
3. **Web server directory** where docs will be hosted (e.g., `/var/www/html/docs`)

## Setup Instructions

### Step 1: Generate SSH Key Pair

On your local machine or CI server:

```bash
# Generate a new SSH key pair (no passphrase for automation)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key -N ""

# This creates:
# - ~/.ssh/github_deploy_key (private key - keep secret!)
# - ~/.ssh/github_deploy_key.pub (public key - add to server)
```

### Step 2: Configure Your Server

Copy the public key to your server:

```bash
# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy_key.pub user@your-server.com

# Or manually:
cat ~/.ssh/github_deploy_key.pub | ssh user@your-server.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Create the deployment directory:

```bash
# SSH to your server
ssh user@your-server.com

# Create docs directory
sudo mkdir -p /var/www/html/docs
sudo chown $USER:$USER /var/www/html/docs
chmod 755 /var/www/html/docs
```

### Step 3: Add GitHub Secrets

Go to your repository settings: **Settings → Secrets and variables → Actions → New repository secret**

> **⚠️ Important:** Add secrets as **Repository secrets**, NOT Environment secrets!
>
> - ✅ **Repository secrets** - Available to all workflows (what you need)
> - ❌ **Environment secrets** - Only available when using environment protection rules
>
> Path: **Settings → Secrets and variables → Actions → Repository secrets tab → New repository secret**

Add these secrets (**all are required** except DEPLOY_PORT):

| Secret Name | Value | Example | Required |
|------------|-------|---------|----------|
| `DEPLOY_HOST` | Your server hostname or IP | `docs.example.com` or `192.168.1.100` | ✅ Yes |
| `DEPLOY_USER` | SSH username | `deploy` or `www-data` | ✅ Yes |
| `DEPLOY_PATH` | Path on server (must end with `/`) | `/var/www/html/docs/` | ✅ Yes |
| `DEPLOY_PORT` | SSH port | `22` (default) or `2222` | ⚠️ Optional |
| `DEPLOY_KEY` | Private SSH key | Contents of `~/.ssh/github_deploy_key` | ✅ Yes |

> **⚠️ Important Notes:**
> - `DEPLOY_PATH` **must not be empty** and should end with a trailing slash `/`
> - All required secrets must be set before the workflow will run
> - The workflow will fail with a clear error message if any required secret is missing

**Quick Visual Guide:**

```
GitHub Repository
└── Settings
    └── Secrets and variables
        └── Actions
            ├── 🟢 Repository secrets ← Add secrets HERE (correct!)
            └── 🔴 Environment secrets ← NOT here (won't work)
```

#### How to Add DEPLOY_KEY Secret:

```bash
# Display the private key
cat ~/.ssh/github_deploy_key

# Copy the ENTIRE output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# [key content]
# -----END OPENSSH PRIVATE KEY-----
```

Paste this into the `DEPLOY_KEY` secret in GitHub.

### Step 4: Configure Web Server

#### For Apache:

Create/edit Apache config:

```apache
# /etc/apache2/sites-available/docs.conf
<VirtualHost *:80>
    ServerName docs.example.com
    DocumentRoot /var/www/html/docs

    <Directory /var/www/html/docs>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        # Set proper MIME types
        AddType text/html .html
        AddType application/javascript .js
        AddType text/css .css
    </Directory>

    # Cache static assets
    <IfModule mod_expires.c>
        ExpiresActive On
        ExpiresByType image/jpg "access plus 1 year"
        ExpiresByType image/jpeg "access plus 1 year"
        ExpiresByType image/gif "access plus 1 year"
        ExpiresByType image/png "access plus 1 year"
        ExpiresByType text/css "access plus 1 month"
        ExpiresByType application/javascript "access plus 1 month"
        ExpiresByType text/html "access plus 1 hour"
    </IfModule>

    ErrorLog ${APACHE_LOG_DIR}/docs_error.log
    CustomLog ${APACHE_LOG_DIR}/docs_access.log combined
</VirtualHost>
```

Enable the site:

```bash
sudo a2ensite docs
sudo systemctl reload apache2
```

#### For Nginx:

Create Nginx config:

```nginx
# /etc/nginx/sites-available/docs
server {
    listen 80;
    server_name docs.example.com;

    root /var/www/html/docs;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Cache static assets
    location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    access_log /var/log/nginx/docs_access.log;
    error_log /var/log/nginx/docs_error.log;
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/docs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 5: Test the Workflow

#### Option 1: Push a change

```bash
# Make a small change to documentation
echo "Test deployment" >> docs/README.md
git add docs/README.md
git commit -m "Test: Trigger docs deployment"
git push
```

#### Option 2: Manual trigger

1. Go to **Actions** tab in GitHub
2. Click **Deploy Documentation** workflow
3. Click **Run workflow** → **Run workflow**

### Step 6: Verify Deployment

Check the GitHub Actions logs:
1. Go to **Actions** tab
2. Click on the latest workflow run
3. Review the logs for any errors

Visit your documentation:
```
http://docs.example.com
```

## Workflow Triggers

The workflow runs when:

1. **Push to main branch** with changes to:
   - `docs/**` (any documentation file)
   - `README.md`
   - `CONTRIBUTING.md`
   - `CHANGELOG.md`
   - `mkdocs.yml`
   - `requirements-docs.txt`
   - `.github/workflows/deploy-docs.yml`

2. **Manual trigger** via GitHub Actions UI

## Troubleshooting

### Missing or Empty Secrets

**Error:** `The remote_path can not be empty` (See: [GitHub Issue #44](https://github.com/Burnett01/rsync-deployments/issues/44))

This error occurs when the `DEPLOY_PATH` secret is not set or is empty.

**Common Cause:** Secrets added as **Environment secrets** instead of **Repository secrets**!

```bash
# Verify all secrets are configured in GitHub
# Go to: Repository Settings → Secrets and variables → Actions → Repository secrets tab

# Required secrets:
# ✅ DEPLOY_HOST - Server hostname/IP
# ✅ DEPLOY_USER - SSH username
# ✅ DEPLOY_PATH - Target path (must end with /)
# ✅ DEPLOY_KEY  - Private SSH key
# ⚠️ DEPLOY_PORT - SSH port (optional, defaults to 22)
```

The workflow now includes validation that will fail early with a clear error message if any required secret is missing:

```
❌ Error: DEPLOY_PATH secret is not set
```

**Solutions:**

1. **Check secret location:** Ensure secrets are added as **Repository secrets**, NOT Environment secrets
   - ✅ Correct: Settings → Secrets and variables → Actions → **Repository secrets** tab
   - ❌ Wrong: Settings → Secrets and variables → Actions → **Environment secrets** tab

2. **Verify secrets exist:** Go to Repository secrets and confirm all required secrets are listed

3. **Check secret values:** Ensure `DEPLOY_PATH` ends with `/` (e.g., `/var/www/html/docs/`)

### SSH Connection Issues

**Error:** `Permission denied (publickey)`

```bash
# Verify the public key is on the server
ssh user@server "cat ~/.ssh/authorized_keys"

# Test SSH connection manually
ssh -i ~/.ssh/github_deploy_key user@server

# Check SSH permissions on server
ssh user@server "chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

### Deployment Path Issues

**Error:** `rsync: failed to set permissions on "/path": Operation not permitted`

```bash
# SSH to server and fix permissions
ssh user@server
sudo chown -R $USER:$USER /var/www/html/docs
chmod 755 /var/www/html/docs
```

### Build Failures

**Error:** `mkdocs build` fails

```bash
# Test build locally
mkdocs build --verbose

# Check requirements-docs.txt is up to date
pip install -r requirements-docs.txt
```

## Security Best Practices

1. **Use dedicated SSH key** - Don't reuse personal keys
2. **Restrict key permissions** - Public key only needs read access
3. **Use non-root user** - Deploy as dedicated user (e.g., `deploy` or `www-data`)
4. **Rotate keys regularly** - Update SSH keys every 6-12 months
5. **Monitor deployments** - Review GitHub Actions logs regularly

## Advanced Configuration

### Deploy to Multiple Servers

Modify workflow to deploy to staging and production:

```yaml
jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      # ... build steps ...
      - name: Deploy to staging
        uses: burnett01/rsync-deployments@6.0.0
        with:
          switches: -avz --delete
          path: site/
          remote_path: ${{ secrets.STAGING_PATH }}
          remote_host: ${{ secrets.STAGING_HOST }}
          remote_user: ${{ secrets.STAGING_USER }}
          remote_key: ${{ secrets.STAGING_KEY }}

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      # ... same as staging but with PROD secrets ...
```

### Add Deployment Notifications

Add Slack/Discord notifications:

```yaml
      - name: Notify on success
        if: success()
        uses: 8398a7/action-slack@v3
        with:
          status: custom
          custom_payload: |
            {
              text: "📚 Documentation deployed successfully!",
              color: 'good'
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

### Enable HTTPS with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-apache  # For Apache
sudo apt install certbot python3-certbot-nginx   # For Nginx

# Get certificate
sudo certbot --apache -d docs.example.com       # For Apache
sudo certbot --nginx -d docs.example.com        # For Nginx

# Auto-renewal is configured automatically
```

## Cost Comparison

| Hosting Option | Cost | Pros | Cons |
|---------------|------|------|------|
| **Your Server** | Variable | Full control, private docs, custom domain | Server maintenance |
| **GitHub Pages** | Free | Zero setup, automatic | Public repos only (or paid) |
| **Netlify** | Free tier | Easy setup, CDN | Limited build minutes |
| **Read the Docs** | Free | Built for docs | Public only (free tier) |

## Monitoring

### Check Deployment Status

```bash
# View GitHub Actions logs
gh run list --workflow=deploy-docs.yml

# View latest run
gh run view --web
```

### Monitor Server

```bash
# Check disk usage
ssh user@server "df -h /var/www/html/docs"

# View access logs
ssh user@server "tail -f /var/log/apache2/docs_access.log"  # Apache
ssh user@server "tail -f /var/log/nginx/docs_access.log"    # Nginx

# Check deployment directory
ssh user@server "ls -lah /var/www/html/docs"
```

## Rollback

If deployment breaks something:

```bash
# SSH to server
ssh user@server

# View recent deployments (rsync doesn't keep history by default)
# You'll need to restore from backup or redeploy an older commit

# Quick fix: Deploy specific commit
git checkout <previous-commit-sha>
git push origin HEAD:main --force  # This triggers redeploy
# Then restore main branch
git checkout main
```

For better rollback, consider using `git-restore-mtime` before rsync to preserve file timestamps.

## Alternative: SCP Deployment

If rsync isn't available, use SCP:

```yaml
      - name: Deploy via SCP
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          port: ${{ secrets.DEPLOY_PORT }}
          source: "site/*"
          target: ${{ secrets.DEPLOY_PATH }}
          strip_components: 1
```

## Need Help?

- Check [GitHub Actions documentation](https://docs.github.com/en/actions)
- Review [MkDocs deployment docs](https://www.mkdocs.org/user-guide/deploying-your-docs/)
- See workflow runs in **Actions** tab for detailed logs
