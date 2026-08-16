# Reference images

Drop your brand/style reference image(s) directly in this folder (`.jpg`, `.jpeg`, `.png`, or `.webp`).

- Every image found here is sent to Gemini 3 Pro Image (via OpenRouter) alongside the generation
  prompt for every visual concept render — as actual image input, not a text description.
- Files are read in **filename natural-sort order** (numeric-aware — `i2.jpg` sorts before
  `i11.jpg`). The first one is treated as the primary reference (composition, camera angle,
  lighting, etc.); any others are treated as supporting references. Prefix filenames with numbers
  to control the order, e.g. `01-hero.jpg`, `02-detail.jpg`.
- No restart or code change needed — just add/remove/replace files here and the next generation
  picks them up.
- Leave the folder empty to generate without reference conditioning (falls back to prompt-only,
  same as before).
- **If your images are finished ad creatives** (logo, headline copy, discount badges, CTA
  buttons) rather than clean photography, that's fine — the prompt explicitly tells Gemini to
  extract only the underlying photographic qualities (composition, lighting, environment,
  materials) and to exclude any text/logo/badges/UI chrome from the generated output.
- `archive/` holds reference images that are currently excluded from generation (not deleted) —
  move a file back up into this folder to bring it back into rotation.
