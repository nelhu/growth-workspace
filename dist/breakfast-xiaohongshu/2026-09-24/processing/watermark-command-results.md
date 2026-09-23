# Watermark command results

All three `remove-ai-watermarks all` commands used version 0.41.1 and exited 1 only because invisible-watermark GPU dependencies were unavailable. For each image, visible-watermark removal reported `Skipped (no visible watermark detected)`, AI metadata stripping completed, and a distinct clean output file was generated. This is non-blocking under the active Skill.

All three follow-up `identify --json` commands exited 0 and returned `watermarks: []`, `signals: []`, `ai_from_metadata: false`, and `confidence: none`. Absence of metadata is not absolute proof that an image is clean.
