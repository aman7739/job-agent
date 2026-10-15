# Custom Domain & HTTPS Setup Guide for GitHub Pages

This guide outlines how to configure a custom domain, configure DNS records, enforce HTTPS, and deploy the public showcase site using GitHub Pages.

---

## 1. GitHub Pages Configuration

1. In your GitHub repository, navigate to **Settings** &rarr; **Pages**.
2. Under **Build and deployment**:
   - **Source:** Select **GitHub Actions**.
   - The `.github/workflows/pages.yml` workflow will automatically compile the templates via `python site/build.py` and publish the rendered `dist/` directory.

> [!NOTE]
> **Repository Visibility Rule:**  
> GitHub Pages is available for free on public repositories. If your repository is private, GitHub Pages requires a GitHub Pro, Team, or Enterprise plan. If using a personal free plan, either set repository visibility to Public (confirming `.env` and database secrets remain strictly excluded via `.gitignore`), or publish `dist/` to an independent public showcase repository.

---

## 2. DNS Records for Custom Domain

### Option A: Apex Domain (e.g., `jobdigest.dev`)
Add 4 `A` records with your DNS registrar (Cloudflare, Namecheap, GoDaddy, Google Domains, etc.):

| Type | Host / Name | Target IP Value | TTL |
|---|---|---|---|
| `A` | `@` | `185.199.108.153` | Automatic / 300 |
| `A` | `@` | `185.199.109.153` | Automatic / 300 |
| `A` | `@` | `185.199.110.153` | Automatic / 300 |
| `A` | `@` | `185.199.111.153` | Automatic / 300 |

### Option B: Subdomain (e.g., `jobs.yourdomain.com`)
Add a single `CNAME` record:

| Type | Host / Name | Target Value | TTL |
|---|---|---|---|
| `CNAME` | `jobs` | `<your-github-username>.github.io.` | Automatic / 300 |

---

## 3. Enforcing HTTPS & CNAME Configuration

1. In repository **Settings** &rarr; **Pages** &rarr; **Custom domain**:
   - Enter your domain (e.g., `jobdigest.dev`).
   - Click **Save**. GitHub will automatically create a `CNAME` verification check.
2. Check the box **Enforce HTTPS**:
   - GitHub Pages provisions a free TLS/SSL certificate via Let's Encrypt.
   - Initial certificate provisioning typically takes between 5 to 30 minutes. Once provisioned, HTTP requests are automatically redirected to HTTPS (301 Permanent Redirect).

---

## 4. Default GitHub Pages URL (Alternative)

If you do not register a custom domain, the showcase site is immediately available at:
```
https://<your-github-username>.github.io/<repository-name>/
```
In this scenario, configure `SITE_BASE_URL` in `.github/workflows/pages.yml` or repository variables to ensure canonical URLs, sitemaps, and OpenGraph images resolve to your GitHub Pages subdomain.

---

## 5. Verification Checklist

- [x] `https://<domain>/` loads the showcase homepage with valid TLS certificate.
- [x] `https://<domain>/sitemap.xml` resolves and returns valid XML with Sitemaps 0.9 protocol.
- [x] `https://<domain>/robots.txt` resolves and points to the sitemap.
- [x] `https://<domain>/llms.txt` resolves and provides AI search documentation.
- [x] `https://<domain>/non-existent-path` correctly serves the custom `404.html` page.
