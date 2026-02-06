import os
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from invoices.models import Invoice
from invoices.invoice_config import INVOICE_CONFIG


def invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    client = invoice.client
    cfg = INVOICE_CONFIG

    # ----------------------
    # SAFE ATTRIBUTE ACCESS
    # ----------------------
    def safe(obj, attr):
        return getattr(obj, attr, "") or ""

    # ----------------------
    # AMOUNT IN WORDS
    # ----------------------
    def amount_in_words(amount):
        try:
            from num2words import num2words
            return num2words(int(amount), lang="en_IN").title() + " Only"
        except Exception:
            return ""

    # ----------------------
    # TAX CALCULATIONS (MODEL-INDEPENDENT)
    # ----------------------
    subtotal = Decimal(invoice.subtotal())

    cgst_rate = Decimal(cfg["tax"]["cgst"]) / 100
    sgst_rate = Decimal(cfg["tax"]["sgst"]) / 100
    igst_rate = Decimal(cfg["tax"]["igst"]) / 100

    cgst_amount = subtotal * cgst_rate
    sgst_amount = subtotal * sgst_rate
    igst_amount = subtotal * igst_rate

    freight = Decimal(safe(invoice, "freight") or 0)

    total_before_round = subtotal + cgst_amount + sgst_amount + igst_amount + freight
    round_off = total_before_round.quantize(Decimal("1")) - total_before_round
    grand_total = total_before_round + round_off

    # ----------------------
    # PDF RESPONSE
    # ----------------------
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{invoice.formatted_invoice_number()}.pdf"'
    )

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    margin = 30
    usable_width = width - 2 * margin

    left_col_width = usable_width * 0.6
    right_col_width = usable_width * 0.4

    meta_row_height = 22
    item_row_height = 20

    # Outer border
    c.setLineWidth(1)
    c.rect(margin, margin, usable_width, height - 2 * margin)

    current_y = height - margin

    # =====================================================
    # HEADER
    # =====================================================
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 5, current_y - 13, f"Mo. : {cfg['company']['phone']}")
    c.drawRightString(
        width - margin - 5,
        current_y - 13,
        cfg["invoice_meta"]["copies_text"],
    )
    current_y -= 18

    logo_path = os.path.join(settings.BASE_DIR, cfg["company"]["logo_path"])
    if os.path.exists(logo_path):
        c.drawImage(logo_path, margin + 5, current_y - 62, 50, 50, mask="auto")

    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, current_y - 26, cfg["invoice_meta"]["title"])

    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, current_y - 60, cfg["company"]["name"])

    c.line(margin, current_y - 72, width - margin, current_y - 72)
    current_y -= 72

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(width / 2, current_y - 14, cfg["company"]["address"])
    c.line(margin, current_y - 22, width - margin, current_y - 22)
    current_y -= 22

    c.drawCentredString(
        width / 2,
        current_y - 14,
        f"Company’s GSTTIN No. : {cfg['company']['gstin']} , PAN No. : {cfg['company']['pan']}",
    )
    c.line(margin, current_y - 22, width - margin, current_y - 22)
    current_y -= 22

    # =====================================================
    # BUYER + INVOICE GRID
    # =====================================================
    rows = [
        ("Buyer :-", "State Code :", safe(client, "state_code"), safe(invoice, "state_code")),
        (safe(client, "name"), "Invoice No :", "", invoice.formatted_invoice_number()),
        (safe(client, "address"), "Invoice Date :", "", invoice.issue_date.strftime("%d-%m-%Y")),
        ("Party’s GSTIN No. :", "Challan No :", safe(client, "gstin"), safe(invoice, "challan_no")),
        ("Buyers Order No :", "Transport Name :", safe(invoice, "order_no"), safe(invoice, "transport_name")),
        ("Destination :", "Vehicle No :", safe(invoice, "destination"), safe(invoice, "vehicle_no")),
        ("State Code :", "Place of Supply :", safe(client, "state_code"), safe(invoice, "place_of_supply")),
        ("", "Terms / Mode of Payment :", "", cfg["terms"]["payment"]),
    ]

    for l_lbl, r_lbl, l_val, r_val in rows:
        c.rect(margin, current_y - meta_row_height, left_col_width, meta_row_height)
        c.drawString(margin + 5, current_y - 14, f"{l_lbl} {l_val}")

        c.rect(margin + left_col_width, current_y - meta_row_height, right_col_width, meta_row_height)
        c.drawString(
            margin + left_col_width + 5,
            current_y - 14,
            f"{r_lbl} {r_val}",
        )
        current_y -= meta_row_height

    # =====================================================
    # ITEMS TABLE (HEADER BORDERED, ROWS CLEAN)
    # =====================================================
    col_widths = [
        usable_width * 0.10,
        usable_width * 0.30,
        usable_width * 0.10,
        usable_width * 0.08,
        usable_width * 0.10,
        usable_width * 0.15,
        usable_width * 0.17,
    ]

    headers = [
        "Sr. No.",
        "Description of Goods",
        "HSN CODE",
        "UOM",
        "Qty.",
        "Rate Per Unit",
        "AMOUNT Rs.",
    ]

    table_top = current_y

    x = margin
    for i, h in enumerate(headers):
        c.rect(x, table_top - item_row_height, col_widths[i], item_row_height)
        c.drawCentredString(x + col_widths[i] / 2, table_top - 14, h)
        x += col_widths[i]

    current_y = table_top - item_row_height

    items = list(invoice.items.all())
    max_rows = 10

    for idx in range(max_rows):
        x = margin
        if idx < len(items):
            item = items[idx]
            values = [
                str(idx + 1),
                safe(item.product, "name"),
                safe(item.product, "hsn"),
                safe(item, "uom") or "KG",
                str(item.quantity),
                f"{item.price:.0f}",
                f"{item.line_total():.0f}",
            ]
        else:
            values = [""] * 7

        for i, val in enumerate(values):
            if i == 1:
                c.drawString(x + 4, current_y - 14, val)
            else:
                c.drawCentredString(x + col_widths[i] / 2, current_y - 14, val)
            x += col_widths[i]

        current_y -= item_row_height

    c.line(margin, current_y, width - margin, current_y)

    # =====================================================
    # TOTALS + BANK DETAILS
    # =====================================================
    box_height = 22

    left_rows = [
        "Bank Details",
        f"Bank Name : {cfg['bank']['name']}",
        f"A/c No. : {cfg['bank']['account']}",
        f"IFSC Code : {cfg['bank']['ifsc']}",
        f"Total Amount in Words : {amount_in_words(grand_total)}",
    ]

    right_rows = [
        ("Total Amount Before Tax", f"{subtotal:.2f}"),
        (f"CGST {cfg['tax']['cgst']} %", f"{cgst_amount:.2f}"),
        (f"SGST {cfg['tax']['sgst']} %", f"{sgst_amount:.2f}"),
        (f"IGST {cfg['tax']['igst']} %", f"{igst_amount:.2f}"),
        ("Freight", f"{freight:.2f}"),
        ("Round off", f"{round_off:.2f}"),
        ("Total Amount After Tax", f"{grand_total:.2f}"),
    ]

    for i in range(max(len(left_rows), len(right_rows))):
        c.rect(margin, current_y - box_height, left_col_width, box_height)
        if i < len(left_rows):
            c.drawString(margin + 5, current_y - 14, left_rows[i])

        c.rect(margin + left_col_width, current_y - box_height, right_col_width, box_height)
        if i < len(right_rows):
            c.drawRightString(
                width - margin - 5,
                current_y - 14,
                f"{right_rows[i][0]} : {right_rows[i][1]}",
            )
        current_y -= box_height

    # =====================================================
    # DECLARATION + SIGNATURE
    # =====================================================
    decl_height = 80

    c.rect(margin, current_y - decl_height, left_col_width, decl_height)
    c.rect(margin + left_col_width, current_y - decl_height, right_col_width, decl_height)

    declaration = [
        "Certified that the particulars given above are true and correct.",
        "Goods once sold will not be taken back.",
        f"Interest {cfg['terms']['interest']} will be charged on overdue payment.",
        f"Subject to {cfg['terms']['jurisdiction']} Jurisdiction only.",
    ]

    y_text = current_y - 18
    for line in declaration:
        c.drawString(margin + 5, y_text, line)
        y_text -= 14

    c.drawCentredString(
        margin + left_col_width + right_col_width / 2,
        current_y - 30,
        f"For, {cfg['company']['name']}",
    )
    c.drawCentredString(
        margin + left_col_width + right_col_width / 2,
        current_y - 60,
        "Authorised Signatory / Name",
    )

    c.showPage()
    c.save()
    return response
