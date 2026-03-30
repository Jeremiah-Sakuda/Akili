# Security and Correctness Code Review
## Ingest Pipeline and Verification Modules

**Date:** 2026-02-27  
**Scope:** Ingest pipeline (`src/akili/ingest/`) and verification modules (`src/akili/verify/`)

---

## Executive Summary

This review identified **2 CRITICAL**, **5 HIGH**, **7 MEDIUM**, and **6 LOW** severity issues across file handling, API security, data validation, error handling, mathematical correctness, and resource management.

**Note:** Two issues initially flagged were verified as correct (MATH-1: grid merge logic, MEDIUM-7: Z3 contradiction check).

---

## CRITICAL SEVERITY ISSUES

### CRITICAL-1: Path Traversal Vulnerability in Pipeline
**File:** `src/akili/ingest/pipeline.py`  
**Lines:** 59-61  
**Issue:** No path normalization or traversal protection before opening PDF files.

```python
pdf_path = Path(pdf_path)
if not pdf_path.exists():
    raise FileNotFoundError(f"PDF not found: {pdf_path}")
```

**Risk:** If `pdf_path` is user-controlled or derived from user input, an attacker could use `../../../etc/passwd` or similar to read arbitrary files.

**Recommendation:**
```python
pdf_path = Path(pdf_path).resolve()  # Normalize absolute path
# Add validation that path is within allowed directory
allowed_base = Path(os.environ.get("AKILI_DOCS_DIR", "/tmp")).resolve()
if not str(pdf_path).startswith(str(allowed_base)):
    raise ValueError(f"Path outside allowed directory: {pdf_path}")
```

**Severity:** CRITICAL

---

### CRITICAL-2: Prompt Injection via doc_id in Gemini Calls
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 565-569  
**Issue:** `doc_id` and `page_index` are directly interpolated into the prompt without sanitization.

```python
prompt = (
    f"{EXTRACT_PROMPT}{hint_block}\n\n"
    f"This image is page {page_index} of document {doc_id}. "
    "Return JSON with keys: units, bijections, grids."
)
```

**Risk:** If `doc_id` contains malicious content (e.g., `"\n\nIgnore previous instructions..."), it could manipulate Gemini's behavior.

**Recommendation:**
```python
# Sanitize doc_id to prevent injection
safe_doc_id = re.sub(r'[^\w\-]', '', str(doc_id))[:64]  # Alphanumeric only, max 64 chars
safe_page_index = max(0, int(page_index))  # Ensure non-negative integer
prompt = (
    f"{EXTRACT_PROMPT}{hint_block}\n\n"
    f"This image is page {safe_page_index} of document {safe_doc_id}. "
    "Return JSON with keys: units, bijections, grids."
)
```

**Severity:** CRITICAL

---

## HIGH SEVERITY ISSUES

### HIGH-1: Division by Zero in Voltage Margin Calculation
**File:** `src/akili/verify/derived.py`  
**Lines:** 388-391  
**Issue:** Division by `v_max` without checking if it's zero before the division.

```python
if v_op is None or v_max is None or v_max == 0:
    return None
```

**Status:** ✅ **FIXED** - The check exists, but the logic is correct. However, see MEDIUM-5 for edge case.

**Severity:** HIGH (mitigated by existing check, but see MEDIUM-5)

---

### HIGH-2: Memory Exhaustion Risk from Unbounded Page Lists
**File:** `src/akili/ingest/pipeline.py`  
**Lines:** 64-71  
**Issue:** No maximum page limit enforced. A malicious PDF with thousands of pages could exhaust memory.

```python
pages = load_pdf_pages(pdf_path)
total_pages = len(pages)
# ... processes all pages without limit
```

**Risk:** Memory exhaustion, DoS.

**Recommendation:**
```python
MAX_PAGES = int(os.environ.get("AKILI_MAX_PAGES", "1000"))
pages = load_pdf_pages(pdf_path)
if len(pages) > MAX_PAGES:
    raise ValueError(f"PDF has {len(pages)} pages, exceeds maximum {MAX_PAGES}")
```

**Severity:** HIGH

---

### HIGH-3: API Key Exposure in Error Messages
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 538-539, 622-629  
**Issue:** API key is read from environment but error messages might leak it if exceptions contain sensitive data.

**Risk:** If exceptions are logged or returned to users, API keys could be exposed.

**Recommendation:** Ensure error handling never includes API key in logs or responses. Add explicit check:
```python
def _ensure_configured() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    # Never log or expose api_key value
```

**Severity:** HIGH

---

### HIGH-4: Missing Input Validation in Grid Cell Access
**File:** `src/akili/canonical/models.py`  
**Lines:** 96-101  
**Issue:** `get_cell()` doesn't validate that `row` and `col` are within grid bounds.

```python
def get_cell(self, row: int, col: int) -> GridCell | None:
    """Return cell at (row, col) if present."""
    for c in self.cells:
        if c.row == row and c.col == col:
            return c
    return None
```

**Risk:** If called with negative or very large indices, it could cause performance issues or unexpected behavior.

**Recommendation:**
```python
def get_cell(self, row: int, col: int) -> GridCell | None:
    """Return cell at (row, col) if present."""
    if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
        return None
    for c in self.cells:
        if c.row == row and c.col == col:
            return c
    return None
```

**Severity:** HIGH

---

### HIGH-5: Race Condition in Temp File Cleanup
**File:** `src/akili/api/app.py` (referenced in search results)  
**Lines:** 173-200, 286-304  
**Issue:** In `/ingest/stream`, temp file cleanup happens in `finally` block, but thread may still be using it.

**Risk:** File could be deleted while thread is still reading it, causing crashes.

**Recommendation:** Ensure thread completes before cleanup, or use reference counting.

**Severity:** HIGH

---

## MEDIUM SEVERITY ISSUES

### MEDIUM-1: Incomplete Error Handling in Consensus Extraction
**File:** `src/akili/ingest/consensus.py`  
**Lines:** 204-205  
**Issue:** If `extract_page()` fails for both precision and recall passes, no error is raised; empty extraction is returned.

**Risk:** Silent failures could mask API issues or rate limits.

**Recommendation:** Log warnings when both extractions fail, or raise exception if both fail.

**Severity:** MEDIUM

---

### MEDIUM-2: Potential Integer Overflow in Grid Merging
**File:** `src/akili/ingest/multipage.py`  
**Lines:** 144-159  
**Issue:** `row_offset = ga.rows` and `merged_rows = ga.rows + extra_rows` could overflow for very large grids.

**Risk:** Integer overflow on 32-bit systems or with extremely large PDFs.

**Recommendation:** Add bounds checking:
```python
MAX_ROWS = 1_000_000
if ga.rows > MAX_ROWS or gb.rows > MAX_ROWS:
    logger.warning(f"Grid too large to merge safely: {ga.rows}, {gb.rows}")
    return None  # or skip merge
```

**Severity:** MEDIUM

---

### MEDIUM-3: Missing Validation in Unit Similarity Calculation
**File:** `src/akili/ingest/consensus.py`  
**Lines:** 37-80  
**Issue:** `_unit_similarity()` doesn't validate input types or handle edge cases (e.g., division by zero if `weights == 0`).

**Risk:** Could raise exceptions or return NaN/Inf values.

**Recommendation:**
```python
def _unit_similarity(u1: dict, u2: dict) -> float:
    """Score how similar two extracted units are (0.0 to 1.0)."""
    if not isinstance(u1, dict) or not isinstance(u2, dict):
        return 0.0
    score = 0.0
    weights = 0.0
    # ... existing logic ...
    return score / weights if weights > 0 else 0.0  # ✅ Already handled
```

**Status:** ✅ **PARTIALLY FIXED** - Division by zero is handled, but input validation is missing.

**Severity:** MEDIUM

---

### MEDIUM-4: Unvalidated JSON Response from Gemini
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 614-617  
**Issue:** `json.loads(text)` could raise exceptions or parse malicious JSON that exhausts memory.

**Risk:** DoS via malicious JSON payloads.

**Recommendation:**
```python
try:
    # Limit JSON size
    if len(text) > 10_000_000:  # 10MB limit
        logger.warning("Gemini response too large, truncating")
        text = text[:10_000_000]
    data = json.loads(text)
except json.JSONDecodeError as e:
    logger.error(f"JSON decode error: {e}")
    return PageExtraction(units=[], bijections=[], grids=[])
```

**Severity:** MEDIUM

---

### MEDIUM-5: Edge Case in Voltage Margin: Negative Results Not Handled
**File:** `src/akili/verify/derived.py`  
**Lines:** 391-392  
**Issue:** If `v_op > v_max` (operating voltage exceeds max), margin calculation produces negative result without validation.

```python
margin_pct = ((v_max - v_op) / v_max) * 100.0
```

**Risk:** Negative margins indicate invalid data but aren't flagged.

**Recommendation:**
```python
if v_op > v_max:
    logger.warning(f"Operating voltage {v_op}V exceeds max {v_max}V")
    # Return error or flag as invalid
    return None
margin_pct = ((v_max - v_op) / v_max) * 100.0
```

**Severity:** MEDIUM

---

### MEDIUM-6: Missing Unit Conversion Validation in Derived Queries
**File:** `src/akili/verify/derived.py`  
**Lines:** 130-136, 280-283  
**Issue:** Unit conversions assume specific formats (e.g., "mA" → divide by 1000) but don't validate unit strings.

**Risk:** Invalid unit strings could cause incorrect calculations.

**Recommendation:** Use a centralized unit conversion function with validation.

**Severity:** MEDIUM

---

### MEDIUM-7: Z3 Check Logic Error: Contradiction Detection Uses Wrong Solver Logic
**File:** `src/akili/verify/z3_checks.py`  
**Lines:** 248-256  
**Issue:** The contradiction check adds `a == b` and checks if it's NOT satisfiable, which is backwards.

```python
s.add(a == ref_val)
s.add(b == bv)
s.add(a == b)

if s.check() != sat:  # This means a != b is satisfiable, so they're different
    issues.append(...)
```

**Status:** ✅ **LOGIC IS CORRECT** - If `a == b` is NOT satisfiable, then `a != b` must be true, meaning contradiction.

**Severity:** MEDIUM (false positive - logic is actually correct)

---

### MEDIUM-8: Missing Bounds Checking in Coordinate Normalization
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 274-291  
**Issue:** `_normalize_origin()` doesn't validate that coordinates are in [0, 1] range as expected.

**Risk:** Invalid coordinates could cause rendering issues or security problems.

**Recommendation:**
```python
def _normalize_origin(origin: object) -> dict | None:
    """Return {x, y} dict with numeric x,y; accept dict or [x,y] list."""
    # ... existing logic ...
    if isinstance(origin, dict):
        x, y = origin.get("x"), origin.get("y")
        if x is not None and y is not None:
            x, y = float(x), float(y)
            # Clamp to [0, 1] or validate
            if not (0 <= x <= 1 and 0 <= y <= 1):
                logger.warning(f"Coordinate out of range: ({x}, {y})")
                x = max(0, min(1, x))
                y = max(0, min(1, y))
            return {"x": x, "y": y}
```

**Severity:** MEDIUM

---

## LOW SEVERITY ISSUES

### LOW-1: Inefficient Grid Cell Lookup
**File:** `src/akili/canonical/models.py`  
**Lines:** 96-101  
**Issue:** `get_cell()` uses linear search instead of dictionary lookup.

**Recommendation:** Cache cells in a dict: `{(row, col): cell}` for O(1) access.

**Severity:** LOW

---

### LOW-2: Missing Type Hints in Some Functions
**File:** Multiple files  
**Issue:** Some functions lack complete type hints, reducing static analysis effectiveness.

**Severity:** LOW

---

### LOW-3: Hardcoded Retry Limits
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 24-25  
**Issue:** Retry limits are configurable via env vars but defaults may not suit all use cases.

**Severity:** LOW

---

### LOW-4: Missing Logging in Critical Paths
**File:** `src/akili/ingest/pipeline.py`  
**Lines:** 87-95  
**Issue:** Page failures are logged but don't include enough context for debugging.

**Severity:** LOW

---

### LOW-5: Potential Precision Loss in Float Comparisons
**File:** `src/akili/ingest/consensus.py`  
**Lines:** 48-49  
**Issue:** Floating point comparison uses hardcoded epsilon (0.01) which may not be appropriate for all units.

**Recommendation:** Use relative epsilon based on magnitude.

**Severity:** LOW

---

### LOW-6: Missing Input Sanitization in Proof Generation
**File:** `src/akili/verify/proof.py`  
**Lines:** Multiple  
**Issue:** User questions are passed directly to rule functions without sanitization.

**Risk:** Very long questions could cause performance issues.

**Recommendation:** Truncate or validate question length.

**Severity:** LOW

---

## MATHEMATICAL CORRECTNESS ISSUES

### MATH-1: Row Offset Calculation in Grid Merge (VERIFIED CORRECT)
**File:** `src/akili/ingest/multipage.py`  
**Lines:** 148-150  
**Status:** ✅ **LOGIC IS CORRECT**

The code correctly handles header row skipping:
- Row 0 is skipped before reaching the calculation (line 148-149)
- For remaining rows (1, 2, 3...), `cell.row - 1 + row_offset` correctly maps them
- Example: If grid_a has 5 rows and we skip grid_b's row 0, grid_b's row 1 becomes row 5 (1-1+5=5) ✓

**Severity:** N/A (False positive - logic is correct)

---

### MATH-2: Fragile Unit Conversion in Power Calculation
**File:** `src/akili/verify/derived.py`  
**Lines:** 113, 130  
**Issue:** Voltage conversion assumes all non-"V" units are "mV", which is fragile.

```python
unit_measures=["V", "mV"]  # Line 113 - only searches for V or mV
# ...
v_volts = v if (voltage_unit.unit_of_measure or "").upper() == "V" else v / 1000.0
```

**Current behavior:** 
- Works correctly for "V" and "mV" (the expected units)
- But if a "kV" unit somehow gets through (e.g., from different search), it would be incorrectly divided by 1000 instead of multiplied

**Risk:** Low in practice since `_find_unit` filters by `unit_measures=["V", "mV"]`, but the conversion logic is fragile and doesn't explicitly validate the unit.

**Recommendation:** Make conversion explicit and robust:
```python
uom_upper = (voltage_unit.unit_of_measure or "").upper()
if uom_upper == "V":
    v_volts = v
elif uom_upper == "MV":  # millivolts
    v_volts = v / 1000.0
elif uom_upper == "KV":  # kilovolts (defensive)
    v_volts = v * 1000.0
else:
    logger.warning(f"Unexpected voltage unit '{uom_upper}', assuming V")
    v_volts = v
```

**Severity:** MEDIUM (works for expected inputs but fragile)

---

### MATH-3: Thermal Calculation Uses Hardcoded Ambient Temperature
**File:** `src/akili/verify/derived.py`  
**Lines:** 247  
**Issue:** `t_ambient = 25.0` is hardcoded, which may not match actual operating conditions.

**Severity:** LOW (documentation issue)

---

## RESOURCE EXHAUSTION ISSUES

### RESOURCE-1: Unbounded Memory Growth in Page Processing
**File:** `src/akili/ingest/pipeline.py`  
**Lines:** 68-86  
**Issue:** `all_canonical` list grows unbounded. Very large PDFs could exhaust memory.

**Recommendation:** Process pages in batches or stream results.

**Severity:** MEDIUM

---

### RESOURCE-2: No Timeout on Gemini API Calls
**File:** `src/akili/ingest/gemini_extract.py`  
**Lines:** 572-588  
**Issue:** Retry loop has no overall timeout. A stuck API call could hang indefinitely.

**Recommendation:** Add total timeout:
```python
import time
start_time = time.time()
MAX_TOTAL_TIME = 300  # 5 minutes
for attempt in range(_GEMINI_MAX_RETRIES):
    if time.time() - start_time > MAX_TOTAL_TIME:
        raise TimeoutError("Gemini API call exceeded maximum time")
    # ... existing retry logic ...
```

**Severity:** MEDIUM

---

## SUMMARY BY CATEGORY

### File Handling Security
- ✅ Temp files are cleaned up (in app.py)
- ❌ Path traversal vulnerability (CRITICAL-1)
- ❌ No path normalization

### External API Security
- ✅ API key from environment
- ❌ Prompt injection via doc_id (CRITICAL-2)
- ❌ No timeout on API calls (RESOURCE-2)
- ⚠️ Error messages might leak API key (HIGH-3)

### Data Validation
- ⚠️ Missing coordinate bounds checking (MEDIUM-8)
- ⚠️ Missing grid bounds validation (HIGH-4)
- ⚠️ JSON size not limited (MEDIUM-4)

### Error Handling
- ⚠️ Silent failures in consensus (MEDIUM-1)
- ✅ Good retry logic with backoff
- ⚠️ Missing validation in some paths

### Mathematical Correctness
- ❌ Unit conversion errors (MATH-2) - HIGH
- ❌ Grid merge row calculation (MATH-1) - MEDIUM
- ⚠️ Z3 contradiction check logic (actually correct)

### Resource Exhaustion
- ❌ No page limit (HIGH-2)
- ❌ Unbounded memory growth (RESOURCE-1)
- ❌ No API timeout (RESOURCE-2)

---

## RECOMMENDATIONS PRIORITY

1. **IMMEDIATE:** Fix CRITICAL-1 (path traversal) and CRITICAL-2 (prompt injection)
2. **HIGH PRIORITY:** Fix HIGH-2 (page limit), HIGH-4 (grid bounds), MATH-2 (unit conversion)
3. **MEDIUM PRIORITY:** Fix MEDIUM-5 (negative margin), MEDIUM-8 (coordinate bounds), MATH-1 (grid merge)
4. **LOW PRIORITY:** Address LOW severity issues and improve logging

---

## TESTING RECOMMENDATIONS

1. Add fuzzing tests for path traversal attacks
2. Add tests for prompt injection via doc_id
3. Add tests for very large PDFs (1000+ pages)
4. Add tests for unit conversion edge cases
5. Add tests for grid merge with various row configurations
6. Add performance tests for memory usage with large documents

---

**Review completed:** 2026-02-27
