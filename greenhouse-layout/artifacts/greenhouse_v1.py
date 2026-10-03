"""온실 재배 구획 배치 계산기 — FastAPI 실습 과제.

설치: python -m pip install fastapi uvicorn
실행: python greenhouse.py
접속: http://127.0.0.1:8000

계산, SVG 배치도, HTML/CSS/JavaScript를 이 파일 하나에 포함했습니다.
외부 이미지, 인터넷 연결, 별도의 템플릿 파일이 필요하지 않습니다.
"""

from decimal import Decimal
from html import escape
from string import Template
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="온실 재배 구획 배치 계산기")
MAX_BEDS = 2500
Size = Annotated[Decimal, Query(ge=Decimal("0.01"), le=1000, decimal_places=4)]
PathSize = Annotated[Decimal, Query(ge=0, le=1000, decimal_places=4)]


def fmt(value):
    """불필요한 소수점 0 없이 숫자를 표시합니다."""
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def row_name(index):
    """0 → A, 25 → Z, 26 → AA 형태의 행 이름입니다."""
    result = ""
    while index >= 0:
        result = chr(65 + index % 26) + result
        index = index // 26 - 1
    return result


def calculate_layout(width, length, bed_width, bed_length, path):
    """구획 사이에만 통로를 놓습니다. Decimal로 경계값 오차를 피합니다."""
    width, length, bed_width, bed_length, path = (
        Decimal(str(v)) for v in (width, length, bed_width, bed_length, path)
    )
    if not all(v.is_finite() for v in (width, length, bed_width, bed_length, path)):
        raise ValueError("유한한 숫자를 입력해 주세요.")
    if min(width, length, bed_width, bed_length) <= 0 or path < 0:
        raise ValueError("크기는 0보다 크게, 통로 폭은 0 이상으로 입력해 주세요.")
    columns = int((width + path) // (bed_width + path))
    rows = int((length + path) // (bed_length + path))
    count = columns * rows
    if count > MAX_BEDS:
        raise ValueError(f"한 화면에는 최대 {MAX_BEDS:,}개 구획을 표시할 수 있어요. 구획 크기를 늘려 주세요.")
    # 어느 한 방향에도 들어가지 않으면 전체 면적을 미배치 공간으로 처리합니다.
    if count == 0:
        columns = rows = 0
    used_width = columns * bed_width + max(columns - 1, 0) * path
    used_length = rows * bed_length + max(rows - 1, 0) * path
    total_area = width * length
    bed_area = count * bed_width * bed_length
    path_area = used_width * used_length - bed_area
    unused_area = total_area - bed_area - path_area
    return dict(width=width, length=length, bed_width=bed_width, bed_length=bed_length,
                path=path, columns=columns, rows=rows, count=count,
                used_width=used_width, used_length=used_length,
                total_area=total_area, bed_area=bed_area, path_area=path_area,
                unused_area=unused_area, rate=bed_area / total_area * 100)


def make_svg(data):
    """동일한 축척으로 온실, 구획, 통로, 남는 공간을 그립니다."""
    w, h, bw, bh, path = (float(data[k]) for k in
                          ("width", "length", "bed_width", "bed_length", "path"))
    scale = min(580 / w, 455 / h)
    sw, sh = w * scale, h * scale
    x, y = (820 - sw) / 2, (575 - sh) / 2 + 10
    uw, uh = float(data["used_width"]) * scale, float(data["used_length"]) * scale
    sbw, sbh = bw * scale, bh * scale
    # 작은 구획에서는 장식과 번호를 생략합니다. 작물 장식은 식재 수가 아닙니다.
    detail = min(sbw, sbh) >= 17 and data["count"] <= 350
    labels = min(sbw, sbh) >= 22 and data["count"] <= 350
    rounding = min(3.5, sbw * .09, sbh * .09)
    out = [f'''<svg id="plan-svg" viewBox="0 0 820 610" xmlns="http://www.w3.org/2000/svg"
        data-fit-width="{sw+140:.4f}" data-fit-height="{sh+120:.4f}"
        data-center-x="{x+sw/2:.4f}" data-center-y="{y+sh/2:.4f}"
        role="group" aria-labelledby="plan-title plan-desc">
      <title id="plan-title">온실 재배 구획 배치도</title>
      <desc id="plan-desc">{fmt(data['width'])}m × {fmt(data['length'])}m 온실.
        가로 {data['columns']}개, 세로 {data['rows']}개, 총 {data['count']}개 구획.
        외곽 여유 공간 없이 구획 사이에만 통로를 배치합니다.</desc>
      <defs>
        <pattern id="unused" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="7" height="7" fill="#f0f1eb"/><path d="M0 0V7" stroke="#d1d6cc" stroke-width="2"/>
        </pattern>
        <pattern id="plants" width="22" height="24" patternUnits="userSpaceOnUse">
          <path d="M11 17V8" stroke="#396b45" stroke-width="1"/>
          <ellipse cx="7.5" cy="9.5" rx="3" ry="5" transform="rotate(-40 7.5 9.5)" fill="#8eaf6c"/>
          <ellipse cx="14" cy="8" rx="3" ry="5" transform="rotate(40 14 8)" fill="#afc68a"/>
        </pattern>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#273f2e" flood-opacity=".10"/>
        </filter>
      </defs>
      <g id="drawing">
      <rect x="{x-5:.4f}" y="{y-5:.4f}" width="{sw+10:.4f}" height="{sh+10:.4f}"
        rx="3" fill="#fafbf6" stroke="#355746" stroke-width="2" filter="url(#shadow)"/>
      <rect x="{x:.4f}" y="{y:.4f}" width="{sw:.4f}" height="{sh:.4f}" fill="url(#unused)"/>
      <rect x="{x:.4f}" y="{y:.4f}" width="{uw:.4f}" height="{uh:.4f}" fill="#e9dfc9"/>
      <g class="dimensions" stroke="#8b9b8c" stroke-width="1" fill="none">
        <path d="M{x:.4f},{y-17:.4f}V{y-42:.4f} M{x+sw:.4f},{y-17:.4f}V{y-42:.4f}
          M{x:.4f},{y-33:.4f}H{x+sw:.4f}"/>
        <path d="M{x-2:.4f},{y-30:.4f}l4,-6 M{x+sw-2:.4f},{y-30:.4f}l4,-6"/>
        <path d="M{x-17:.4f},{y:.4f}H{x-42:.4f} M{x-17:.4f},{y+sh:.4f}H{x-42:.4f}
          M{x-33:.4f},{y:.4f}V{y+sh:.4f}"/>
        <path d="M{x-36:.4f},{y+2:.4f}l6,-4 M{x-36:.4f},{y+sh+2:.4f}l6,-4"/>
      </g>
      <g class="dimension-label" fill="#576b5d" font-size="12" font-weight="600" text-anchor="middle">
        <rect x="{x+sw/2-38:.4f}" y="{y-42:.4f}" width="76" height="18" fill="#f7f8f2"/>
        <text x="{x+sw/2:.4f}" y="{y-29:.4f}">{fmt(data['width'])} m</text>
        <g transform="translate({x-33:.4f},{y+sh/2:.4f}) rotate(-90)">
          <rect x="-38" y="-10" width="76" height="18" fill="#f7f8f2"/>
          <text y="4">{fmt(data['length'])} m</text>
        </g>
      </g>''']
    for row in range(data["rows"]):
        for col in range(data["columns"]):
            px = x + col * (bw + path) * scale
            py = y + row * (bh + path) * scale
            name = f"{row_name(row)}{col+1:02d}"
            out.append(f'''<g class="bed" data-name="{name}" tabindex="0" role="button"
                aria-label="구획 {name}, {fmt(data['bed_width'])} × {fmt(data['bed_length'])}미터" aria-pressed="false">
              <title>{name} · {fmt(data['bed_width'])} × {fmt(data['bed_length'])} m · {fmt(data['bed_width']*data['bed_length'])} ㎡</title>
              <rect class="bed-fill" x="{px:.4f}" y="{py:.4f}" width="{sbw:.4f}" height="{sbh:.4f}"
                rx="{rounding:.4f}" fill="{'#648b59' if (row+col)%2 == 0 else '#719560'}" stroke="#446d42" stroke-width=".8"/>''')
            if detail:
                out.append(f'''<rect x="{px+2:.4f}" y="{py+2:.4f}" width="{max(0,sbw-4):.4f}"
                    height="{max(0,sbh-4):.4f}" rx="{rounding:.4f}" fill="url(#plants)" pointer-events="none"/>''')
            if labels:
                fs = min(10, sbw / 2.9)
                label_width = min(28, sbw - 2)
                out.append(f'''<rect x="{px+sbw/2-label_width/2:.4f}" y="{py+sbh/2-8:.4f}" width="{label_width:.4f}" height="16" rx="4" fill="#254a37" fill-opacity=".88" pointer-events="none"/>
                  <text x="{px+sbw/2:.4f}" y="{py+sbh/2+3:.4f}" text-anchor="middle" fill="#fff" font-size="{fs:.2f}" font-weight="600" pointer-events="none">{name}</text>''')
            out.append("</g>")
    if data["count"]:
        out.append(f'''<text class="plan-caption" x="{x+sw/2:.4f}" y="{y+sh+30:.4f}" text-anchor="middle" fill="#65786a" font-size="11">
          가로 {data['columns']}개 × 세로 {data['rows']}개 · 통로 {fmt(data['path'])} m</text>''')
    out.append("</g></svg>")
    return "".join(out)


# 화면의 아이콘도 SVG로 작성하여 외부 파일 없이 실행합니다.
LEAF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21V11M12 14C5 15 3 10 3 5c6-1 10 2 9 9ZM12 11c-1-6 3-9 9-9 0 6-3 10-9 9Z"/></svg>'
GRID = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'

PAGE = Template(r'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#234b39">
<title>온실 재배 구획 배치 계산기 · 온실연구실</title>
<style>
:root{--ink:#243d31;--muted:#788377;--green:#285940;--line:#e2e7dc;--paper:#f6f7f2;--sand:#e9dfc9}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Pretendard","Malgun Gothic","Apple SD Gothic Neo",sans-serif;font-size:14px;letter-spacing:-.025em}
button,input,a{font:inherit}button,a,input{ -webkit-tap-highlight-color:transparent}button,a{touch-action:manipulation}button{cursor:pointer}a{color:inherit;text-decoration:none}svg{display:block}button:focus-visible,a:focus-visible,input:focus-visible,[role=button]:focus-visible{outline:3px solid #be973f;outline-offset:3px}button:disabled{cursor:default;opacity:.35}
.topbar{height:78px;background:#fcfdf9;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 42px}
.brand{display:flex;align-items:center;gap:12px;font-size:19px;font-weight:750}.brand-mark{background:var(--ink);color:#d6e7b3;padding:9px;border-radius:12px}.brand-mark svg{width:23px;height:23px}.brand small{margin-left:8px;border-left:1px solid #d7ddd2;padding-left:19px;font-size:12px;letter-spacing:.11em;font-weight:500;color:var(--muted)}
.top-right{display:flex;align-items:center;gap:24px;color:var(--muted);font-size:12px}.status{display:flex;gap:7px;align-items:center}.status i{width:6px;height:6px;background:#709654;border-radius:50%}.top-right a{border-bottom:1px solid #aab8a7;padding-bottom:3px}
main{max-width:1536px;margin:auto;padding:34px 42px 25px}.intro{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:28px}.eyebrow{font-size:10px;font-weight:700;letter-spacing:.19em;color:#6f846c;margin:0 0 11px}.intro h1{font-size:29px;line-height:1.3;letter-spacing:-1.3px;margin:0 0 9px;font-weight:700}.intro p{margin:0;color:var(--muted);font-size:13px}.project-id{font-family:Consolas,monospace;font-size:11px;color:#8a9788;border:1px solid var(--line);padding:9px 12px;border-radius:6px}
.workspace{display:grid;grid-template-columns:282px minmax(0,1fr);gap:24px;align-items:start}.sidebar{background:#fcfdf9;border:1px solid var(--line);border-radius:15px;overflow:hidden}.sidebar-heading{padding:23px 22px 19px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.sidebar-heading h2{font-size:15px;margin:0}.sidebar-heading span{font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:3px 6px}
.form-body{padding:22px}.field-section+.field-section{margin-top:24px;padding-top:21px;border-top:1px solid var(--line)}.section-label{display:flex;align-items:center;gap:8px;margin:0 0 16px;font-weight:700;font-size:12px}.step{color:#7b9075;font-family:Consolas,monospace;font-size:10px}.input-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{display:block;font-size:11px;color:#728071;margin-bottom:7px}.input-wrap{position:relative}.input-wrap input{width:100%;border:1px solid #dfe5d8;border-radius:7px;background:white;padding:10px 29px 10px 11px;color:var(--ink);font-size:17px;font-weight:600;font-variant-numeric:tabular-nums;appearance:textfield;-moz-appearance:textfield}.input-wrap input::-webkit-inner-spin-button{appearance:none}.input-wrap input:focus{border-color:#789971;outline:2px solid #d8e6cf}.input-wrap span{position:absolute;right:12px;top:14px;color:#8c9788;font-size:11px;pointer-events:none}.field-note{font-size:11px;line-height:1.7;color:#8b9587;margin:10px 0 0}.apply{border:0;border-radius:8px;background:var(--green);color:#fff;padding:13px 14px;display:flex;align-items:center;justify-content:space-between;width:100%;font-weight:600;margin-top:25px;transition:background .2s}.apply:hover{background:#173f2b}.apply span{font-size:19px;line-height:1}.reset{display:block;width:100%;text-align:center;color:#7c8b77;font-size:11px;margin-top:14px;padding:4px}.assumptions{background:#eef2e8;border-top:1px solid #e1e7d9;padding:19px 22px}.assumptions h3{font-size:11px;margin:0 0 8px;color:#5d7656}.assumptions p{font-size:11px;color:#7c8b72;line-height:1.85;margin:0}.support-note{font-size:11px;color:#8c9787;line-height:1.8;margin:16px 8px}
.results{min-width:0}.metrics{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:19px}.metric{background:#fcfdf9;border:1px solid var(--line);border-radius:12px;padding:18px 21px;min-height:112px;position:relative}.metric:first-child{background:#244c39;color:#fafcf4;border-color:#244c39}.metric-label{font-size:11px;color:#788974}.metric:first-child .metric-label{color:#c0d1b7}.metric strong{font-family:Arial,"Malgun Gothic",sans-serif;display:inline-block;font-size:33px;letter-spacing:-1.5px;font-weight:500;margin-top:8px;line-height:1.1}.metric .unit{font-size:13px;margin-left:6px;opacity:.65}.metric small{display:block;color:#8f9c88;font-size:10px;margin-top:9px}.metric:first-child small{color:#afc4a4}.metric-icon{position:absolute;right:18px;top:18px;opacity:.45}.metric-icon svg{width:16px;height:16px}.mini-bar{height:3px;background:#e8edde;margin-top:14px;border-radius:4px;overflow:hidden}.mini-bar span{height:100%;background:#7e9b61;display:block;width:$rate%}
.plan-card{background:#fcfdf9;border:1px solid var(--line);border-radius:15px;overflow:hidden}.plan-heading{padding:19px 22px;display:flex;justify-content:space-between;gap:12px;align-items:center;border-bottom:1px solid var(--line)}.plan-heading h2{font-size:14px;margin:0;display:flex;align-items:center;gap:9px}.plan-heading h2 svg{width:16px;height:16px;color:#769068}.plan-heading p{font-size:10px;color:#91a087;margin:5px 0 0 25px}.view-tag{font-size:10px;padding:6px 9px;background:#f0f4e9;color:#708666;border-radius:5px;white-space:nowrap}.canvas{position:relative;background-color:#f7f8f2;background-image:radial-gradient(#dce2d6 .7px,transparent .7px);background-size:18px 18px;overflow:hidden;height:535px;touch-action:none}.canvas #plan-svg{width:100%;height:100%;user-select:none}.canvas-label{position:absolute;top:24px;left:24px;pointer-events:none;z-index:1}.canvas-label b{font-family:Consolas,monospace;letter-spacing:1.6px;font-size:10px;color:#627c60}.canvas-label span{display:block;color:#96a18e;font-size:9px;margin-top:7px}.orientation{position:absolute;right:25px;top:22px;display:flex;flex-direction:column;align-items:center;color:#87967e;font-size:9px;gap:6px;pointer-events:none}.orientation svg{width:19px;height:30px}.orientation span{writing-mode:vertical-rl;letter-spacing:3px}.canvas-hint{position:absolute;bottom:19px;left:22px;font-size:10px;color:#8c9a82;pointer-events:none}.zoom-tools{position:absolute;bottom:15px;right:18px;background:#fcfdf9;border:1px solid #dce4d3;border-radius:8px;display:flex;align-items:center;padding:3px;box-shadow:0 2px 5px #23432408}.zoom-tools button{border:0;background:transparent;color:#57754c;height:29px;min-width:29px;border-radius:4px;font-size:17px}.zoom-tools button:hover{background:#eef3e7}.zoom-tools output{font-family:Consolas,monospace;width:44px;text-align:center;font-size:10px;color:#89957f}.zoom-tools .fit{font-size:10px;padding:0 10px;border-left:1px solid var(--line);margin-left:3px;border-radius:0}.bed{cursor:pointer;outline:none}.bed .bed-fill{transition:stroke .15s,filter .15s}.bed:hover .bed-fill,.bed:focus-visible .bed-fill{stroke:#dbb653;stroke-width:2.3;filter:brightness(1.12)}.bed.selected .bed-fill{stroke:#f3ce6b;stroke-width:3;filter:brightness(1.09)}
.plan-bottom{display:flex;justify-content:space-between;gap:14px;padding:15px 22px;border-top:1px solid var(--line);align-items:center;flex-wrap:wrap}.legend{display:flex;gap:17px;color:#788970;font-size:10px}.legend span{display:flex;gap:6px;align-items:center}.swatch{width:9px;height:9px;border-radius:2px;display:inline-block}.swatch.green{background:#719560}.swatch.sand{background:var(--sand);border:1px solid #d7cfba}.swatch.hatch{background:repeating-linear-gradient(135deg,#f0f1eb,#f0f1eb 2px,#d1d6cc 2px,#d1d6cc 3px);border:1px solid #d1d6cc}.download{border:0;background:transparent;color:#627c57;font-size:10px;padding:4px;display:flex;gap:6px;align-items:center}.download svg{width:13px;height:13px}
.selection{margin-top:14px;border:1px solid var(--line);border-radius:11px;display:flex;align-items:center;gap:15px;background:#fcfdf9;padding:15px 19px;min-height:67px}.selection-icon{width:32px;height:32px;background:#edf2e6;display:flex;align-items:center;justify-content:center;color:#759664;border-radius:8px;flex:none}.selection-icon svg{width:17px;height:17px}.selection-text{flex:1;min-width:0}.selection-text strong{font-size:12px;font-weight:600;display:block}.selection-text p{font-size:10px;color:#8b9782;margin:5px 0 0}.selection-dim{font-size:12px;font-family:Consolas,"Malgun Gothic",monospace;color:#66805d;text-align:right}.selection-dim small{display:block;font-family:"Malgun Gothic",sans-serif;font-size:9px;color:#98a18e;margin-top:5px}.area-summary{display:flex;gap:22px;font-size:10px;color:#8c9785;margin:14px 2px}.area-summary b{color:#677b5d;font-weight:500;margin-left:5px}.empty-state{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);padding:23px;text-align:center;max-width:320px;width:85%;background:#fcfdf9f2;border:1px solid var(--line);border-radius:10px}.empty-state strong{display:block;font-size:14px}.empty-state p{font-size:12px;color:#819177;line-height:1.8;margin:8px 0 0}
.footer{margin-top:24px;padding-top:17px;border-top:1px solid var(--line);display:flex;justify-content:space-between;font-size:10px;color:#99a18f}.footer b{font-weight:500;color:#6e8265}.dirty-note{color:#a1772d;font-size:11px;line-height:1.7;margin:11px 0 0}.error-wrap{max-width:600px;padding:40px;margin:12vh auto;background:#fcfdf9;border:1px solid var(--line);border-radius:14px}.error-wrap h1{font-size:24px}.error-wrap p,.error-wrap li{line-height:1.9;color:#73816b}.error-wrap a{display:inline-block;background:var(--green);color:white;padding:12px 20px;border-radius:7px;margin-top:12px}
@media(min-width:1450px){.canvas{height:585px}}
@media(max-width:1100px){main{padding:25px 24px}.topbar{padding:0 24px}.workspace{grid-template-columns:250px minmax(0,1fr);gap:18px}.form-body{padding:20px}.metric{padding:17px 15px}.metric strong{font-size:28px}.metric-icon{display:none}.canvas{height:500px}.canvas-label span{display:none}.canvas-label{top:17px;left:17px}.orientation{right:17px;top:17px}}
@media(max-width:800px){.brand small,.status,.project-id{display:none}.topbar{height:65px}.intro{margin-bottom:23px}.intro h1{font-size:24px}.intro p{font-size:12px;line-height:1.7}.workspace{grid-template-columns:1fr}.sidebar-heading{padding:16px 20px}.form-body{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:18px}.field-section+.field-section{margin:0;padding:0;border:0}.field-section:nth-child(3){grid-column:1/2}.form-actions{display:flex;flex-direction:column;justify-content:center}.apply{margin-top:0}.reset{margin-top:9px}.field-note{font-size:10px}.assumptions{padding:13px 18px}.assumptions h3{display:inline;margin-right:9px}.assumptions p{display:inline}.support-note{display:none}.canvas{height:540px}.metrics{gap:9px}.metric{padding:16px 13px}.metric strong{font-size:28px}.plan-heading{padding:17px}.footer{gap:12px;line-height:1.7}.area-summary{flex-wrap:wrap;gap:9px 17px}}
@media(max-width:450px){main{padding:24px 14px}.topbar{padding:0 17px}.top-right{font-size:10px}.metric{min-height:114px;padding:14px 11px}.metric-label{font-size:10px}.metric strong{font-size:25px}.metric small{font-size:9px}.metric .unit{font-size:10px;margin-left:4px}.canvas{height:490px}.canvas-label{font-size:9px}.canvas-hint{display:none}.plan-bottom{padding:14px}.legend{gap:10px;font-size:9px}.selection{padding:13px;gap:10px}.selection-dim{font-size:11px}.view-tag{font-size:9px}.intro h1{font-size:23px}.plan-heading p{font-size:9px}.footer span:last-child{display:none}}
@media(max-width:450px){.canvas-label,.plan-caption{display:none}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
@media print{.sidebar,.top-right,.zoom-tools,.download,.canvas-hint,.form-actions{display:none}.workspace{display:block}.topbar{height:55px}main{padding:20px}.canvas{height:600px}.plan-card,.metrics{break-inside:avoid}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style>
</head>
<body>
<header class="topbar"><a class="brand" href="/" aria-label="온실연구실 처음으로"><span class="brand-mark">$leaf</span>온실연구실<small>GREENHOUSE LAB</small></a><div class="top-right"><span class="status"><i></i>재배 공간을 설계하는 작은 도구</span><a href="#conditions">배치 기준 ↗</a></div></header>
<main>
<section class="intro"><div><div class="eyebrow">PLAN YOUR GROWING SPACE</div><h1>온실 재배 구획 배치 계산기</h1><p>온실의 크기부터 통로까지, 나의 재배 공간을 한눈에 그려보세요.</p></div><span class="project-id">LAYOUT / 01</span></section>
<div class="workspace">
<aside><section class="sidebar"><div class="sidebar-heading"><h2>공간 설정</h2><span>단위 m</span></div>
<form action="/layout" method="get" id="layout-form"><div class="form-body">
<div class="field-section"><h3 class="section-label"><span class="step">01</span>온실 크기</h3><div class="input-row"><div><label for="width">가로 길이</label><div class="input-wrap"><input id="width" name="width" type="number" min="0.01" max="1000" step="0.0001" value="$width" required><span>m</span></div></div><div><label for="length">세로 길이</label><div class="input-wrap"><input id="length" name="length" type="number" min="0.01" max="1000" step="0.0001" value="$length" required><span>m</span></div></div></div></div>
<div class="field-section"><h3 class="section-label"><span class="step">02</span>재배 구획 크기</h3><div class="input-row"><div><label for="bed_width">구획 가로</label><div class="input-wrap"><input id="bed_width" name="bed_width" type="number" min="0.01" max="1000" step="0.0001" value="$bed_width" required><span>m</span></div></div><div><label for="bed_length">구획 세로</label><div class="input-wrap"><input id="bed_length" name="bed_length" type="number" min="0.01" max="1000" step="0.0001" value="$bed_length" required><span>m</span></div></div></div><p class="field-note">같은 크기의 구획을 일정한 방향으로 배치해요.</p></div>
<div class="field-section"><h3 class="section-label"><span class="step">03</span>이동 공간</h3><label for="path">구획 사이 통로 폭</label><div class="input-wrap"><input id="path" name="path" type="number" min="0" max="1000" step="0.0001" value="$path" required><span>m</span></div><p class="field-note">가로·세로 구획 사이에 동일하게 적용해요.</p></div>
<div class="form-actions"><button class="apply" type="submit">배치 계산하기<span aria-hidden="true">→</span></button><a class="reset" href="/">기본값으로 되돌리기</a><p id="dirty-note" class="dirty-note" hidden>값을 변경했어요. 계산하기를 누르면 배치도에 반영돼요.</p></div>
</div></form>
<div class="assumptions" id="conditions"><h3>배치 기준 안내</h3><p>구획 사이에만 통로를 배치합니다.<br>외곽 통로·출입구·기둥은 포함하지 않습니다.<br>구획 회전 없이 좌측 상단부터 배치합니다.</p></div></section><p class="support-note">크기 0.01–1,000 m · 통로 0–1,000 m<br>소수점 넷째 자리까지 · 최대 2,500개 구획<br>작물 모양은 장식이며 식재 수를 뜻하지 않아요.</p></aside>
<section class="results" aria-label="배치 계산 결과">
<div class="metrics"><article class="metric"><span class="metric-label">배치 가능한 구획</span><span class="metric-icon">$grid</span><div><strong id="count-value">$count</strong><span class="unit">개</span></div><small>가로 $columns개 × 세로 $rows개</small></article><article class="metric"><span class="metric-label">실제 재배 면적</span><div><strong id="area-value">$bed_area</strong><span class="unit">㎡</span></div><small>전체 온실 $total_area ㎡</small></article><article class="metric"><span class="metric-label">재배 면적 비율</span><div><strong id="rate-value">$rate</strong><span class="unit">%</span></div><div class="mini-bar"><span></span></div></article></div>
<section class="plan-card"><div class="plan-heading"><div><h2>$grid 재배 공간 배치도</h2><p>실제 치수 비율을 반영한 평면도</p></div><span class="view-tag">위에서 본 모습 · 2D</span></div>
<div class="canvas" id="canvas"><div class="canvas-label"><b>GREENHOUSE / 01</b><span>$width × $length m &nbsp; · &nbsp; $total_area ㎡</span></div><div class="orientation"><svg viewBox="0 0 20 30" aria-hidden="true"><path d="M10 2L3 16h7z" fill="#7d9070"/><path d="M10 2l7 14h-7z" fill="#c0ccae"/><path d="M10 16v12" stroke="#7d9070"/></svg><span>세로 방향</span></div>
$svg $empty
<span class="canvas-hint">구획을 선택해 자세히 살펴보세요</span><div class="zoom-tools" role="group" aria-label="배치도 확대 축소"><button id="zoom-out" type="button" aria-label="축소">−</button><output id="zoom-value" aria-live="polite">100%</output><button id="zoom-in" type="button" aria-label="확대">+</button><button id="zoom-fit" class="fit" type="button">화면 맞춤</button></div></div>
<div class="plan-bottom"><div class="legend" aria-label="배치도 범례"><span><i class="swatch green"></i>재배 구획</span><span><i class="swatch sand"></i>통로</span><span><i class="swatch hatch"></i>남는 공간</span></div><button class="download" id="download" type="button"><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M10 2v10m-4-4 4 4 4-4M3 13v4h14v-4"/></svg>배치도 저장</button></div></section>
<section class="selection" aria-live="polite"><div class="selection-icon">$leaf</div><div class="selection-text"><strong id="selected-title">$selection_title</strong><p id="selected-detail">$selection_detail</p></div><div class="selection-dim">$bed_width × $bed_length m<small>구획 1개 기준 · $single_area ㎡</small></div></section>
<div class="area-summary"><span>통로 면적<b>$path_area ㎡</b></span><span>남는 면적<b>$unused_area ㎡</b></span><span>전체 면적<b>$total_area ㎡</b></span></div>
</section></div>
<footer class="footer"><span><b>온실연구실</b> &nbsp; / &nbsp; 작은 설계로 시작하는 나의 온실</span><span>동일 방향 격자 배치 · 실제 시공 전 현장 조건 확인</span></footer>
</main>
<script>
// 계산은 FastAPI가 수행합니다. JavaScript는 선택·확대 등 화면 조작만 담당합니다.
const svg=document.getElementById('plan-svg');
const canvas=document.getElementById('canvas');
let selected=null, zoom=1, offsetX=0, offsetY=0, drag=null, dragged=false;
let baseWidth=820,baseHeight=610;
const centerX=Number(svg.dataset.centerX),centerY=Number(svg.dataset.centerY);
function selectBed(bed){
 if(selected){selected.classList.remove('selected');selected.setAttribute('aria-pressed','false');}
 selected=bed;bed.classList.add('selected');bed.setAttribute('aria-pressed','true');
 document.getElementById('selected-title').textContent='구획 '+bed.dataset.name+' 선택됨';
 document.getElementById('selected-detail').textContent='가로 $bed_width m × 세로 $bed_length m · 재배 면적 $single_area ㎡';
}
svg.addEventListener('click',function(e){const bed=e.target.closest('.bed');if(bed&&!dragged)selectBed(bed);});
svg.addEventListener('keydown',function(e){const bed=e.target.closest('.bed');if(bed&&(e.key==='Enter'||e.key===' ')){e.preventDefault();selectBed(bed);}});
function applyView(){
 const aspect=canvas.clientWidth/canvas.clientHeight;
 const fitHeight=Number(svg.dataset.fitHeight)+(canvas.clientWidth<450?40:0);
 baseWidth=Math.max(Number(svg.dataset.fitWidth),fitHeight*aspect);
 baseHeight=baseWidth/aspect;
 const vw=baseWidth/zoom,vh=baseHeight/zoom;
 offsetX=Math.max(-(baseWidth-vw)/2,Math.min((baseWidth-vw)/2,offsetX));
 offsetY=Math.max(-(baseHeight-vh)/2,Math.min((baseHeight-vh)/2,offsetY));
 svg.setAttribute('viewBox',[centerX-vw/2+offsetX,centerY-vh/2+offsetY,vw,vh].join(' '));
 document.getElementById('zoom-value').textContent=Math.round(zoom*100)+'%';
 document.getElementById('zoom-out').disabled=zoom<=1;
 document.getElementById('zoom-in').disabled=zoom>=4;
 canvas.style.cursor=zoom>1?'grab':'default';
}
document.getElementById('zoom-in').addEventListener('click',()=>{zoom=Math.min(4,zoom+.25);applyView();});
document.getElementById('zoom-out').addEventListener('click',()=>{zoom=Math.max(1,zoom-.25);applyView();});
document.getElementById('zoom-fit').addEventListener('click',()=>{zoom=1;offsetX=offsetY=0;applyView();});
svg.addEventListener('pointerdown',function(e){
 dragged=false;if(zoom<=1||e.button!==0)return;
 drag={x:e.clientX,y:e.clientY,ox:offsetX,oy:offsetY};
});
svg.addEventListener('pointermove',function(e){
 if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
 if(Math.abs(dx)+Math.abs(dy)>5){dragged=true;svg.setPointerCapture(e.pointerId);}
 if(!dragged)return;
 const m=svg.getScreenCTM();offsetX=drag.ox-dx/m.a;offsetY=drag.oy-dy/m.d;applyView();canvas.style.cursor='grabbing';
});
svg.addEventListener('pointerup',()=>{drag=null;applyView();});
svg.addEventListener('pointercancel',()=>{drag=null;applyView();});
svg.addEventListener('pointerleave',()=>{if(!dragged)drag=null;});
applyView();
new ResizeObserver(applyView).observe(canvas);
document.getElementById('layout-form').addEventListener('input',()=>{document.getElementById('dirty-note').hidden=false;});
document.getElementById('download').addEventListener('click',function(){
 const clone=svg.cloneNode(true);clone.setAttribute('viewBox','0 0 820 610');clone.setAttribute('width','820');clone.setAttribute('height','610');
 clone.setAttribute('style','background:#f7f8f2;font-family:Malgun Gothic,Arial,sans-serif');
 clone.querySelectorAll('.bed').forEach(b=>{b.removeAttribute('tabindex');b.removeAttribute('role');b.removeAttribute('aria-pressed');});
 const ns='http://www.w3.org/2000/svg';const bg=document.createElementNS(ns,'rect');bg.setAttribute('width','820');bg.setAttribute('height','610');bg.setAttribute('fill','#f7f8f2');clone.insertBefore(bg,clone.firstChild);
 const title=document.createElementNS(ns,'text');title.setAttribute('x','20');title.setAttribute('y','25');title.setAttribute('fill','#355746');title.setAttribute('font-size','12');title.textContent='온실 재배 구획 배치도 · $width × $length m · $count개 구획';clone.appendChild(title);
 const note=document.createElementNS(ns,'text');note.setAttribute('x','20');note.setAttribute('y','596');note.setAttribute('fill','#65786a');note.setAttribute('font-size','10');note.textContent='녹색: 재배 구획 · 모래색: 통로 · 사선: 남는 공간 | 외곽 통로·출입구·기둥 미포함';clone.appendChild(note);
 const blob=new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='greenhouse-layout.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
</script></body></html>''')


def render_page(data):
    values = {key: fmt(value) if isinstance(value, Decimal) else f"{value:,}"
              for key, value in data.items()}
    # 입력 칸과 JS에는 천 단위 쉼표 없는 숫자를 넣습니다.
    values.update({key: str(data[key]) for key in ("width", "length", "bed_width", "bed_length", "path")})
    values["rate"] = f"{data['rate']:.1f}"
    values.update(leaf=LEAF, grid=GRID, svg=make_svg(data),
                  single_area=fmt(data["bed_width"] * data["bed_length"]),
                  selection_title="어떤 구획을 살펴볼까요?" if data["count"] else "구획 크기를 조정해 주세요",
                  selection_detail="배치도의 구획을 클릭하면 크기와 면적을 확인할 수 있어요." if data["count"] else "온실보다 작은 구획으로 변경한 뒤 다시 계산해 보세요.",
                  empty="" if data["count"] else '<div class="empty-state"><strong>배치 가능한 구획이 없습니다</strong><p>온실보다 구획이 커요.<br>온실 또는 구획 크기를 조정해 주세요.</p></div>')
    return PAGE.substitute(values)


def error_page(message):
    # 사용자 입력이나 오류 문구를 그대로 HTML로 삽입하지 않습니다.
    return HTMLResponse(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <title>입력값을 확인해 주세요 · 온실연구실</title><body style="margin:0;background:#f6f7f2;color:#243d31;font-family:Malgun Gothic,sans-serif">
      <main style="max-width:560px;margin:12vh auto;padding:35px;background:#fff;border:1px solid #e2e7dc;border-radius:15px">
      <p style="font-size:12px;color:#748b6e">온실연구실 / 입력 안내</p><h1 style="font-size:24px">입력값을 확인해 주세요</h1>
      <p style="line-height:1.9">{escape(message)}</p><p style="font-size:13px;line-height:1.9;color:#748b6e">크기: 0.01–1,000 m · 통로: 0–1,000 m<br>소수점 넷째 자리까지 입력할 수 있어요.</p>
      <button onclick="history.back()" style="padding:11px 16px;cursor:pointer">이전 화면</button>
      <a href="/" style="display:inline-block;padding:12px 16px;color:#285940">기본 배치로 돌아가기 →</a></main></body></html>''', status_code=422)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    names = {"width": "온실 가로", "length": "온실 세로", "bed_width": "구획 가로", "bed_length": "구획 세로", "path": "통로 폭"}
    fields = list(dict.fromkeys(names.get(str(error["loc"][-1]), "입력값") for error in exc.errors()))
    return error_page(", ".join(fields) + " 값을 확인해 주세요. 허용 범위 안의 숫자를 입력해야 합니다.")


@app.get("/", response_class=HTMLResponse)
@app.get("/layout", response_class=HTMLResponse)
def layout(width: Size = Decimal("10"), length: Size = Decimal("20"),
           bed_width: Size = Decimal("1"), bed_length: Size = Decimal("4"),
           path: PathSize = Decimal("0.5")):
    """주소창의 GET 매개변수를 받아 계산 결과와 SVG 배치도를 반환합니다."""
    try:
        data = calculate_layout(width, length, bed_width, bed_length, path)
    except ValueError as exc:
        return error_page(str(exc))
    return HTMLResponse(render_page(data))


if __name__ == "__main__":
    print("온실 재배 구획 배치 계산기: http://127.0.0.1:8000", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000)
