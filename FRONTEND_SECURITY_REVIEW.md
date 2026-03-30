# Frontend Security and Correctness Code Review

**Date:** February 27, 2026  
**Scope:** `frontend/src/` directory  
**Files Reviewed:** 15 files

---

## Executive Summary

This review identified **2 CRITICAL**, **5 HIGH**, **8 MEDIUM**, and **4 LOW** severity security and correctness issues. The most critical concerns involve potential XSS vulnerabilities from unescaped user-controlled data and information leakage through error messages.

---

## CRITICAL Issues

### CRITICAL-1: Potential XSS via Unescaped User-Controlled Data in Chat Messages
**File:** `components/SidebarRight.tsx`  
**Lines:** 64, 75, 123, 208  
**Severity:** CRITICAL

**Issue:** User-controlled data from API responses (answers, reasons, formatted answers) is rendered directly without HTML escaping. While React escapes by default when using JSX text content, the data flows through multiple components and could be vulnerable if rendering logic changes.

**Vulnerable Code:**
```tsx
// Line 64: msg.text rendered directly
<p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{msg.text}</p>

// Line 75: res.reason rendered directly
<p className="text-amber-900 dark:text-amber-200 text-sm leading-relaxed">{res.reason}</p>

// Line 123: answer rendered directly
<p className="text-gray-900 dark:text-gray-100 text-sm leading-relaxed">{answer}</p>

// Line 208: msg.text rendered directly
{msg.text}
```

**Risk:** If the API is compromised or returns malicious HTML/JavaScript, it could execute in the user's browser context.

**Recommendation:**
- Explicitly sanitize all user-controlled strings before rendering
- Use a library like `DOMPurify` for any HTML content
- Consider using `dangerouslySetInnerHTML` only when absolutely necessary and with sanitization
- Add Content Security Policy (CSP) headers

---

### CRITICAL-2: Potential XSS via Filename Display
**File:** `App.tsx`  
**Line:** 156  
**Severity:** CRITICAL

**Issue:** Filenames from API responses are displayed directly without sanitization. While React escapes text content, filenames could contain malicious content if rendered in contexts that don't escape.

**Vulnerable Code:**
```tsx
// Line 156
{selectedDocId
  ? documents.find((d) => d.doc_id === selectedDocId)?.filename ?? selectedDocId
  : 'Select a document'}
```

**Risk:** Malicious filenames could potentially be used in XSS attacks if the rendering context changes or if used in attributes.

**Recommendation:**
- Sanitize filenames before display
- Ensure filenames are always rendered as text content, never as HTML
- Validate filename format on the backend

---

## HIGH Issues

### HIGH-1: Information Leakage in Error Messages
**File:** `api.ts`  
**Lines:** 135-138, 152-156, 196-199, 375-376  
**Severity:** HIGH

**Issue:** Error messages from API responses are exposed directly to users, potentially leaking sensitive information about system internals, file paths, database errors, or API structure.

**Vulnerable Code:**
```typescript
// Lines 135-138
const err = await res.json().catch(() => ({ detail: res.statusText }));
const detail = err.detail;
const message = Array.isArray(detail) ? detail.join(' ') : detail ?? 'Delete failed';
throw new Error(message);

// Lines 152-156 (similar pattern)
// Lines 196-199 (similar pattern)
// Lines 375-376 (similar pattern)
```

**Risk:** Error messages could reveal:
- Internal file paths
- Database schema information
- API endpoint details
- Stack traces or technical details
- User enumeration information

**Recommendation:**
- Implement error message sanitization
- Map backend error codes to user-friendly messages
- Log detailed errors server-side only
- Never expose stack traces or internal paths to clients

---

### HIGH-2: Missing Input Validation on User Questions
**File:** `api.ts`, `App.tsx`, `components/SidebarRight.tsx`  
**Lines:** `api.ts:244-264`, `App.tsx:89-109`, `SidebarRight.tsx:56-60`  
**Severity:** HIGH

**Issue:** User questions are only trimmed but not validated for length, content, or format before being sent to the API. This could allow:
- Extremely long strings causing DoS
- Injection attempts
- Resource exhaustion

**Vulnerable Code:**
```typescript
// api.ts:255 - No validation
body: JSON.stringify({
  doc_id: docId,
  question,  // No length limit, no sanitization
  include_formatted_answer: options?.includeFormattedAnswer ?? false,
}),

// App.tsx:92 - Only trim()
if (!selectedDocId?.trim() || !question.trim()) return;
```

**Risk:**
- DoS attacks via extremely long strings
- Potential injection if backend doesn't validate
- Resource exhaustion

**Recommendation:**
- Add maximum length validation (e.g., 1000 characters)
- Validate question format (reject empty, whitespace-only)
- Consider rate limiting on the frontend
- Sanitize special characters if needed

---

### HIGH-3: Missing CSRF Protection
**File:** `api.ts` (all API calls)  
**Severity:** HIGH

**Issue:** API requests use Bearer tokens but there's no explicit CSRF protection mechanism. While Bearer tokens mitigate some CSRF risks, additional protection should be considered for state-changing operations.

**Vulnerable Code:**
```typescript
// All API calls use Bearer tokens but no CSRF tokens
const headers = await authHeaders({ 'Content-Type': 'application/json' });
```

**Risk:**
- Cross-site request forgery attacks
- Unauthorized actions if token is compromised

**Recommendation:**
- Implement CSRF tokens for state-changing operations (POST, PUT, DELETE)
- Use SameSite cookies if applicable
- Consider double-submit cookie pattern
- Verify Origin/Referer headers on backend

---

### HIGH-4: Race Condition in Document Deletion
**File:** `App.tsx`  
**Lines:** 67-82  
**Severity:** HIGH

**Issue:** The `handleDeleteDocument` function doesn't prevent multiple simultaneous deletion requests for the same document, which could cause race conditions or inconsistent UI state.

**Vulnerable Code:**
```typescript
const handleDeleteDocument = useCallback(
  async (docId: string) => {
    try {
      await apiDeleteDocument(docId);
      await refreshDocuments();
      // No check if docId still exists or if deletion is in progress
    } catch {
      // Silent failure
    }
  },
  [refreshDocuments, selectedDocId]
);
```

**Risk:**
- Multiple deletion requests for same document
- UI state inconsistencies
- Potential errors if document is deleted while being viewed

**Recommendation:**
- Add loading state per document ID
- Disable delete button while deletion is in progress
- Check document existence before deletion
- Handle concurrent deletion attempts gracefully

---

### HIGH-5: Missing Error Boundaries for Component Trees
**File:** `main.tsx`, `App.tsx`  
**Severity:** HIGH

**Issue:** While there's a top-level error boundary in `main.tsx`, individual component trees (like DocumentViewer, FileUploader, SidebarRight) don't have error boundaries. A single component error could crash the entire app.

**Current Implementation:**
```tsx
// main.tsx has ErrorBoundary, but no component-level boundaries
<ErrorBoundary>
  <ThemeProvider>
    <AuthProvider>
      <App />
    </AuthProvider>
  </ThemeProvider>
</ErrorBoundary>
```

**Risk:**
- Single component error crashes entire application
- Poor user experience
- Loss of user data/work in progress

**Recommendation:**
- Add error boundaries around major component sections:
  - DocumentViewer
  - FileUploader
  - SidebarRight
  - SidebarLeft
- Provide recovery mechanisms (retry, reset state)
- Log errors to monitoring service

---

## MEDIUM Issues

### MEDIUM-1: Token Expiry Not Handled Proactively
**File:** `api.ts`  
**Lines:** 22-34  
**Severity:** MEDIUM

**Issue:** Firebase tokens are fetched on-demand but there's no proactive refresh mechanism. Tokens could expire mid-request, causing failures.

**Current Code:**
```typescript
async function authHeaders(init?: HeadersInit): Promise<HeadersInit> {
  const headers = new Headers(init);
  const auth = getFirebaseAuth();
  if (auth?.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      // No forceRefresh or expiry check
      if (token) headers.set('Authorization', `Bearer ${token}`);
    } catch {
      // ignore token errors
    }
  }
  return headers;
}
```

**Risk:**
- Expired tokens causing 401 errors
- Poor user experience with unexpected logouts
- Failed requests due to token expiry

**Recommendation:**
- Use `getIdToken(true)` to force refresh when needed
- Implement token refresh before expiry
- Add retry logic with token refresh on 401

---

### MEDIUM-2: Insecure Direct Object References - Document ID Validation
**File:** `api.ts` (all document operations)  
**Severity:** MEDIUM

**Issue:** Document IDs from user input are used directly in API calls without validation. While `encodeURIComponent` prevents URL injection, there's no validation that the user has access to the document.

**Vulnerable Code:**
```typescript
// api.ts:309 - docId used directly
export async function getCanonical(docId: string): Promise<CanonicalResponse> {
  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    // No validation that docId is valid format or user has access
  });
}
```

**Risk:**
- Attempts to access other users' documents
- Potential enumeration attacks
- Invalid document IDs causing errors

**Recommendation:**
- Validate document ID format (UUID, length, characters)
- Backend must verify user ownership/access
- Return 404 (not 403) for non-existent documents to prevent enumeration
- Rate limit document access attempts

---

### MEDIUM-3: File Upload Validation Insufficient
**File:** `components/FileUploader.tsx`  
**Lines:** 64-70  
**Severity:** MEDIUM

**Issue:** File upload only checks file extension (`.pdf`) but doesn't validate:
- File size limits
- MIME type
- File content (magic bytes)
- Filename sanitization

**Current Code:**
```typescript
if (!file.name.toLowerCase().endsWith('.pdf')) {
  setError('Please upload a PDF file.');
  return;
}
// No size check, MIME check, or content validation
```

**Risk:**
- Large file uploads causing DoS
- Malicious files with `.pdf` extension
- Filename-based attacks

**Recommendation:**
- Add file size validation (e.g., max 50MB)
- Validate MIME type (`application/pdf`)
- Check file magic bytes
- Sanitize filename
- Show progress for large files

---

### MEDIUM-4: Error Message Leaks API Status
**File:** `App.tsx`  
**Line:** 102  
**Severity:** MEDIUM

**Issue:** Error message "Query failed. Is the API running?" reveals system architecture details.

**Vulnerable Code:**
```typescript
setMessages((m) => [
  ...m,
  { role: 'assistant', text: 'Query failed. Is the API running?', response: { status: 'refuse', reason: 'Query failed.' } },
]);
```

**Risk:**
- Information disclosure about system architecture
- Aids attackers in reconnaissance

**Recommendation:**
- Use generic error message: "Query failed. Please try again."
- Log detailed errors server-side only

---

### MEDIUM-5: Missing Input Sanitization in Correction Submission
**File:** `components/ReviewPanel.tsx`  
**Lines:** 62-70  
**Severity:** MEDIUM

**Issue:** User-provided correction values and notes are not sanitized before submission.

**Vulnerable Code:**
```typescript
await submitCorrection({
  doc_id: docId,
  canonical_id: canonicalId,
  canonical_type: canonicalType,
  action,
  original_value: originalValue,
  corrected_value: action === 'correct' ? correctedValue.trim() : undefined,
  notes: notes.trim() || undefined,  // Only trimmed, not sanitized
});
```

**Risk:**
- Potential injection if backend doesn't sanitize
- XSS if values are rendered elsewhere
- Data corruption

**Recommendation:**
- Validate correction value format
- Sanitize notes field
- Add length limits
- Validate canonical_type and canonical_id formats

---

### MEDIUM-6: window.confirm Used for Critical Actions
**File:** `components/SidebarLeft.tsx`  
**Line:** 132  
**Severity:** MEDIUM

**Issue:** Using `window.confirm` for document deletion is not accessible and provides poor UX. The filename in the confirmation could be XSS if not properly escaped (though React handles this).

**Vulnerable Code:**
```typescript
if (window.confirm(`Delete "${file.name}"? This cannot be undone.`)) {
  onDeleteDocument(file.id);
}
```

**Risk:**
- Poor accessibility
- Inconsistent UI
- Potential XSS if filename contains special characters (though React mitigates)

**Recommendation:**
- Replace with custom modal component
- Ensure proper accessibility (ARIA labels, keyboard navigation)
- Sanitize filename in confirmation message

---

### MEDIUM-7: JSON Parsing Without Validation
**File:** `api.ts`  
**Lines:** 213-237  
**Severity:** MEDIUM

**Issue:** Server-sent events are parsed as JSON without validating structure or size.

**Vulnerable Code:**
```typescript
const msg = JSON.parse(dataLine.slice(6)) as IngestProgressEvent;
// No validation of structure, size, or content
```

**Risk:**
- Malformed JSON causing crashes
- Large payloads causing memory issues
- Type confusion if structure doesn't match

**Recommendation:**
- Validate JSON structure before parsing
- Use schema validation (e.g., Zod)
- Add size limits
- Handle malformed data gracefully

---

### MEDIUM-8: Missing Rate Limiting on Frontend
**File:** `components/SidebarRight.tsx`, `App.tsx`  
**Severity:** MEDIUM

**Issue:** No rate limiting prevents users from spamming queries or API requests.

**Risk:**
- DoS via rapid requests
- Resource exhaustion
- Poor user experience

**Recommendation:**
- Implement debouncing/throttling on query input
- Add rate limiting per user session
- Disable submit button during loading
- Show cooldown messages

---

## LOW Issues

### LOW-1: Theme Storage in localStorage
**File:** `contexts/ThemeContext.tsx`  
**Lines:** 11, 36  
**Severity:** LOW

**Issue:** Theme preference is stored in localStorage. While not sensitive, it persists across sessions and could be manipulated.

**Note:** This is acceptable for theme preferences, but worth noting.

**Recommendation:**
- Consider using sessionStorage if theme should reset
- Validate stored theme value on read

---

### LOW-2: Missing Loading States in Some Operations
**File:** `components/SidebarLeft.tsx`  
**Lines:** 45-55  
**Severity:** LOW

**Issue:** Canonical data fetching doesn't show loading state, causing potential confusion.

**Recommendation:**
- Add loading indicators
- Show skeleton loaders

---

### LOW-3: Error Fallback Displays Full Error Message
**File:** `main.tsx`  
**Line:** 19  
**Severity:** LOW

**Issue:** Error boundary displays full error message which could leak sensitive information in production.

**Vulnerable Code:**
```tsx
<p className="text-sm text-red-700 dark:text-red-400 mb-3 font-mono break-all">{error.message}</p>
```

**Recommendation:**
- Show generic message in production
- Log full error to monitoring service
- Only show details in development

---

### LOW-4: Missing Input Length Limits in UI
**File:** `components/SidebarRight.tsx`  
**Line:** 223  
**Severity:** LOW

**Issue:** Textarea for questions has no `maxLength` attribute.

**Recommendation:**
- Add `maxLength` attribute
- Show character count
- Validate before submission

---

## Positive Findings

1. ✅ **No `dangerouslySetInnerHTML` usage** - Good security practice
2. ✅ **Proper URL encoding** - `encodeURIComponent` used for all URL parameters
3. ✅ **Token handling** - Bearer tokens used correctly, 401 handling implemented
4. ✅ **Error boundary present** - Top-level error boundary in `main.tsx`
5. ✅ **No sensitive data in localStorage** - Only theme preference stored
6. ✅ **Firebase config** - Properly uses environment variables
7. ✅ **File type validation** - At least checks file extension

---

## Recommendations Summary

### Immediate Actions (CRITICAL/HIGH)
1. Implement input sanitization for all user-controlled data
2. Add error message sanitization and mapping
3. Implement CSRF protection
4. Add component-level error boundaries
5. Add input validation (length, format)
6. Fix race conditions in document deletion

### Short-term (MEDIUM)
1. Implement token refresh mechanism
2. Add file upload validation (size, MIME, magic bytes)
3. Replace `window.confirm` with accessible modal
4. Add rate limiting/throttling
5. Validate JSON structure in SSE parsing

### Long-term (LOW)
1. Improve error handling UX
2. Add loading states everywhere
3. Implement comprehensive input validation
4. Add monitoring and error logging

---

## Testing Recommendations

1. **XSS Testing:** Test with malicious payloads in:
   - Chat messages
   - Filenames
   - Correction values
   - Error messages

2. **Input Validation Testing:**
   - Extremely long strings
   - Special characters
   - Unicode characters
   - SQL injection patterns

3. **Race Condition Testing:**
   - Rapid document deletion
   - Concurrent API requests
   - Multiple file uploads

4. **Error Handling Testing:**
   - Network failures
   - API errors
   - Invalid responses
   - Token expiry scenarios

---

**Review Completed:** February 27, 2026  
**Next Review Recommended:** After implementing CRITICAL and HIGH priority fixes
