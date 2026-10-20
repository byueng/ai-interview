# Resume upload (frontend contract proposal)

The backend endpoint is not implemented by this change.

- `POST /interview/sessions/{session_id}/resume`
- Uses the existing `VITE_API_BASE_URL` and `/interview` development proxy.
- Request: `multipart/form-data`, one `file` field containing the original PDF.
  The browser supplies the multipart boundary. No Base64 conversion or frontend parsing.
- Success: HTTP 200 with `{ "resume": "server/path/to/resume.pdf" }`.
  Return only after accepting the file for use by the existing candidate configuration.
- The returned path is included in `candidate_config.resume` when saving configuration.
- Errors may return `{ "detail": "User-facing error" }` with a non-2xx status.
- The backend must validate the PDF, enforce its file size policy and associate it with
  the specified session. Frontend extension/MIME checks are only picker validation.
- Removing an association clears the pending candidate configuration, not the server file.
- Upload failure preserves the previously associated resume. No parsing result is mocked.
