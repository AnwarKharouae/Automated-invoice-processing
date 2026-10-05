"""
Excel export — Phase 1.

Reads from review_data snapshots. Preserves pink flags only where the
user did NOT edit the cell (initial text == current text).

Sheets:
  1. All Invoices  — colored blocks (details + items stacked per invoice)
  2. Items         — flat table, one row per item
  3. Details       — flat table, one row per invoice (wide format)
"""

import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


PALETTE = [
    "B8D4E8", "FFE0A3", "B2DFDB", "D1C4E9",
    "FFCC80", "B3E5FC", "D7CCC8", "C5CAE9", "DCEDC8",
    "F0F4C3", "B0BEC5",
]
PINK_FILL   = "FFC8C8"
EDITED_FILL = "81C784"
HEADER_TEXT = "FFFFFF"
FLAT_HEADER = "DDDDDD"
NEEDS_REVIEW_HEADER = "EF9A9A"
NEEDS_REVIEW_HEADER = "EF9A9A"    # light red — pink flags or failed
EMPTY_HEADER        = "FFD9A0"    # light orange — empty extraction, manually filled

THIN = Side(style="thin", color="666666")
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# ---------------- helpers ----------------

def _darken(hex_color, factor=0.55):
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{int(r*(1-factor)):02X}{int(g*(1-factor)):02X}{int(b*(1-factor)):02X}"

def _cell(data):
    """Normalize cell to (text, state). Handles list AND tuple (JSON roundtrip)."""
    if isinstance(data, (list, tuple)) and len(data) == 2:
        return data[0], data[1]
    return data, None


def _snapshots(state):
    """Return (initial, current) from a table state dict."""
    history = state.get("history", [])
    idx = state.get("index", -1)
    if not history:
        return None, None
    initial = history[0]
    current = history[idx] if 0 <= idx < len(history) else history[-1]
    return initial, current


def _state_grid(initial, current):
    """
    Return 2D list [row][col] of state per cell.
    Rules:
      - "edited" wins (user touched it)
      - "pink" preserved only if text unchanged from initial
      - else None
    """
    c_rows = current.get("rows", []) if current else []
    i_rows = initial.get("rows", []) if initial else []
    grid = []
    for r, row in enumerate(c_rows):
        r_states = []
        for c, cell in enumerate(row):
            text_c, state_c = _cell(cell)
            if state_c == "edited":
                r_states.append("edited")
                continue
            if state_c == "pink":
                if r < len(i_rows) and c < len(i_rows[r]):
                    text_i, _ = _cell(i_rows[r][c])
                    if str(text_c) == str(text_i):
                        r_states.append("pink")
                        continue
                # text changed but state wasn't updated — treat as edited
                r_states.append("edited")
                continue
            r_states.append(None)
        grid.append(r_states)
    return grid


def _has_pink(grid):
    return any("pink" in r for r in grid)


def _autofit(ws, ncols):
    for col_idx in range(1, ncols + 1):
        letter = get_column_letter(col_idx)
        m = 0
        for row_cells in ws[letter]:
            v = row_cells.value
            if v is not None:
                m = max(m, len(str(v)))
        ws.column_dimensions[letter].width = min(m + 3, 40)


# ---------------- color assignment ----------------

def _assign_colors(entries):
    """
    entries: list of {name, has_pink}
    Returns {name: {"block": hex or None, "header": hex or None}}
    """
    out = {}
    idx = 0
    prev = None
    for e in entries:
        if e["has_pink"]:
            out[e["name"]] = {"block": None, "header": None}
            continue
        if PALETTE[idx % len(PALETTE)] == prev:
            idx += 1
        block = PALETTE[idx % len(PALETTE)]
        prev = block
        idx += 1
        out[e["name"]] = {"block": block, "header": _darken(block)}
    return out


# ---------------- block sheet ----------------

def _write_subtable(ws, row, title, cols, rows, pink, block):
    t = ws.cell(row=row, column=1, value=title)
    t.font = Font(bold=True, size=11)
    if block:
        t.fill = PatternFill("solid", fgColor=block)
    row += 1

    for c, h in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(bold=True)
        cell.border = CELL_BORDER
        if block:
            cell.fill = PatternFill("solid", fgColor=block)
    row += 1



    for r, r_data in enumerate(rows):
        for c, cell_data in enumerate(r_data):
            text, _ = _cell(cell_data)
            cell = ws.cell(row=row, column=c + 1, value=text)
            cell.border = CELL_BORDER
            is_state = pink and r < len(pink) and c < len(pink[r]) and pink[r][c]
            if is_state == "pink":
                cell.fill = PatternFill("solid", fgColor=PINK_FILL)
            elif is_state == "edited":
                cell.fill = PatternFill("solid", fgColor=EDITED_FILL)
            elif block:
                cell.fill = PatternFill("solid", fgColor=block)
        row += 1
    return row

def _header_for(fname, data, has_pink):
    """Return (text, fill_hex, text_color_hex)."""
    if data.get("failed"):
        return (f"⚠ {fname} — manual entry (processing failed)",
                NEEDS_REVIEW_HEADER, "7A0000")
    if data.get("empty"):
        return (f"❓ {fname} — manually filled (empty extraction)",
                EMPTY_HEADER, "7A4000")
    if has_pink:
        return (f"⚠ {fname} — needs review",
                NEEDS_REVIEW_HEADER, "7A0000")
    return (f"✓ {fname}", None, HEADER_TEXT)   # None → use block header color


def _build_all_invoices(wb, filenames, review_data, color_map, snap_map, pink_map):
    ws = wb.active
    ws.title = "All Invoices"
    row = 1

    for fname in filenames:
        data = review_data.get(fname, {})
        colors = color_map[fname]
        block = colors["block"]
        header = colors["header"]

        d_pink = pink_map[fname]["details"]
        i_pink = pink_map[fname]["items"]
        has_pink = _has_pink(d_pink) or _has_pink(i_pink)

        header_text, header_fill, text_color = _header_for(fname, data, has_pink)
        if header_fill is None:
            header_fill = header          # clean invoice — use block color
        if header_fill is None:
            header_fill = NEEDS_REVIEW_HEADER  # safety net

        h = ws.cell(row=row, column=1, value=header_text)
        h.font = Font(bold=True, size=14, color=text_color)
        h.fill = PatternFill("solid", fgColor=header_fill)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1

        d_cur = snap_map[fname]["details"]
        i_cur = snap_map[fname]["items"]

        row = _write_subtable(ws, row, "Details",
                              d_cur.get("columns", []), d_cur.get("rows", []),
                              d_pink, block)
        row += 1
        row = _write_subtable(ws, row, "Items",
                              i_cur.get("columns", []), i_cur.get("rows", []),
                              i_pink, block)
        row += 3

    _autofit(ws, 5)


# ---------------- flat sheets ----------------

def _build_items_flat(wb, filenames, review_data, color_map, snap_map, pink_map):
    ws = wb.create_sheet("Items")

    # union of columns
    all_cols = []
    for fname in filenames:
        for c in snap_map[fname]["items"].get("columns", []):
            if c not in all_cols:
                all_cols.append(c)
    # standard order first
    standard = ["product_name", "product_code", "quantity", "unit_price", "total"]
    ordered = [c for c in standard if c in all_cols] + \
              [c for c in all_cols if c not in standard]

    headers = ["source_file", "invoice_number"] + ordered
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=FLAT_HEADER)
        c.border = CELL_BORDER

    for fname in filenames:
        block = color_map[fname]["block"]
        d_cur = snap_map[fname]["details"]
        i_cur = snap_map[fname]["items"]
        i_pink = pink_map[fname]["items"]

        # invoice number from details
        inv_num = ""
        for r in d_cur.get("rows", []):
            if len(r) >= 2:
                k, _ = _cell(r[0]); v, _ = _cell(r[1])
                if str(k).strip().lower() == "invoice_number":
                    inv_num = v
                    break

        i_cols = i_cur.get("columns", [])
        for r_idx, r_data in enumerate(i_cur.get("rows", [])):
            out = [fname, inv_num]
            flags = [False, False]
            for field in ordered:
                if field in i_cols:
                    ci = i_cols.index(field)
                    text, _ = _cell(r_data[ci]) if ci < len(r_data) else ("", False)
                    out.append(text)
                    flags.append(i_pink[r_idx][ci] if r_idx < len(i_pink)
                                 and ci < len(i_pink[r_idx]) else False)
                else:
                    out.append("")
                    flags.append(False)
            ws.append(out)
            row_num = ws.max_row
            for c_idx, (text, pink) in enumerate(zip(out, flags), 1):
                cell = ws.cell(row=row_num, column=c_idx)
                cell.border = CELL_BORDER
                if pink == "pink":
                    cell.fill = PatternFill("solid", fgColor=PINK_FILL)
                elif pink == "edited":
                    cell.fill = PatternFill("solid", fgColor=EDITED_FILL)
                elif block:
                    cell.fill = PatternFill("solid", fgColor=block)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autofit(ws, len(headers))


def _build_details_flat(wb, filenames, review_data, color_map, snap_map, pink_map):
    ws = wb.create_sheet("Details")

    all_fields = []
    for fname in filenames:
        for r in snap_map[fname]["details"].get("rows", []):
            if len(r) >= 2:
                k, _ = _cell(r[0])
                if k not in all_fields:
                    all_fields.append(str(k))

    standard = [
        "invoice_number", "date", "consignee_name", "consignee_address",
        "consignee_phone", "consignee_email", "port_of_loading",
        "port_of_discharge", "vessel_airline", "shipment_date",
        "bank_name", "account_number", "routing_number", "payment_method",
        "total_quantity", "total_value",
    ]
    ordered = [f for f in standard if f in all_fields] + \
              [f for f in all_fields if f not in standard]

    ws.append(["source_file"] + ordered)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=FLAT_HEADER)
        c.border = CELL_BORDER

    for fname in filenames:
        block = color_map[fname]["block"]
        d_cur = snap_map[fname]["details"]
        d_pink = pink_map[fname]["details"]

        field_val = {}
        field_pink = {}
        for r_idx, r in enumerate(d_cur.get("rows", [])):
            if len(r) >= 2:
                k, _ = _cell(r[0]); v, _ = _cell(r[1])
                field_val[str(k)] = v
                field_pink[str(k)] = (
                    d_pink[r_idx][1] if r_idx < len(d_pink)
                    and len(d_pink[r_idx]) > 1 else False
                )

        out = [fname] + [field_val.get(f, "") for f in ordered]
        flags = [False] + [field_pink.get(f, False) for f in ordered]
        ws.append(out)
        row_num = ws.max_row
        for c_idx, (text, pink) in enumerate(zip(out, flags), 1):
            cell = ws.cell(row=row_num, column=c_idx)
            cell.border = CELL_BORDER
            if pink == "pink":
                cell.fill = PatternFill("solid", fgColor=PINK_FILL)
            elif pink == "edited":
                cell.fill = PatternFill("solid", fgColor=EDITED_FILL)
            elif block:
                cell.fill = PatternFill("solid", fgColor=block)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    _autofit(ws, len(ordered) + 1)

# ---------------- main API ----------------
def _safe_sheet_name(name):
    """Excel forbids \ / ? * [ ] : and max 31 chars."""
    for ch in '\\/?*[]:':
        name = name.replace(ch, "-")
    return name[:31]

def _build_failed_sheet(wb, filenames, review_data, snap_map, pink_map):
    """Lists invoices that crashed or extracted empty, with their manual tables."""
    failed = [f for f in filenames
              if review_data.get(f, {}).get("failed")
              or review_data.get(f, {}).get("empty")]
    if not failed:
        return

    ws = wb.create_sheet(_safe_sheet_name("Failed / Manual"))

    ws["A1"] = "Invoices that failed processing or returned empty"
    ws["A1"].font = Font(bold=True, size=14, color="7A0000")
    ws["A2"] = "These were manually filled in by the user."
    ws["A2"].font = Font(italic=True, color="666666")

    row = 4
    for fname in failed:
        data = review_data.get(fname, {})
        if data.get("failed"):
            label = f"⚠ {fname} — processing failed, filled manually"
            fill = NEEDS_REVIEW_HEADER
            tcolor = "7A0000"
        else:
            label = f"❓ {fname} — empty extraction, filled manually"
            fill = EMPTY_HEADER
            tcolor = "7A4000"

        h = ws.cell(row=row, column=1, value=label)
        h.font = Font(bold=True, size=13, color=tcolor)
        h.fill = PatternFill("solid", fgColor=fill)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1

        d_cur = snap_map[fname]["details"]
        i_cur = snap_map[fname]["items"]
        d_pink = pink_map[fname]["details"]
        i_pink = pink_map[fname]["items"]

        row = _write_subtable(ws, row, "Details",
                              d_cur.get("columns", []), d_cur.get("rows", []),
                              d_pink, None)
        row += 1
        row = _write_subtable(ws, row, "Items",
                              i_cur.get("columns", []), i_cur.get("rows", []),
                              i_pink, None)
        row += 3

    _autofit(ws, 5)
# ---------------- main API ----------------

def export_batch(review_data, filenames, output_path):
    if not filenames:
        raise ValueError("No invoices to export")

    # Build snapshot + state maps
    snap_map = {}
    pink_map = {}
    entries = []
    for fname in filenames:
        data = review_data.get(fname, {})
        d_state = data.get("details_state", {})
        i_state = data.get("items_state", {})
        d_init, d_cur = _snapshots(d_state)
        i_init, i_cur = _snapshots(i_state)
        d_cur = d_cur or {"columns": [], "rows": []}
        i_cur = i_cur or {"columns": [], "rows": []}

        d_states = _state_grid(d_init, d_cur)
        i_states = _state_grid(i_init, i_cur)

        snap_map[fname] = {"details": d_cur, "items": i_cur}
        pink_map[fname] = {"details": d_states, "items": i_states}

        entries.append({
            "name": fname,
            "has_pink": _has_pink(d_states) or _has_pink(i_states),
        })

    color_map = _assign_colors(entries)

    wb = Workbook()
    _build_all_invoices(wb, filenames, review_data, color_map, snap_map, pink_map)
    _build_items_flat(wb, filenames, review_data, color_map, snap_map, pink_map)
    _build_details_flat(wb, filenames, review_data, color_map, snap_map, pink_map)
    _build_failed_sheet(wb, filenames, review_data, snap_map, pink_map)
    _build_needs_review_sheet(wb, filenames, review_data, snap_map, pink_map)
    _build_changes_sheet(wb, filenames, snap_map)

    wb.save(output_path)
    return output_path


def _build_needs_review_sheet(wb, filenames, review_data, snap_map, pink_map):
    """Two tables: list of invoices with pink + list of specific pink cells."""
    with_pink = []
    cell_rows = []

    for fname in filenames:
        d_pink = pink_map[fname]["details"]
        i_pink = pink_map[fname]["items"]
        if not (_has_pink(d_pink) or _has_pink(i_pink)):
            continue

        with_pink.append(fname)

        # details
        d_cur = snap_map[fname]["details"]
        d_cols = d_cur.get("columns", [])
        for r, row in enumerate(d_cur.get("rows", [])):
            for c, cell in enumerate(row):
                if r < len(d_pink) and c < len(d_pink[r]) and d_pink[r][c] == "pink":
                    field = ""
                    if d_cols and c < len(d_cols):
                        field = d_cols[c]
                    text = cell[0] if isinstance(cell, tuple) else cell
                    cell_rows.append([fname, "Details", field, str(text)])

        # items
        i_cur = snap_map[fname]["items"]
        i_cols = i_cur.get("columns", [])
        for r, row in enumerate(i_cur.get("rows", [])):
            for c, cell in enumerate(row):
                if r < len(i_pink) and c < len(i_pink[r]) and i_pink[r][c] == "pink":
                    field = ""
                    if i_cols and c < len(i_cols):
                        field = i_cols[c]
                    text = cell[0] if isinstance(cell, tuple) else cell
                    cell_rows.append([fname, "Items", field, str(text)])

    if not with_pink:
        return

    ws = wb.create_sheet("Needs Review")

    ws["A1"] = "Invoices with unresolved pink flags"
    ws["A1"].font = Font(bold=True, size=14, color="7A0000")

    row = 3
    ws.cell(row=row, column=1, value="invoice").font = Font(bold=True)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=FLAT_HEADER)
    ws.cell(row=row, column=1).border = CELL_BORDER
    for i, fname in enumerate(with_pink, 1):
        c = ws.cell(row=row + i, column=1, value=fname)
        c.border = CELL_BORDER
    row = row + 1 + len(with_pink) + 2

    ws.cell(row=row, column=1, value="Unresolved cells").font = Font(bold=True, size=12)
    row += 1

    headers = ["source_file", "table", "field", "value"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=FLAT_HEADER)
        cell.border = CELL_BORDER
    row += 1

    for cr in cell_rows:
        for c, v in enumerate(cr, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.border = CELL_BORDER
            cell.fill = PatternFill("solid", fgColor=PINK_FILL)
        row += 1

    _autofit(ws, 4)

def _has_edits(snap):
    for row in snap.get("rows", []):
        for cell in row:
            if isinstance(cell, tuple) and cell[1] == "edited":
                return True
    return False


def _write_change_table(ws, row, title, cols, rows):
    """Same as _write_subtable but only edited cells get green fill."""
    t = ws.cell(row=row, column=1, value=title)
    t.font = Font(bold=True, size=11, color="2E7D32")
    row += 1

    for c, h in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(bold=True)
        cell.border = CELL_BORDER
    row += 1

    for r_data in rows:
        for c, cell_data in enumerate(r_data, 1):
            text = cell_data[0] if isinstance(cell_data, tuple) else cell_data
            state = cell_data[1] if isinstance(cell_data, tuple) else None
            cell = ws.cell(row=row, column=c, value=text)
            cell.border = CELL_BORDER
            if state == "edited":
                cell.fill = PatternFill("solid", fgColor=EDITED_FILL)
        row += 1
    return row


def _build_changes_sheet(wb, filenames, snap_map):
    edited = [f for f in filenames
              if _has_edits(snap_map[f]["details"]) or _has_edits(snap_map[f]["items"])]
    if not edited:
        return

    ws = wb.create_sheet("Changes")
    ws["A1"] = "Manually edited cells (green)"
    ws["A1"].font = Font(bold=True, size=14, color="2E7D32")
    ws["A2"] = "Only invoices where the user changed something are listed."
    ws["A2"].font = Font(italic=True, color="666666")

    row = 4
    for fname in edited:
        h = ws.cell(row=row, column=1, value=f"✏️ {fname}")
        h.font = Font(bold=True, size=13, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="4CAF50")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1

        d_cur = snap_map[fname]["details"]
        i_cur = snap_map[fname]["items"]

        row = _write_change_table(ws, row, "Details",
                                  d_cur.get("columns", []), d_cur.get("rows", []))
        row += 1
        row = _write_change_table(ws, row, "Items",
                                  i_cur.get("columns", []), i_cur.get("rows", []))
        row += 3

    _autofit(ws, 5)