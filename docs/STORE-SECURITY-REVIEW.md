# Database Store Security & Correctness Review

**Date:** February 27, 2026  
**Scope:** All files in `src/akili/store/`  
**Reviewer:** Automated Security Audit

---

## Executive Summary

This review identified **1 CRITICAL**, **3 HIGH**, **5 MEDIUM**, and **2 LOW** severity issues across the database store implementations. The most critical issue is a SQL injection vulnerability in PostgreSQL table name handling. Transaction safety, connection management, and error handling also require attention.

---

## CRITICAL Issues

### 1. SQL Injection Vulnerability in `postgres.py:409`
**File:** `src/akili/store/postgres.py`  
**Line:** 409  
**Severity:** CRITICAL  
**Issue:** Table name is interpolated using f-string instead of being validated/whitelisted.

```python
for table in ("units", "bijections", "grids", "ranges", "conditional_units"):
    cur.execute(f"DELETE FROM {table} WHERE doc_id = %s AND org_id = %s", (doc_id, self._org_id))
```

**Risk:** While the table names are currently hardcoded, this pattern is dangerous. If `table` ever comes from user input or external configuration, this becomes a critical SQL injection vector.

**Recommendation:** Use a whitelist validation:
```python
ALLOWED_TABLES = {"units", "bijections", "grids", "ranges", "conditional_units"}
for table in ALLOWED_TABLES:
    cur.execute(f"DELETE FROM {table} WHERE doc_id = %s AND org_id = %s", (doc_id, self._org_id))
```

Or better yet, use psycopg2's identifier quoting:
```python
from psycopg2 import sql
for table in ("units", "bijections", "grids", "ranges", "conditional_units"):
    cur.execute(
        sql.SQL("DELETE FROM {} WHERE doc_id = %s AND org_id = %s").format(sql.Identifier(table)),
        (doc_id, self._org_id)
    )
```

---

## HIGH Severity Issues

### 2. Missing Transaction Wrapping in `repository.py:430-439`
**File:** `src/akili/store/repository.py`  
**Lines:** 430-439  
**Severity:** HIGH  
**Issue:** `delete_document()` performs multiple DELETE operations without explicit transaction control.

```python
def delete_document(self, doc_id: str) -> None:
    """Remove a document and all its canonical objects from the store."""
    with self._conn() as c:
        c.execute("DELETE FROM units WHERE doc_id = ?", (doc_id,))
        c.execute("DELETE FROM bijections WHERE doc_id = ?", (doc_id,))
        c.execute("DELETE FROM grids WHERE doc_id = ?", (doc_id,))
        c.execute("DELETE FROM ranges WHERE doc_id = ?", (doc_id,))
        c.execute("DELETE FROM conditional_units WHERE doc_id = ?", (doc_id,))
        c.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    self._audit("delete_document", doc_id)
```

**Risk:** If any DELETE fails, partial deletion occurs, leaving orphaned records. SQLite auto-commits each statement, so there's no atomicity guarantee.

**Recommendation:** Wrap in explicit transaction:
```python
def delete_document(self, doc_id: str) -> None:
    with self._conn() as c:
        c.execute("BEGIN")
        try:
            c.execute("DELETE FROM units WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM bijections WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM grids WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM ranges WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM conditional_units WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
    self._audit("delete_document", doc_id)
```

### 3. Missing Transaction Wrapping in `postgres.py:405-411`
**File:** `src/akili/store/postgres.py`  
**Lines:** 405-411  
**Severity:** HIGH  
**Issue:** Same issue as #2 - multiple DELETE operations without explicit transaction control.

**Risk:** Partial deletion if any operation fails. While psycopg2 context managers auto-commit on success, explicit transaction control is safer.

**Recommendation:** Wrap in explicit transaction:
```python
def delete_document(self, doc_id: str) -> None:
    with self._conn() as conn:
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                for table in ("units", "bijections", "grids", "ranges", "conditional_units"):
                    cur.execute(f"DELETE FROM {table} WHERE doc_id = %s AND org_id = %s", (doc_id, self._org_id))
                cur.execute("DELETE FROM documents WHERE doc_id = %s AND org_id = %s", (doc_id, self._org_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    self._audit("delete_document", doc_id)
```

### 4. No Transaction Wrapping in Migration Script
**File:** `src/akili/store/migrate.py`  
**Lines:** 32-56  
**Severity:** HIGH  
**Issue:** Migration processes documents sequentially without transaction wrapping per document or overall.

**Risk:** If migration fails partway through, database is left in inconsistent state. No rollback mechanism.

**Recommendation:** Wrap each document migration in a transaction:
```python
for doc_info in docs:
    doc_id = doc_info["doc_id"]
    try:
        with dst._conn() as conn:
            conn.autocommit = False
            try:
                units = src.get_units_by_doc(doc_id)
                bijections = src.get_bijections_by_doc(doc_id)
                grids = src.get_grids_by_doc(doc_id)
                ranges = src.get_ranges_by_doc(doc_id)
                cunits = src.get_conditional_units_by_doc(doc_id)
                
                dst.store_canonical(...)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception as e:
        logger.error("Failed to migrate doc %s: %s", doc_id, e)
        # Continue with next document or abort based on requirements
```

---

## MEDIUM Severity Issues

### 5. Missing Input Validation for `doc_id` and Other Parameters
**File:** Multiple files  
**Severity:** MEDIUM  
**Issue:** No validation that `doc_id`, `org_id`, `canonical_id`, etc. are non-empty, non-None, or within reasonable length limits before database operations.

**Risk:** Empty strings or extremely long strings could cause issues. Malformed IDs could lead to data integrity problems.

**Recommendation:** Add validation:
```python
def _validate_doc_id(self, doc_id: str) -> None:
    if not doc_id or not isinstance(doc_id, str):
        raise ValueError("doc_id must be a non-empty string")
    if len(doc_id) > 255:  # Reasonable limit
        raise ValueError("doc_id exceeds maximum length")
    # Add any other validation rules
```

### 6. PostgreSQL Connection Not Explicitly Closed on Exception
**File:** `src/akili/store/postgres.py`  
**Lines:** 76-77, throughout  
**Severity:** MEDIUM  
**Issue:** While `with self._conn() as conn:` should close connections, psycopg2 connections in a context manager commit on success but may not properly handle all exception scenarios.

**Risk:** Connection leaks under certain error conditions. While Python's context manager should handle this, explicit error handling is safer.

**Recommendation:** Ensure proper exception handling. Current pattern is mostly correct, but verify psycopg2 version compatibility. Consider connection pooling for production.

### 7. SQLite Migration Logic Uses Silent Exception Swallowing
**File:** `src/akili/store/repository.py`  
**Lines:** 74-77  
**Severity:** MEDIUM  
**Issue:** Migration logic silently ignores OperationalError, which could hide other issues.

```python
try:
    c.execute("ALTER TABLE units ADD COLUMN context TEXT")
except sqlite3.OperationalError:
    pass  # column already exists
```

**Risk:** Other OperationalErrors (permissions, locked database, etc.) are silently ignored.

**Recommendation:** Be more specific:
```python
try:
    c.execute("ALTER TABLE units ADD COLUMN context TEXT")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
        pass  # Expected: column already exists
    else:
        raise  # Unexpected error
```

### 8. No Data Validation Before JSON Serialization
**File:** Multiple files  
**Severity:** MEDIUM  
**Issue:** JSON serialization of `origin_json`, `bbox_json`, etc. happens without validation that the data structures are valid.

**Risk:** Invalid Point/BBox objects could cause JSON serialization errors at runtime, or worse, corrupt data if exceptions are caught.

**Recommendation:** Add validation before serialization:
```python
def _point_to_json(p: Point) -> str:
    if not isinstance(p, Point):
        raise TypeError(f"Expected Point, got {type(p)}")
    if not isinstance(p.x, (int, float)) or not isinstance(p.y, (int, float)):
        raise ValueError("Point coordinates must be numeric")
    return json.dumps({"x": p.x, "y": p.y})
```

### 9. JSON Deserialization Errors Not Handled Gracefully
**File:** `repository.py`, `postgres.py`  
**Lines:** Multiple (e.g., `repository.py:28`, `repository.py:335`, `postgres.py:42`, `postgres.py:322`)  
**Severity:** MEDIUM  
**Issue:** `json.loads()` calls throughout the codebase don't handle `json.JSONDecodeError` exceptions.

**Risk:** If database contains corrupted JSON data, `json.loads()` will raise `JSONDecodeError`, causing unhandled exceptions and potential application crashes.

**Example:**
```python
def _json_to_point(s: str) -> Point:
    d = json.loads(s)  # No error handling
    return Point(x=d["x"], y=d["y"])
```

**Recommendation:** Add error handling:
```python
def _json_to_point(s: str) -> Point:
    try:
        d = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in origin_json: {e}") from e
    if not isinstance(d, dict) or "x" not in d or "y" not in d:
        raise ValueError("Invalid Point JSON structure")
    return Point(x=d["x"], y=d["y"])
```

---

## LOW Severity Issues

### 10. Credential Handling in DSN Construction
**File:** `src/akili/store/postgres.py`  
**Lines:** 53-63  
**Severity:** LOW  
**Issue:** Password is included in DSN string, which could be logged or exposed in error messages.

**Risk:** If DSN is logged or included in exception messages, credentials could be exposed.

**Recommendation:** Use connection parameters instead of DSN string when possible, or ensure logging excludes DSN:
```python
def _conn(self):
    # Parse DSN but don't log it
    return psycopg2.connect(self._dsn)
```

Also ensure logging configuration excludes sensitive environment variables.

### 11. Missing Foreign Key Constraint Enforcement Check
**File:** `src/akili/store/repository.py`  
**Lines:** 70, 90, 103, 120, 137  
**Severity:** LOW  
**Issue:** Foreign key constraints are defined but SQLite may have foreign keys disabled by default.

**Risk:** Foreign key constraints may not be enforced, allowing orphaned records.

**Recommendation:** Enable foreign key enforcement:
```python
def _init_schema(self) -> None:
    with self._conn() as c:
        c.execute("PRAGMA foreign_keys = ON")  # Enable FK enforcement
        c.executescript("""
            # ... rest of schema
        """)
```

---

## Positive Findings

✅ **Good:** All user-provided data uses parameterized queries (`?` for SQLite, `%s` for PostgreSQL)  
✅ **Good:** Connection context managers (`with`) are used consistently  
✅ **Good:** Multi-tenant isolation via `org_id` in PostgreSQL implementation  
✅ **Good:** Audit logging is implemented  
✅ **Good:** Schema initialization is idempotent (`CREATE TABLE IF NOT EXISTS`)

---

## Recommendations Summary

1. **CRITICAL:** Fix SQL injection vulnerability in `postgres.py:409` using whitelist or `sql.Identifier()`
2. **HIGH:** Add explicit transaction wrapping for multi-statement operations
3. **HIGH:** Add transaction control to migration script
4. **MEDIUM:** Add input validation for all database parameters
5. **MEDIUM:** Improve error handling in migration logic
6. **MEDIUM:** Add data validation before JSON serialization
7. **MEDIUM:** Add error handling for JSON deserialization
8. **LOW:** Review credential handling and logging
9. **LOW:** Enable foreign key enforcement in SQLite

---

## Testing Recommendations

1. Test `delete_document()` with partial failures to verify transaction rollback
2. Test migration script with corrupted source data
3. Test with malicious input (SQL injection attempts, extremely long strings)
4. Test connection handling under high concurrency
5. Test foreign key constraint enforcement

---

**End of Report**
