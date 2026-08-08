#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Generate the workshop's sample loan documents as PNG images.

Run at bootstrap time (not committed as static assets) so that statement and
paystub dates are always fresh relative to the workshop day - date-based
validation rules ("paystub within 30 days", "statement covers 90 days") never
rot.

Personas:
  alice  - the golden path. Valid ID, recent paystub from a registered
           employer, 90-day statement with steady payroll deposits.
  bob    - the flagged path. Valid ID, paystub from an unregistered employer
           with income that does not match his statement deposits.
Extras:
  alice-statement-60d - covers only ~60 days: triggers NEEDS_RESUBMISSION.

Usage: python3 generate_docs.py [output_dir]
"""
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "sample-docs")

FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",            # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # linux
    "C:/Windows/Fonts/arial.ttf",                     # windows
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size, index=1 if (bold and path.endswith(".ttc")) else 0)
        except OSError:
            continue
    return ImageFont.load_default(size)


def canvas(w: int, h: int, color: str = "#ffffff") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (w, h), color)
    return img, ImageDraw.Draw(img)


def fmt(d: date) -> str:
    return d.strftime("%m/%d/%Y")


TODAY = date.today()


# ---------------------------------------------------------------------------
# Government ID
# ---------------------------------------------------------------------------

def make_id(path: Path, full_name: str, dob: str, id_number: str, expires: date) -> None:
    img, d = canvas(1000, 620, "#dfe9f5")
    d.rectangle([0, 0, 1000, 110], fill="#1d3557")
    d.text((40, 30), "STATE OF WORKSHOPIA", font=font(40, bold=True), fill="#ffffff")
    d.text((40, 78), "DRIVER LICENSE / IDENTIFICATION CARD", font=font(20), fill="#cfd8e3")
    # photo placeholder
    d.rectangle([40, 150, 300, 470], fill="#b8c4d4", outline="#5a6b80", width=3)
    d.text((105, 290), "PHOTO", font=font(34), fill="#5a6b80")
    rows = [
        ("4d NAME", full_name.upper()),
        ("3 DOB", dob),
        ("4a ISS", fmt(TODAY - timedelta(days=900))),
        ("4b EXP", fmt(expires)),
        ("5 DL NO", id_number),
        ("8 ADDR", "12 WORKSHOP LANE, CAPITAL CITY, WK 00001"),
    ]
    y = 150
    for label, value in rows:
        d.text((340, y), label, font=font(20), fill="#5a6b80")
        d.text((340, y + 26), value, font=font(30, bold=True), fill="#111111")
        y += 76
    d.text((40, 530), "WORKSHOPIA TRAINING SPECIMEN", font=font(20), fill="#a33")
    img.save(path)


# ---------------------------------------------------------------------------
# Paystub
# ---------------------------------------------------------------------------

def make_paystub(path: Path, full_name: str, employer: str, gross: float,
                 pay_date: date, ytd_periods: int) -> None:
    img, d = canvas(1000, 760, "#ffffff")
    d.rectangle([0, 0, 1000, 90], fill="#2a5d34")
    d.text((40, 24), employer.upper(), font=font(34, bold=True), fill="#ffffff")
    d.text((40, 62), "EARNINGS STATEMENT", font=font(18), fill="#d2e3d6")
    period_end = pay_date - timedelta(days=3)
    period_start = period_end - timedelta(days=13)
    info = [
        ("EMPLOYEE", full_name),
        ("PAY DATE", fmt(pay_date)),
        ("PAY PERIOD", f"{fmt(period_start)} - {fmt(period_end)}"),
        ("PAY FREQUENCY", "BIWEEKLY"),
    ]
    y = 120
    for label, value in info:
        d.text((40, y), label, font=font(18), fill="#666666")
        d.text((320, y), value, font=font(22, bold=True), fill="#111111")
        y += 44
    d.line([40, y + 10, 960, y + 10], fill="#cccccc", width=2)
    y += 40
    d.text((40, y), "EARNINGS", font=font(20, bold=True), fill="#2a5d34")
    y += 40
    taxes = round(gross * 0.24, 2)
    net = round(gross - taxes, 2)
    table = [
        ("Regular pay", f"${gross:,.2f}", f"${gross * ytd_periods:,.2f}"),
        ("Taxes & withholding", f"-${taxes:,.2f}", f"-${taxes * ytd_periods:,.2f}"),
        ("NET PAY", f"${net:,.2f}", f"${net * ytd_periods:,.2f}"),
    ]
    d.text((520, y - 40), "CURRENT", font=font(18), fill="#666666")
    d.text((760, y - 40), "YEAR TO DATE", font=font(18), fill="#666666")
    for name, cur, ytd in table:
        bold = name == "NET PAY"
        d.text((40, y), name, font=font(22, bold=bold), fill="#111111")
        d.text((520, y), cur, font=font(22, bold=bold), fill="#111111")
        d.text((760, y), ytd, font=font(22, bold=bold), fill="#111111")
        y += 46
    d.text((40, 700), "WORKSHOPIA TRAINING SPECIMEN", font=font(18), fill="#a33")
    img.save(path)


# ---------------------------------------------------------------------------
# Bank statement
# ---------------------------------------------------------------------------

def make_statement(path: Path, full_name: str, payroll_source: str,
                   deposit_net: float, days: int, opening: float) -> None:
    img, d = canvas(1000, 1350, "#ffffff")
    d.rectangle([0, 0, 1000, 90], fill="#134074")
    d.text((40, 24), "FIRST BANK OF WORKSHOPIA", font=font(32, bold=True), fill="#ffffff")
    d.text((40, 62), "ACCOUNT STATEMENT", font=font(18), fill="#c6d3e3")
    end = TODAY - timedelta(days=2)
    start = end - timedelta(days=days)
    d.text((40, 120), f"ACCOUNT HOLDER:  {full_name.upper()}", font=font(22, bold=True), fill="#111")
    d.text((40, 156), "ACCOUNT:  CHK ****4417", font=font(20), fill="#333")
    d.text((40, 192), f"STATEMENT PERIOD:  {fmt(start)} - {fmt(end)}", font=font(20), fill="#333")
    d.line([40, 240, 960, 240], fill="#cccccc", width=2)
    d.text((40, 260), "DATE", font=font(18), fill="#666")
    d.text((220, 260), "DESCRIPTION", font=font(18), fill="#666")
    d.text((700, 260), "AMOUNT", font=font(18), fill="#666")
    d.text((850, 260), "BALANCE", font=font(18), fill="#666")

    txns: list[tuple[date, str, float]] = []
    # biweekly payroll deposits across the period
    pay = start + timedelta(days=6)
    while pay <= end:
        txns.append((pay, f"ACH DEPOSIT {payroll_source.upper()} PAYROLL", deposit_net))
        pay += timedelta(days=14)
    # recurring spend
    rent_day = start + timedelta(days=3)
    while rent_day <= end:
        txns.append((rent_day, "ACH DEBIT CAPITAL CITY PROPERTIES RENT", -1450.00))
        rent_day += timedelta(days=30)
    misc_day = start + timedelta(days=9)
    i = 0
    misc = [("POS DEBIT GROCERY MART", -182.45), ("POS DEBIT FUEL STOP", -54.10),
            ("ACH DEBIT UTILITY CO", -138.20), ("POS DEBIT PHARMACY", -36.75)]
    while misc_day <= end:
        txns.append((misc_day, misc[i % len(misc)][0], misc[i % len(misc)][1]))
        misc_day += timedelta(days=11)
        i += 1
    txns.sort(key=lambda t: t[0])

    y = 300
    balance = opening
    for when, desc, amount in txns:
        balance += amount
        d.text((40, y), fmt(when), font=font(18), fill="#111")
        d.text((220, y), desc, font=font(18), fill="#111")
        color = "#2a7a2a" if amount > 0 else "#111"
        d.text((700, y), f"{amount:+,.2f}", font=font(18), fill=color)
        d.text((850, y), f"{balance:,.2f}", font=font(18), fill="#111")
        y += 34
    d.line([40, y + 6, 960, y + 6], fill="#cccccc", width=2)
    d.text((40, y + 24), f"OPENING BALANCE {fmt(start)}:  ${opening:,.2f}",
           font=font(20), fill="#333")
    d.text((40, y + 56), f"ENDING BALANCE {fmt(end)}:  ${balance:,.2f}",
           font=font(22, bold=True), fill="#111")
    d.text((40, 1300), "WORKSHOPIA TRAINING SPECIMEN", font=font(18), fill="#a33")
    img.save(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # --- Alice: golden path ---
    make_id(OUT / "alice-id.png", "Alice Anderson", "04/17/1991", "WK-DL-7741023",
            expires=TODAY + timedelta(days=730))
    # biweekly gross 3,300 -> ~85,800/yr; net per check ~2,508
    make_paystub(OUT / "alice-paystub.png", "Alice Anderson", "Mercy General Hospital",
                 gross=3300.00, pay_date=TODAY - timedelta(days=9),
                 ytd_periods=max(1, (TODAY.timetuple().tm_yday // 14)))
    make_statement(OUT / "alice-statement-90d.png", "Alice Anderson",
                   "Mercy General", deposit_net=2508.00, days=90, opening=6200.00)
    # only ~60 days: fails the 90-day coverage rule
    make_statement(OUT / "alice-statement-60d.png", "Alice Anderson",
                   "Mercy General", deposit_net=2508.00, days=60, opening=6200.00)

    # --- Bob: flagged path ---
    make_id(OUT / "bob-id.png", "Bob Baxter", "11/02/1985", "WK-DL-3390871",
            expires=TODAY + timedelta(days=365))
    # paystub claims 4,800 gross biweekly (~124k/yr) from an unregistered employer...
    make_paystub(OUT / "bob-paystub.png", "Bob Baxter", "Apex Fabrication Co",
                 gross=4800.00, pay_date=TODAY - timedelta(days=12),
                 ytd_periods=max(1, (TODAY.timetuple().tm_yday // 14)))
    # ...but his statement shows deposits consistent with ~1,900 net biweekly
    make_statement(OUT / "bob-statement-90d.png", "Bob Baxter",
                   "APX FAB", deposit_net=1900.00, days=90, opening=740.00)

    print(f"Wrote {len(list(OUT.glob('*.png')))} documents to {OUT}/")


if __name__ == "__main__":
    main()
