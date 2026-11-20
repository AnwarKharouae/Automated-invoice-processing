Automated-invoice-processing

A 100% local, desktop invoice extraction and review application built with PySide6 and powered by a three-model AI pipeline. Process invoices locally at zero cost per invoice (~20 seconds per invoice), verify extractions in an interactive review UI with visual flags and edit tracking, and export formatted multi-sheet Excel workbooks.

Highlights

100% Local & Zero Cost per Invoice — Runs completely on your machine with no external API fees.

Three-Model Pipeline — Combines DeepSeek-OCR, Llama 3.2, and PaddleOCR-VL with automatic VRAM management for 8 GB GPUs.

Human-in-the-Loop Review — Visual bounding-box verification, pink flags for unlocated values, and green edit tracking.

6-Sheet Excel Export — Color-coded, formatted workbooks with audit trails and review tabs.

Portable Sessions — Save and reload full review states, schemas, and annotated images as self-contained ZIP files.

Standalone Windows EXE — Portable Onedir build (~250 MB) that launches in under 1 second with no Python installation required.

Getting Started

Option 1: Standalone Windows EXE

Download/copy the portable application folder anywhere on your Windows machine (no Python installation required).

Ensure Ollama is installed and running in the background (the app checks for Ollama on startup).

Launch the executable. Editable resources—including the schema, sounds, and GIFs—live directly next to the .exe.

Option 2: Running from Source

Ensure Ollama is installed and running, with the pipeline models available (DeepSeek-OCR, Llama 3.2, and PaddleOCR-VL).

Install the Python dependencies:

pip install -r requirements.txt


Run the application from your local repository.

Features

Core Extraction

Three-model pipeline — DeepSeek-OCR reads the document, Llama 3.2 structures the extracted fields, and PaddleOCR-VL spots value locations.

Row-anchored value location — Matches each extracted value to the correct row on the invoice.

Annotated output image — Draws yellow bounding boxes for invoice details and green bounding boxes for line items.

Fuzzy matching — Survives OCR typos and formatting variations.

Numeric cleaning — Automatically strips $, ,, and USD.

Model Lifecycle & VRAM Management

Automatic model swapping — Unloads Llama + Paddle before loading DeepSeek, and vice versa.

VRAM-aware — Designed specifically for 8 GB GPUs to prevent out-of-memory (OOM) crashes.

Startup preloading — DeepSeek preloads at startup so it is ready as soon as you click Process.

Warm between batches — DeepSeek reloads automatically after each batch so subsequent batches in the same session start instantly without extra loading overhead.

Review Interface

Zoomable image viewer — Smooth mouse-wheel zoom, Ctrl+0 to fit to view, and a gray workspace background.

Editable mini-Excel tables — Double-click cells to edit, and add or remove rows and columns directly.

Per-invoice review — Click any invoice in the sidebar to load its annotated image and extracted tables.

Pink flags — Highlights values the AI could not locate on the invoice image.

Green flags — Highlights values you manually edited, maintaining a visible audit trail inside the app.

Per-invoice Undo / Redo — Ctrl+Z / Ctrl+Y undo/redo stacks that persist even when switching between invoices.

Sidebar status icons — Track progress at a glance:

☐ New

✏️ Edited

❓ Empty

⚠ Failed

✓ Approved

Right-click context menu — Quickly approve, remove, or add new invoices from the sidebar.

Individual approval — Approve invoices one by one before exporting the batch.

Batch Workflow

Add invoices mid-session — Only newly added files are processed; existing edits are preserved.

Remove invoices — Remove individual invoices from the list without affecting the rest of the batch.

Skip already-processed files — Clicking Process multiple times only processes new files.

Empty extraction detection — Automatically flags blank pages and failed extractions.

Manual fallback — Every invoice receives an editable table even if AI extraction produces no output.

Loading Experience & Audio

Animated progress overlay — Full-screen dark overlay during processing with phase labels showing the exact running step.

Weighted progress bar — Reflects actual time spent per phase.

Per-phase character GIFs — Custom visuals for preprocess, OCR, structure, spotting, drawing, and done states (with automatic emoji fallbacks if a GIF is missing).

Audio cues (replay-safe):

Tuturu on startup when DeepSeek is ready.

FAAAAAAAAAH when a batch finishes processing.

Ready chime when DeepSeek reloads after a batch.

Save & Session Management

Save / Save As / Overwrite Save — Standard file saving behavior, including silent overwrites of the active session.

Portable session ZIPs — Bundles the review state, schema, and annotated images into a single portable archive.

Load session — Restore an entire review session in a fresh launch of the app.

Timestamped & versioned filenames — Suggested filenames include the date/time and built-in versioning for an audit trail.

Optional session cleanup on export — User-confirmed cleanup prompt upon exporting.

Excel Export

Exports a formatted 6-sheet Excel workbook per batch:

All Invoices — Color-coded blocks (one per invoice) with details and line items stacked.

Items — Flat table with one row per line item, color-coded by source invoice.

Details — Wide-format flat table with one row per invoice.

Needs Review — Lists invoices with unresolved pink flags alongside the specific flagged cells.

Changes — Audit trail of manual user edits, with edited cells highlighted in green.

Failed / Manual — Logs crashed or empty extractions for accountability.

Export Styling:

Preserves pink fills for unresolved flags and green fills for user-edited values.

Assigns distinct pastel colors per invoice (ensuring adjacent invoices differ).

Applies red headers for pink-flagged invoices and orange headers for empty extractions.

Adds borders to every cell, plus frozen header rows and autofilters on flat sheets.

Preferences & Interface Polish

Configurable folders — Set default directories for Excel exports (Approve Batch & Save) and session saves (Save Session), persisted between sessions.

Built-in schema editor — Edit the Llama extraction prompt directly inside the app, with "save my ass.txt" available as a backup reset option.

Light & dark mode — Toolbar theme toggle with full palette handling and theme-matched modal dialogs.

Toolbar & status bar — Emoji toolbar actions (📂 Upload, 📁 Load Session, 💾 Save Session, ⚙️ Preferences, 🌙 Dark, ▶️ Process, ✅ Approve), an always-visible icon legend in the bottom-right status bar, and a custom judgemental cat window icon.

Safety & Robustness

Startup & pre-flight checks — Clear error prompts if Ollama is not running or if the schema file is missing.

Crash isolation — A failure on one invoice will not crash the rest of the batch; failed invoices are tracked in the sidebar and excluded from default export.

Session version check — Prevents loading incompatible session archives.

Atomic session saves — Writes session data to a temporary folder before zipping to prevent corruption.

License

This project is licensed under the MIT License.
