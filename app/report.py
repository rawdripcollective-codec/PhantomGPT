import io, json, time
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

SEV_COLOR = {"critical": "#b91c1c", "high": "#ea580c", "medium": "#ca8a04",
             "low": "#0891b2", "info": "#4b5563"}


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("H", parent=s["Heading1"], textColor=colors.HexColor("#0f172a")))
    s.add(ParagraphStyle("Small", parent=s["BodyText"], fontSize=7.5, leading=10,
                         textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle("Mono", parent=s["BodyText"], fontName="Courier",
                         fontSize=7, leading=9))
    return s


def markdown(p):
    out = [f"# {p['chat']['title']}", f"Persona: {p['chat']['persona']}", "", "## Findings", ""]
    for f in p["findings"]:
        out += [f"### [{f['severity'].upper()}] {f['title']}",
                f"- host: {f['host'] or '-'}  evidence: {f['ev_id'] or '-'}  status: {f['status']}"]
        if f["notes"]:
            out.append(f"- {f['notes']}")
        out.append("")
    out += ["## Evidence", ""]
    for e in p["evidence"]:
        out += [f"**{e['ev_id']}** `{e['tool']}` sha256 `{e['sha256']}`", "```json",
                (e["payload"] or "")[:3000], "```", ""]
    out += ["## Transcript", ""]
    for m in p["messages"]:
        if m["role"] in ("user", "assistant") and m["content"]:
            out.append(f"**{m['role']}:** {m['content']}")
    return "\n".join(out)


def pdf(p):
    buf = io.BytesIO()
    st = _styles()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=p["chat"]["title"], author="PhantomGPT")
    story = [Paragraph(escape(p["chat"]["title"]), st["Title"]),
             Paragraph(f"Persona: {escape(p['chat']['persona'])} &nbsp;|&nbsp; "
                       f"Generated {time.strftime('%Y-%m-%d %H:%M')}", st["Small"]),
             Spacer(1, 8 * mm)]

    counts = {}
    for f in p["findings"]:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    story.append(Paragraph("Executive summary", st["H"]))
    if p["findings"]:
        hosts = len({f["host"] for f in p["findings"] if f["host"]})
        story.append(Paragraph(
            f"{len(p['findings'])} findings across {hosts} hosts. "
            + ", ".join(f"{v} {k}" for k, v in counts.items()), st["BodyText"]))
    else:
        story.append(Paragraph("No findings recorded.", st["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Findings", st["H"]))
    if p["findings"]:
        rows = [["#", "Severity", "Title", "Host", "Evidence", "Status"]]
        for i, f in enumerate(p["findings"], 1):
            rows.append([str(i), f["severity"].upper(),
                         Paragraph(escape(f["title"]), st["Small"]),
                         escape(f["host"] or "-"), escape(f["ev_id"] or "-"), f["status"]])
        t = Table(rows, colWidths=[10 * mm, 20 * mm, 68 * mm, 34 * mm, 20 * mm, 18 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        for i, f in enumerate(p["findings"], 1):
            t.setStyle(TableStyle([("TEXTCOLOR", (1, i), (1, i),
                                    colors.HexColor(SEV_COLOR.get(f["severity"], "#4b5563")))]))
        story += [t, Spacer(1, 6 * mm)]
    else:
        story.append(Paragraph("None recorded.", st["BodyText"]))

    story += [PageBreak(), Paragraph("Evidence ledger", st["H"]),
              Paragraph("SHA-256 of each raw tool response, in collection order.", st["Small"]),
              Spacer(1, 4 * mm)]
    for e in p["evidence"]:
        story.append(Paragraph(
            f"{escape(e['ev_id'])} - {escape(e['tool'])} - "
            f"<font face='Courier' size=6>{escape(e['sha256'])}</font>", st["Small"]))
        story.append(Paragraph(escape((e["payload"] or "")[:1500]), st["Mono"]))
        story.append(Spacer(1, 3 * mm))

    doc.build(story)
    return buf.getvalue()