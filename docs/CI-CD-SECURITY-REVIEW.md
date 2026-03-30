# CI/CD, Docker, and Configuration Security Review

**Date:** 2026-02-27  
**Scope:** CI/CD pipelines, Docker configurations, and configuration files  
**Reviewer:** Security Audit

---

## Executive Summary

This review identified **2 CRITICAL**, **5 HIGH**, **8 MEDIUM**, and **6 LOW** severity security issues across CI/CD workflows, Docker configurations, dependency management, and configuration files.

**Key Findings:**
- Database file (`akili.db`) is tracked in git (CRITICAL)
- Docker containers run as root (HIGH)
- Unpinned dependency versions in multiple files (HIGH)
- Missing security hardening in Dockerfiles (MEDIUM)
- Incomplete `.gitignore` patterns (MEDIUM)
- CI/CD workflow security improvements needed (MEDIUM)

---

## CRITICAL SEVERITY ISSUES

### CRITICAL-1: Database File Tracked in Git
**File:** `akili.db` (root directory)  
**Lines:** N/A (entire file)  
**Issue:** The SQLite database file `akili.db` is tracked in git repository.

**Risk:** 
- Database may contain sensitive data (document metadata, extracted facts, user corrections)
- Database file could expose internal structure and data
- If database contains any PII or sensitive technical information, it's publicly accessible
- Database corruption could affect all developers

**Evidence:**
```bash
$ git ls-files | grep akili.db
akili.db
```

**Recommendation:**
1. **Immediately remove from git tracking:**
   ```bash
   git rm --cached akili.db
   echo "*.db" >> .gitignore
   git commit -m "Remove database file from git tracking"
   ```
2. **Add to `.gitignore`:** Ensure `*.db` pattern is present
3. **Review git history:** Check if sensitive data was committed:
   ```bash
   git log --all --full-history -- akili.db
   ```
4. **Consider git filter-branch or BFG Repo-Cleaner** if sensitive data was committed

**Severity:** CRITICAL

---

### CRITICAL-2: Hardcoded Dummy API Key in CI Workflow
**File:** `.github/workflows/ci.yml`  
**Lines:** 50-51  
**Issue:** Hardcoded dummy API key value in CI environment variables.

```yaml
env:
  GOOGLE_API_KEY: dummy
```

**Risk:**
- While "dummy" is not a real key, hardcoding any value sets a bad precedent
- If developers copy this pattern elsewhere, they might accidentally commit real keys
- No validation that tests fail gracefully when API key is invalid

**Recommendation:**
1. **Use GitHub Secrets** (even for test values):
   ```yaml
   env:
     GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY_TEST || 'dummy' }}
   ```
2. **Or use empty string** and ensure code handles missing keys gracefully:
   ```yaml
   env:
     GOOGLE_API_KEY: ""
   ```
3. **Add validation** in test setup to ensure tests don't accidentally use production keys

**Severity:** CRITICAL (due to pattern risk)

---

## HIGH SEVERITY ISSUES

### HIGH-1: Docker Containers Run as Root
**File:** `Dockerfile` (root), `frontend/Dockerfile`  
**Lines:** 
- Root Dockerfile: No USER directive (runs as root)
- Frontend Dockerfile: No USER directive (runs as root)

**Issue:** Both Dockerfiles run containers as root user, violating principle of least privilege.

**Risk:**
- If container is compromised, attacker has root access
- Any vulnerability in application code could lead to container escape
- File permissions issues when mounting volumes
- Compliance violations (many security standards require non-root containers)

**Current State:**
```dockerfile
# Root Dockerfile - runs as root
FROM python:3.11-slim
# ... no USER directive

# Frontend Dockerfile - runs as root  
FROM node:20-alpine
# ... no USER directive
```

**Recommendation:**
1. **Create non-root user** in both Dockerfiles:
   ```dockerfile
   # Root Dockerfile
   FROM python:3.11-slim
   
   RUN groupadd -r akili && useradd -r -g akili akili
   
   # ... install dependencies ...
   
   USER akili
   EXPOSE 8000
   CMD ["akili-serve"]
   ```

   ```dockerfile
   # Frontend Dockerfile
   FROM node:20-alpine
   
   RUN addgroup -g 1001 -S nodejs && \
       adduser -S akili -u 1001
   
   # ... copy files ...
   
   USER akili
   EXPOSE 3000
   CMD ["npm", "run", "dev"]
   ```

2. **Ensure volume permissions** work correctly with non-root user
3. **Test thoroughly** to ensure application works with non-root user

**Severity:** HIGH

---

### HIGH-2: Unpinned Docker Base Image Versions
**File:** `Dockerfile`, `frontend/Dockerfile`  
**Lines:**
- Root Dockerfile: Line 2 (`python:3.11-slim`)
- Frontend Dockerfile: Line 3 (`node:20-alpine`)

**Issue:** Base images use tags without specific digests, making builds non-deterministic and vulnerable to supply chain attacks.

**Risk:**
- Base image could be updated with malicious code
- Builds are not reproducible
- Security patches could introduce breaking changes
- Supply chain attacks via compromised base images

**Current State:**
```dockerfile
FROM python:3.11-slim  # Uses latest 3.11-slim tag
FROM node:20-alpine     # Uses latest 20-alpine tag
```

**Recommendation:**
1. **Pin to specific digest:**
   ```dockerfile
   FROM python:3.11-slim@sha256:<digest>
   FROM node:20-alpine@sha256:<digest>
   ```
2. **Use Dependabot** to update digests (already configured for github-actions)
3. **Consider multi-stage builds** to reduce attack surface

**Severity:** HIGH

---

### HIGH-3: Unpinned Python Dependencies
**File:** `pyproject.toml`, `requirements.txt`  
**Lines:** 
- `pyproject.toml`: Lines 23-30 (all dependencies use `>=` without upper bounds)
- `requirements.txt`: Lines 2-8 (all dependencies use `>=`)

**Issue:** All Python dependencies use minimum version constraints (`>=`) without upper bounds or exact versions.

**Risk:**
- Breaking changes in dependency updates could break application
- Security vulnerabilities in newer versions of dependencies
- Non-reproducible builds across environments
- Difficult to track which versions are actually used

**Examples:**
```toml
dependencies = [
    "pydantic>=2.0",           # Could install 3.0, 4.0, etc.
    "fastapi>=0.100",          # Could install any version >= 0.100
    "google-generativeai>=0.3", # Could install any version >= 0.3
]
```

**Recommendation:**
1. **Use `pip-tools` or `pip-compile`** to generate locked `requirements.txt`:
   ```bash
   pip-compile pyproject.toml
   ```
2. **Pin exact versions** in `requirements.txt`:
   ```txt
   pydantic==2.9.0
   fastapi==0.115.0
   ```
3. **Use upper bounds** in `pyproject.toml`:
   ```toml
   "pydantic>=2.0,<3.0"
   ```
4. **Commit `requirements.txt`** with exact versions
5. **Use Dependabot** (already configured) to update dependencies

**Severity:** HIGH

---

### HIGH-4: Unpinned GitHub Actions Versions
**File:** `.github/workflows/ci.yml`  
**Lines:** 26, 29, 54, 66, 69

**Issue:** GitHub Actions use version tags (`@v4`, `@v5`) instead of commit SHAs, making workflows vulnerable to supply chain attacks.

**Risk:**
- Malicious updates to action repositories could compromise CI/CD
- Actions could be updated with breaking changes
- Supply chain attacks via compromised action repositories

**Current State:**
```yaml
uses: actions/checkout@v4
uses: actions/setup-python@v5
uses: codecov/codecov-action@v4
uses: actions/setup-node@v4
```

**Recommendation:**
1. **Pin to commit SHA:**
   ```yaml
   uses: actions/checkout@8f4b7f84864484a7bf31766abe9204da3cbe65b3  # v4
   uses: actions/setup-python@0a5d5e2c5c9e7c7988ccd7d8e3e3e3e3e3e3e3e3  # v5
   ```
2. **Or use major version** but verify actions are from official repositories
3. **Enable Dependabot** for github-actions (already configured)
4. **Review action updates** before merging Dependabot PRs

**Severity:** HIGH

---

### HIGH-5: Missing .env File Validation in Docker Compose
**File:** `docker-compose.yml`  
**Lines:** 10-11, 27-28, 33

**Issue:** Docker Compose references `.env` file without validation that it exists or contains required variables.

**Risk:**
- Application may start with missing or invalid configuration
- Silent failures if required environment variables are missing
- No validation of secret values before container startup

**Current State:**
```yaml
env_file:
  - .env  # No validation that file exists or has required vars
```

**Recommendation:**
1. **Add validation script** or use `env_file` with validation:
   ```yaml
   environment:
     - GOOGLE_API_KEY=${GOOGLE_API_KEY:?GOOGLE_API_KEY is required}
   ```
2. **Create startup script** that validates required env vars:
   ```bash
   # validate-env.sh
   required_vars=("GOOGLE_API_KEY")
   for var in "${required_vars[@]}"; do
     if [ -z "${!var}" ]; then
       echo "Error: $var is required but not set"
       exit 1
     fi
   done
   ```
3. **Document required variables** clearly in README

**Severity:** HIGH

---

## MEDIUM SEVERITY ISSUES

### MEDIUM-1: Missing Multi-Stage Builds in Dockerfiles
**File:** `Dockerfile`, `frontend/Dockerfile`  
**Lines:** Entire files

**Issue:** Dockerfiles don't use multi-stage builds, including build tools and dependencies in final images.

**Risk:**
- Larger image sizes (increased attack surface)
- Build tools and dev dependencies in production images
- Slower image pulls and deployments

**Recommendation:**
1. **Implement multi-stage builds:**
   ```dockerfile
   # Build stage
   FROM python:3.11-slim as builder
   WORKDIR /build
   COPY pyproject.toml requirements.txt ./
   RUN pip install --user --no-cache-dir -e .
   
   # Runtime stage
   FROM python:3.11-slim
   RUN apt-get update && apt-get install -y --no-install-recommends \
       poppler-utils && rm -rf /var/lib/apt/lists/*
   WORKDIR /app
   COPY --from=builder /root/.local /root/.local
   COPY src/ ./src/
   ENV PATH=/root/.local/bin:$PATH
   EXPOSE 8000
   CMD ["akili-serve"]
   ```

**Severity:** MEDIUM

---

### MEDIUM-2: Incomplete .gitignore Patterns
**File:** `.gitignore`  
**Lines:** Entire file

**Issue:** `.gitignore` is missing several important patterns for security and development.

**Missing Patterns:**
- `*.db` (database files - CRITICAL given akili.db is tracked)
- `*.log` (log files may contain sensitive data)
- `.env.local`, `.env.*.local` (local environment overrides)
- `*.pem`, `*.crt`, `*.key` (certificates and keys - only `*.key` is present)
- `node_modules/` (should be explicit)
- `.DS_Store` (already present, but could add more OS files)
- `dist/`, `build/` (build artifacts)

**Current State:**
```gitignore
# Env / secrets
.env
.env.local
*.key
```

**Recommendation:**
```gitignore
# Database files
*.db
*.sqlite
*.sqlite3

# Environment files
.env
.env.local
.env.*.local
.env.production
.env.development

# Secrets and certificates
*.key
*.pem
*.crt
*.p12
*.pfx
*.jks
secrets/
credentials/

# Logs (may contain sensitive data)
*.log
logs/
*.log.*

# Build artifacts
dist/
build/
*.egg-info/
.eggs/

# Dependencies
node_modules/
__pycache__/
```

**Severity:** MEDIUM

---

### MEDIUM-3: No Security Scanning in CI Pipeline
**File:** `.github/workflows/ci.yml`  
**Lines:** Entire workflow

**Issue:** CI pipeline doesn't include security scanning for dependencies or Docker images.

**Risk:**
- Vulnerable dependencies may be deployed
- Security issues not detected early in development
- No automated security checks

**Recommendation:**
1. **Add dependency scanning:**
   ```yaml
   - name: Run Trivy vulnerability scanner
     uses: aquasecurity/trivy-action@master
     with:
       scan-type: 'fs'
       scan-ref: '.'
       format: 'sarif'
       output: 'trivy-results.sarif'
   
   - name: Upload Trivy results to GitHub Security
     uses: github/codeql-action/upload-sarif@v2
     with:
       sarif_file: 'trivy-results.sarif'
   ```

2. **Add npm audit:**
   ```yaml
   - name: npm audit
     working-directory: frontend
     run: npm audit --audit-level=moderate
   ```

3. **Add pip-audit or safety:**
   ```yaml
   - name: pip audit
     run: |
       pip install pip-audit
       pip-audit --requirement requirements.txt
   ```

**Severity:** MEDIUM

---

### MEDIUM-4: Docker Compose Exposes .env File as Volume
**File:** `docker-compose.yml`  
**Lines:** 32-33

**Issue:** `.env` file is mounted as read-only volume in frontend container, exposing all environment variables.

**Risk:**
- If frontend container is compromised, attacker has access to all env vars
- `.env` file may contain sensitive backend secrets
- No separation between frontend and backend secrets

**Current State:**
```yaml
volumes:
  - ./.env:/.env:ro  # Mounts entire .env file
```

**Recommendation:**
1. **Use environment variables** instead of mounting file:
   ```yaml
   environment:
     - VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY}
     - VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN}
     # ... only VITE_* vars needed by frontend
   ```

2. **Separate frontend and backend secrets:**
   - Create `.env.frontend` with only VITE_* variables
   - Keep backend secrets in `.env` (not mounted to frontend)

**Severity:** MEDIUM

---

### MEDIUM-5: Missing Healthcheck in Frontend Container
**File:** `docker-compose.yml`  
**Lines:** 23-36 (frontend service)

**Issue:** Frontend service doesn't have a healthcheck, making it difficult to detect failures.

**Risk:**
- Container may appear healthy but application may be broken
- No automatic restart on failure
- Difficult to monitor service health

**Recommendation:**
```yaml
frontend:
  build: ./frontend
  healthcheck:
    test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 10s
```

**Severity:** MEDIUM

---

### MEDIUM-6: No Resource Limits in Docker Compose
**File:** `docker-compose.yml`  
**Lines:** Entire file

**Issue:** Docker Compose services don't define resource limits (CPU, memory).

**Risk:**
- Resource exhaustion attacks (DoS)
- One service could consume all available resources
- No protection against runaway processes

**Recommendation:**
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
  
  frontend:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 256M
```

**Severity:** MEDIUM

---

### MEDIUM-7: Firebase Configuration Exposure Risk
**File:** `firebase.json`, `.env.example`  
**Lines:** 
- `firebase.json`: Entire file
- `.env.example`: Lines 39-45

**Issue:** Firebase configuration is stored in version control and example file shows structure.

**Risk:**
- Firebase project structure is exposed
- Example file shows what secrets are needed (reconnaissance)
- `firebase.json` may contain project-specific configuration

**Current State:**
```json
{
  "hosting": {
    "public": "frontend/dist",
    ...
  }
}
```

**Recommendation:**
1. **Review `firebase.json`** - ensure no sensitive data
2. **Use environment variables** for Firebase config where possible
3. **Document** that Firebase config should be reviewed before deployment
4. **Consider** using Firebase CLI to generate config dynamically

**Severity:** MEDIUM (informational exposure)

---

### MEDIUM-8: Missing Input Validation in CI Workflow
**File:** `.github/workflows/ci.yml`  
**Lines:** 48-51

**Issue:** CI workflow doesn't validate that tests actually run or that coverage is meaningful.

**Risk:**
- Tests could be skipped silently
- Coverage threshold could be bypassed
- No validation of test results

**Recommendation:**
1. **Add explicit test result validation:**
   ```yaml
   - name: Validate test results
     run: |
       if [ ! -f coverage.xml ]; then
         echo "Error: Coverage file not generated"
         exit 1
       fi
   ```

2. **Fail on test failures** (already handled by pytest exit code)

**Severity:** MEDIUM

---

## LOW SEVERITY ISSUES

### LOW-1: Missing .dockerignore Files
**File:** Missing `.dockerignore` files  
**Issue:** No `.dockerignore` files to exclude unnecessary files from Docker build context.

**Risk:**
- Larger build context (slower builds)
- Unnecessary files copied into images
- Potential exposure of sensitive files in build context

**Recommendation:**
Create `.dockerignore` in root and `frontend/`:
```
.git
.gitignore
*.md
.env
.env.*
node_modules
__pycache__
*.pyc
.pytest_cache
.coverage
htmlcov
.venv
venv
tests/
docs/
*.db
```

**Severity:** LOW

---

### LOW-2: No Explicit Port Documentation
**File:** `docker-compose.yml`  
**Lines:** 8-9, 25-26

**Issue:** Port mappings are hardcoded without documentation of why these ports were chosen.

**Recommendation:**
Add comments explaining port choices and document in README.

**Severity:** LOW

---

### LOW-3: Missing Build Cache Optimization
**File:** `Dockerfile`, `frontend/Dockerfile`  
**Lines:** Entire files

**Issue:** Dockerfiles don't optimize layer caching for dependencies.

**Recommendation:**
Order COPY commands to maximize cache hits:
```dockerfile
# Copy dependency files first (change less frequently)
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e .

# Copy source code last (changes more frequently)
COPY src/ ./src/
```

**Severity:** LOW

---

### LOW-4: No Explicit Security Headers Configuration
**File:** `vite.config.ts`, `docker-compose.yml`  
**Issue:** No security headers configured for frontend (CSP, HSTS, etc.).

**Recommendation:**
Configure security headers in production deployment (Firebase hosting or reverse proxy).

**Severity:** LOW

---

### LOW-5: Missing CI Workflow Permissions
**File:** `.github/workflows/ci.yml`  
**Lines:** Missing `permissions:` block

**Issue:** Workflow uses default permissions which may be overly permissive.

**Recommendation:**
```yaml
permissions:
  contents: read
  pull-requests: write  # For codecov comments
```

**Severity:** LOW

---

### LOW-6: No Explicit Dependency Update Policy
**File:** `.github/dependabot.yml`  
**Issue:** Dependabot is configured but no explicit policy on when to update dependencies.

**Recommendation:**
Document dependency update policy in CONTRIBUTING.md or SECURITY.md.

**Severity:** LOW

---

## SUMMARY BY CATEGORY

### Secret Management
- ❌ Database file tracked in git (CRITICAL-1)
- ⚠️ Hardcoded dummy API key pattern (CRITICAL-2)
- ⚠️ `.env` file mounted in container (MEDIUM-4)
- ✅ `.env` in `.gitignore` (good)
- ⚠️ Missing `.env.*.local` patterns (MEDIUM-2)

### Docker Security
- ❌ Containers run as root (HIGH-1)
- ❌ Unpinned base images (HIGH-2)
- ⚠️ No multi-stage builds (MEDIUM-1)
- ⚠️ No resource limits (MEDIUM-6)
- ⚠️ Missing healthcheck on frontend (MEDIUM-5)
- ⚠️ No `.dockerignore` files (LOW-1)

### CI/CD Pipeline Security
- ❌ Unpinned GitHub Actions (HIGH-4)
- ⚠️ No security scanning (MEDIUM-3)
- ⚠️ Missing workflow permissions (LOW-5)
- ✅ Uses `npm ci` (good - deterministic installs)
- ✅ Uses `pip install -e` (good)

### Dependency Management
- ❌ Unpinned Python dependencies (HIGH-3)
- ✅ npm dependencies locked via `package-lock.json` (good - but package.json uses `^` ranges)
- ⚠️ npm package.json uses `^` version ranges (acceptable since lockfile exists)
- ✅ Dependabot configured (good)
- ⚠️ No security scanning in CI (MEDIUM-3)

### Configuration Files
- ⚠️ Incomplete `.gitignore` (MEDIUM-2)
- ⚠️ Firebase config in git (MEDIUM-7)
- ⚠️ No `.env` validation (HIGH-5)
- ✅ `.env.example` provided (good)

### Build Configuration
- ⚠️ No build cache optimization (LOW-3)
- ⚠️ Missing security headers config (LOW-4)

---

## RECOMMENDATIONS PRIORITY

### Immediate (This Week)
1. **CRITICAL:** Remove `akili.db` from git tracking and add to `.gitignore`
2. **CRITICAL:** Fix hardcoded API key pattern in CI workflow
3. **HIGH:** Create non-root users in Dockerfiles
4. **HIGH:** Pin Docker base images to digests

### High Priority (This Month)
5. **HIGH:** Pin Python dependencies (use pip-tools)
6. **HIGH:** Pin GitHub Actions to commit SHAs
7. **HIGH:** Add `.env` validation in docker-compose
8. **MEDIUM:** Implement multi-stage Docker builds
9. **MEDIUM:** Complete `.gitignore` patterns
10. **MEDIUM:** Add security scanning to CI pipeline

### Medium Priority (Next Sprint)
11. **MEDIUM:** Separate frontend/backend secrets in docker-compose
12. **MEDIUM:** Add healthcheck to frontend container
13. **MEDIUM:** Add resource limits to docker-compose
14. **LOW:** Create `.dockerignore` files
15. **LOW:** Optimize Docker layer caching

---

## TESTING RECOMMENDATIONS

1. **Test non-root Docker containers** - Ensure application works correctly
2. **Test dependency updates** - Verify pinned versions work correctly
3. **Test security scanning** - Ensure CI security checks catch vulnerabilities
4. **Test `.env` validation** - Verify startup fails gracefully with missing vars
5. **Test resource limits** - Ensure containers respect limits under load

---

## COMPLIANCE NOTES

- **OWASP Top 10:** Addresses A06:2021 – Vulnerable and Outdated Components (dependency pinning)
- **CIS Docker Benchmark:** Addresses multiple controls (non-root, resource limits, image pinning)
- **GitHub Security Best Practices:** Addresses supply chain security (action pinning, dependency scanning)

---

**Review completed:** 2026-02-27  
**Next Review:** After implementing HIGH and CRITICAL priority fixes
