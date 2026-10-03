"""온실연구실 — FastAPI 온실 배치 계산기.

python -m pip install fastapi uvicorn
python greenhouse.py  →  http://127.0.0.1:8000

계산, HTML/CSS/JS, SVG, 발표용 보고서를 이 파일에 포함합니다.
네트워크나 외부 이미지·폰트 없이 실행합니다.
"""
from decimal import Decimal
from html import escape
from string import Template
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, Response
import uvicorn

app = FastAPI(title="온실연구실 · 배치 비교", version="2.0")
MAX_BEDS = 2500
Size = Annotated[Decimal, Query(ge=Decimal('.01'), le=1000, decimal_places=4)]
Space = Annotated[Decimal, Query(ge=0, le=1000, decimal_places=4)]
Crop = Literal['leaf', 'strawberry', 'tomato']
Mode = Literal['crop', 'blueprint']
Orientation = Literal['original', 'rotated']
CROPS = {'leaf': '잎채소', 'strawberry': '딸기', 'tomato': '토마토'}
ORIENTATIONS = {'original': '입력 방향', 'rotated': '90° 회전'}
MODES = {'crop': '작물 보기', 'blueprint': '설계도 보기'}
PARAMS = ('width', 'length', 'bed_width', 'bed_length', 'path', 'margin', 'main_path', 'entry')
PRESETS = [
    ('기본 격자', '10 × 20 m', dict(zip(PARAMS, [10,20,1,4,.5,0,0,0]))),
    ('작은 온실', '6 × 10 m', dict(zip(PARAMS, [6,10,.8,2,.4,.3,.8,1]))),
    ('긴 온실', '8 × 30 m', dict(zip(PARAMS, [8,30,1,4,.4,.4,1,1.2]))),
    ('중앙 통로형', '12 × 24 m', dict(zip(PARAMS, [12,24,1,4,.5,.5,1.2,1.5]))),
]


def fmt(value):
    return f'{value:,.4f}'.rstrip('0').rstrip('.')


def row_name(index):
    result = ''
    while index >= 0:
        result = chr(65 + index % 26) + result
        index = index // 26 - 1
    return result


def calculate_layout(width, length, bed_width, bed_length, path,
                     margin=0, main_path=0, entry=0, rotated=False):
    """예약 공간을 먼저 빼고 각 재배 영역에 동일 방향 구획을 채웁니다.

    중앙 통로가 있으면 좌우 동일 폭 영역으로 나눕니다. 구획을 통로 쪽에
    정렬하며, 작업 공간이 있으면 아래쪽에 정렬합니다. 면적은 중복 없이
    재배 / 통로 / 외곽 / 출입 작업 / 미배치 공간으로 분류합니다.
    """
    w,h,bw,bh,p,m,a,e = (Decimal(str(v)) for v in
                        (width,length,bed_width,bed_length,path,margin,main_path,entry))
    if not all(v.is_finite() for v in (w,h,bw,bh,p,m,a,e)):
        raise ValueError('유한한 숫자를 입력해 주세요.')
    if min(w,h,bw,bh) <= 0 or min(p,m,a,e) < 0:
        raise ValueError('온실·구획 크기는 0보다 크게, 통로·여유 공간은 0 이상으로 입력해 주세요.')
    if 2*m >= min(w,h):
        raise ValueError('외곽 여유 폭의 두 배가 온실 가로·세로보다 작아야 합니다.')
    iw, ih = w-2*m, h-2*m
    if a >= iw:
        raise ValueError('중앙 통로 폭은 외곽 여유 공간을 제외한 내부 가로보다 작아야 합니다.')
    if e >= ih:
        raise ValueError('출입 작업 공간 깊이는 외곽 여유 공간을 제외한 내부 세로보다 작아야 합니다.')
    original_bw, original_bh = bw,bh
    if rotated:
        bw,bh = bh,bw
    gh = ih-e
    zone_w = (iw-a)/2 if a else iw
    cols = int((zone_w+p)//(bw+p))
    rows = int((gh+p)//(bh+p))
    number_zones = 2 if a else 1
    count = cols*rows*number_zones
    if count > MAX_BEDS:
        raise ValueError(f'각 배치안에는 최대 {MAX_BEDS:,}개 구획을 표시할 수 있어요. 구획 크기를 늘려 주세요.')
    if not count:
        cols = rows = 0
    used_w = cols*bw + max(cols-1,0)*p
    used_h = rows*bh + max(rows-1,0)*p
    zones, beds = [], []
    for side in range(number_zones):
        zx = m if side == 0 else m+zone_w+a
        # 중앙 통로에 인접하도록 배치합니다. 남는 폭은 바깥쪽에 모입니다.
        bx = zx + zone_w-used_w if a and side == 0 else zx
        by = m+gh-used_h if e else m
        zones.append(dict(x=zx,y=m,width=zone_w,height=gh,
                          bx=bx,by=by,used_width=used_w,used_length=used_h,
                          free_width=zone_w-used_w,free_length=gh-used_h))
        for row in range(rows):
            for col in range(cols):
                beds.append(dict(x=bx+col*(bw+p),y=by+row*(bh+p),
                                 width=bw,height=bh,name=f'{row_name(row)}{side*cols+col+1:02d}'))
    total=w*h
    bed_area=count*bw*bh
    path_area=number_zones*used_w*used_h-bed_area+a*gh
    margin_area=total-iw*ih
    entry_area=iw*e
    unused_area=total-bed_area-path_area-margin_area-entry_area
    return dict(width=w,length=h,bed_width=bw,bed_length=bh,path=p,margin=m,main_path=a,entry=e,
                original_bed_width=original_bw,original_bed_length=original_bh,
                columns=cols*number_zones,columns_per_zone=cols,rows=rows,count=count,
                used_width=used_w,used_length=used_h,inner_width=iw,grow_height=gh,
                total_area=total,bed_area=bed_area,path_area=path_area,margin_area=margin_area,
                entry_area=entry_area,unused_area=unused_area,rate=bed_area/total*100,
                zones=zones,beds=beds,orientation='rotated' if rotated else 'original')


def plan_pair(params):
    return {name:calculate_layout(**params,rotated=(name=='rotated')) for name in ORIENTATIONS}


def make_svg(data, uid='plan', crop='leaf', mode='crop', interactive=True):
    """화면, 비교용 미니 도면, 보고서에 동일한 좌표와 도형을 사용합니다."""
    w,h,bw,bh,p,m,a,e = (float(data[k]) for k in PARAMS)
    scale=min(560/w,420/h)
    sw,sh=w*scale,h*scale
    x,y=(820-sw)/2,(600-sh)/2
    def rect(rx,ry,rw,rh,fill,extra=''):
        return f'<rect x="{x+float(rx)*scale:.5f}" y="{y+float(ry)*scale:.5f}" width="{float(rw)*scale:.5f}" height="{float(rh)*scale:.5f}" fill="{fill}" {extra}/>'
    def text(tx,ty,label,size=11,extra=''):
        return f'<text x="{tx:.4f}" y="{ty:.4f}" font-size="{size}" {extra}>{escape(str(label))}</text>'
    plant={
      'leaf':'<path d="M12 19V7" stroke="#365d39"/><ellipse cx="8" cy="10" rx="4" ry="6" transform="rotate(-40 8 10)" fill="#a9c782"/><ellipse cx="16" cy="9" rx="4" ry="6" transform="rotate(40 16 9)" fill="#c4d898"/>',
      'strawberry':'<path d="M12 7C2 2 3 15 12 12C20 15 23 4 12 7" fill="#a3be70"/><path d="M8 12Q12 9 16 12Q15 21 12 22Q9 21 8 12" fill="#dd7668"/><path d="M11 14l.5 1m2 1 .5 1" stroke="#ffe6ba"/>',
      'tomato':'<path d="M12 22V4M12 12L5 7M12 9l6-5" stroke="#bed18a"/><circle cx="8" cy="15" r="4" fill="#df8868"/><circle cx="16" cy="12" r="4" fill="#e9a171"/>',
    }[crop]
    out=[f'''<svg xmlns="http://www.w3.org/2000/svg" id="{uid}-svg" class="greenhouse-svg {mode}"
       viewBox="0 0 820 660" data-fit-width="{sw+165}" data-fit-height="{sh+175}"
       data-center-x="410" data-center-y="300" role="group" aria-labelledby="{uid}-title {uid}-desc">
      <title id="{uid}-title">{ORIENTATIONS[data['orientation']]} 온실 배치도</title>
      <desc id="{uid}-desc">{fmt(data['width'])} × {fmt(data['length'])} m, {data['count']}개 구획.
       중앙 통로 {fmt(data['main_path'])} m, 외곽 여유 {fmt(data['margin'])} m, 출입 작업 공간 {fmt(data['entry'])} m.</desc>
      <defs>
        <pattern id="{uid}-unused" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="7" height="7" fill="#f1f2ea"/><path d="M0 0V7" stroke="#d3d9cb" stroke-width="2"/>
        </pattern>
        <pattern id="{uid}-plants" width="25" height="28" patternUnits="userSpaceOnUse">{plant}</pattern>
        <pattern id="{uid}-margin" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#e0e7da"/><circle cx="3" cy="3" r=".8" fill="#aebda4"/>
        </pattern>
      </defs>
      <style>
       #{uid}-svg{{font-family:Malgun Gothic,Arial,sans-serif;color:#294b38}}
       #{uid}-svg .bed{{cursor:pointer;outline:none}}
       #{uid}-svg .bed:hover .bed-fill,#{uid}-svg .bed:focus-visible .bed-fill{{stroke:#cb9f37;stroke-width:2.5}}
       #{uid}-svg .bed.selected .bed-fill{{stroke:#d8a22c;stroke-width:3}}
       #{uid}-svg.blueprint .plants{{display:none}}
       #{uid}-svg.blueprint .bed-fill{{fill:#fcfdf8;stroke:#436752;stroke-width:1.2}}
       #{uid}-svg.blueprint .bed-tag rect{{fill:#edf2e9}}
       #{uid}-svg.blueprint .bed-tag text{{fill:#365b43}}
       #{uid}-svg.crop .draft-dimension{{display:none}}
       #{uid}-svg .dimension-text{{fill:#536b56;font-size:11px;text-anchor:middle;paint-order:stroke;stroke:#f7f8f2;stroke-width:4;stroke-linejoin:round}}
      </style>
      <rect x="{x-5}" y="{y-5}" width="{sw+10}" height="{sh+10}" rx="3" fill="#fff" stroke="#355c44" stroke-width="2"/>
      {rect(0,0,w,h,f'url(#{uid}-margin)')}
      {rect(m,m,w-2*m,h-2*m,f'url(#{uid}-unused)')}
    ''']
    if a:
        out.append(rect((w-a)/2,m,a,h-2*m-e,'#dfcfad', 'class="main-aisle"'))
        if a*scale>=12:
            out.append(f'<path d="M410 {y+sh-m*scale-e*scale-5}V{y+m*scale+12}" fill="none" stroke="#b19a6b" stroke-width="1.3" stroke-dasharray="4 5"/>')
            out.append(f'<path d="M406 {y+m*scale+18}l4-6 4 6" fill="none" stroke="#b19a6b" stroke-width="1.3"/>')
    if e:
        out.append(rect(m,h-m-e,w-2*m,e,'#dbe7e1','class="entry-zone"'))
        if e*scale>=15 and (w-2*m)*scale>=90:
            out.append(text(410,y+(h-m-e/2)*scale+4,'출입 · 작업 공간',10,'text-anchor="middle" fill="#537565"'))
    for zone in data['zones']:
        out.append(rect(zone['bx'],zone['by'],zone['used_width'],zone['used_length'],'#eadfc9'))
    sbw,sbh=bw*scale,bh*scale
    for bed in data['beds']:
        px,py=x+float(bed['x'])*scale,y+float(bed['y'])*scale
        name=bed['name']
        attrs=f'tabindex="0" role="button" aria-pressed="false" aria-label="구획 {name}"' if interactive else ''
        out.append(f'<g class="bed" data-name="{name}" {attrs}><title>{name} · {fmt(data["bed_width"])} × {fmt(data["bed_length"])} m</title>')
        out.append(rect(bed['x'],bed['y'],bed['width'],bed['height'],'#74915f',f'class="bed-fill" rx="{min(3,sbw*.07,sbh*.07)}" stroke="#4c7046" stroke-width=".8"'))
        if min(sbw,sbh)>=12 and data['count']<=400:
            out.append(rect(bed['x'],bed['y'],bed['width'],bed['height'],f'url(#{uid}-plants)','class="plants" pointer-events="none"'))
        if min(sbw,sbh)>=16 and data['count']<=400:
            fs=min(10,max(6,min(sbw,sbh)/2.7))
            tw=min(sbw-1,len(name)*fs*.66+4)
            out.append(f'<g class="bed-tag" pointer-events="none"><rect x="{px+(sbw-tw)/2}" y="{py+sbh/2-7}" width="{tw}" height="14" rx="3" fill="#2e523d"/><text x="{px+sbw/2}" y="{py+sbh/2+fs*.34}" font-size="{fs}" fill="white" text-anchor="middle">{name}</text></g>')
        out.append('</g>')
    # 전체 치수는 두 모드에 표시하고, 세부 치수는 설계도에 표시합니다.
    def horizontal(x1,x2,yy,label,extra=''):
        label_svg=text((x1+x2)/2,yy-7,label,extra='class="dimension-text"')
        return f'<g {extra}><path d="M{x1} {yy-5}v10m0-5H{x2}m0-5v10" stroke="#81967f" fill="none"/>{label_svg}</g>'
    out.append(horizontal(x,x+sw,y-28,f'{fmt(data["width"])} m'))
    out.append(f'<g transform="translate({x-30},{y+sh/2}) rotate(-90)"><path d="M{-sh/2} -5v10m0-5H{sh/2}m0-5v10" stroke="#81967f" fill="none"/><text y="-7" class="dimension-text">{fmt(data["length"])} m</text></g>')
    if a:
        out.append(horizontal(x+(w-a)/2*scale,x+(w+a)/2*scale,y-53,f'중앙 {fmt(data["main_path"])} m','class="draft-dimension"'))
    if m:
        out.append(horizontal(x,x+m*scale,y+sh+26,f'외곽 {fmt(data["margin"])} m','class="draft-dimension"'))
    def vertical(y1,y2,xx,label):
        return f'<g class="draft-dimension" transform="translate({xx},{(y1+y2)/2}) rotate(-90)"><path d="M{-(y2-y1)/2} -4v8m0-4H{(y2-y1)/2}m0-4v8" stroke="#81967f" fill="none"/><text y="-6" class="dimension-text">{escape(label)}</text></g>'
    if e*scale>=15:
        out.append(vertical(y+(h-m-e)*scale,y+(h-m)*scale,x+sw+30,f'작업 {fmt(data["entry"])} m'))
    # 좁은 공간에는 치수를 겹쳐 그리지 않고 하단 정보란에서도 제공합니다.
    if data['beds']:
        bed=data['beds'][0]
        bx=x+float(bed['x'])*scale; by=y+float(bed['y'])*scale
        if sbw>=22:
            out.append(horizontal(bx,bx+sbw,by-9,f'{fmt(data["bed_width"])} m','class="draft-dimension"'))
        zone=data['zones'][0]
        fw=float(zone['free_width'])*scale
        if fw>60:
            fx=x+float(zone['x'])*scale if a else x+(float(zone['bx'])+float(zone['used_width']))*scale
            out.append(horizontal(fx,fx+fw,y+m*scale+13,f'여유 {fmt(zone["free_width"])} m','class="draft-dimension"'))
        fh=float(zone['free_length'])*scale
        if fh>15:
            fy=y+m*scale if e else y+(m+float(zone['used_length']))*scale
            out.append(vertical(fy,fy+fh,x+sw+30,f'여유 {fmt(zone["free_length"])} m'))
        if p*scale>=10 and data['columns_per_zone']>=2:
            out.append(horizontal(bx+sbw,bx+sbw+p*scale,by+sbh+7,f'통로 {fmt(data["path"])} m','class="draft-dimension"'))
    if a or e:
        door=min(a if a else 1.2,w-2*m)*scale
        out.append(f'<path d="M{410-door/2} {y+sh+5}H{410+door/2}" stroke="#f7f8f2" stroke-width="7"/>')
        out.append(f'<path d="M{410-door/2} {y+sh-3}v12m{door} -12v12M410 {y+sh+31}v-19m-4 5 4-5 4 5" fill="none" stroke="#537c66" stroke-width="1.7"/>')
        out.append(text(410,y+sh+46,'출입구',11,'text-anchor="middle" fill="#537c66"'))
    out.append('</svg>')
    return ''.join(out)


LEAF='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21V11M12 14C5 15 3 10 3 5c6-1 10 2 9 9ZM12 11c-1-6 3-9 9-9 0 6-3 10-9 9Z"/></svg>'

CSS=r'''
:root{--ink:#294333;--green:#28563e;--muted:#7b8976;--line:#dfe6d8;--paper:#f5f7f0;--white:#fcfdf9}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px "Malgun Gothic","Apple SD Gothic Neo",sans-serif;letter-spacing:-.025em}a{color:inherit;text-decoration:none}button,input,select{font:inherit;color:inherit}button,a{touch-action:manipulation}button{cursor:pointer}button:disabled{opacity:.35;cursor:default}svg{display:block}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #bd963f;outline-offset:3px}[hidden]{display:none!important}
.topbar{height:68px;padding:0 35px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;background:var(--white)}.brand{display:flex;align-items:center;gap:11px;font-size:18px;font-weight:700}.brand svg{width:36px;height:36px;background:#284c37;color:#d4e6af;padding:8px;border-radius:10px}.brand small{font:10px Consolas,monospace;letter-spacing:2px;border-left:1px solid var(--line);padding-left:17px;margin-left:6px;color:#8a977e}.topbar nav{display:flex;gap:20px;color:#819076;font-size:11px}.topbar nav a{border-bottom:1px solid #bac8b0;padding-bottom:3px}
main{max-width:1600px;margin:auto;padding:28px 35px 20px}.intro{display:flex;align-items:end;justify-content:space-between;margin-bottom:23px}.eyebrow{font:10px Consolas,monospace;letter-spacing:2.3px;color:#819370;margin:0 0 9px}.intro h1{font-size:28px;letter-spacing:-1.3px;margin:0 0 8px}.intro p{color:var(--muted);font-size:12px;margin:0}.version{font:11px Consolas,monospace;color:#718567;border:1px solid var(--line);border-radius:6px;padding:9px 12px}
.workspace{display:grid;grid-template-columns:278px minmax(0,1fr);gap:22px;align-items:start}.sidebar{border:1px solid var(--line);border-radius:14px;background:var(--white);overflow:hidden}.side-title{padding:18px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.side-title h2{font-size:14px;margin:0}.unit-tag{color:#89977e;font-size:10px}.form-body{padding:18px 20px}.field-section+.field-section{border-top:1px solid var(--line);margin-top:20px;padding-top:17px}.section-title{font-size:12px;display:flex;align-items:center;gap:8px;margin:0 0 13px}.section-title span{font:10px Consolas,monospace;color:#97a387}.input-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.input-row+.input-row{margin-top:13px}label{font-size:10px;color:#7b8974;display:block;margin-bottom:6px}.input-wrap{position:relative}.input-wrap input{width:100%;padding:9px 25px 9px 10px;background:white;border:1px solid var(--line);border-radius:6px;appearance:textfield;-moz-appearance:textfield;font-size:16px;font-weight:600}.input-wrap input::-webkit-inner-spin-button{appearance:none}.input-wrap span{position:absolute;right:10px;top:12px;font-size:10px;color:#96a28b}.field-note{font-size:10px;line-height:1.8;color:#8b987f;margin:9px 0 0}select{width:100%;background:white;border:1px solid var(--line);border-radius:6px;padding:9px}.presets{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:18px}.preset{border:1px solid var(--line);border-radius:7px;padding:9px 8px;font-size:11px;display:block;text-align:left;background:#f5f7ef}.preset small{display:block;color:#91a083;font-size:9px;margin-top:4px}.preset:hover{border-color:#8b9f77;background:#edf3e3}.apply{border:0;border-radius:7px;background:var(--green);color:white;padding:12px 14px;margin-top:20px;width:100%;display:flex;justify-content:space-between;font-weight:600}.reset{font-size:10px;color:#8a997e;display:block;text-align:center;margin-top:12px}.dirty-note{font-size:10px;color:#9c762d;line-height:1.8;margin-bottom:0}.conditions{background:#edf2e5;border-top:1px solid var(--line);padding:15px 20px;font-size:10px;color:#7c8d6e;line-height:1.9}.conditions strong{color:#5f7953}.conditions p{margin:6px 0 0}
.results{min-width:0}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:15px}.metric{border:1px solid var(--line);background:var(--white);border-radius:11px;padding:16px 19px;min-height:106px}.metric:first-child{background:#284f3a;color:#fff;border-color:#284f3a}.metric .label{color:#7e8f73;font-size:11px}.metric:first-child .label{color:#c0d0b2}.metric strong{font:32px Arial,sans-serif;letter-spacing:-1.2px}.metric .value{margin-top:8px}.metric .unit{font-size:12px;opacity:.65;margin-left:5px}.metric small{display:block;font-size:10px;color:#8b9a7d;margin-top:6px}.metric:first-child small{color:#b4c7a8}
.comparison{border:1px solid var(--line);border-radius:13px;background:var(--white);padding:16px 18px;margin-bottom:16px}.section-heading{display:flex;justify-content:space-between;gap:12px;align-items:center}.section-heading h2{font-size:13px;margin:0}.section-heading>span{font-size:10px;color:#8b9b7a}.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:12px}.compare-option{border:1px solid var(--line);border-radius:9px;padding:10px 13px;display:grid;grid-template-columns:82px minmax(0,1fr) auto;align-items:center;gap:13px;background:#f8faf4;min-width:0}.compare-option.active{border:1.5px solid #628055;background:#f0f5e7;box-shadow:0 0 0 2px #dae5ce66}.compare-option .thumb{width:82px;height:89px;background:#f6f8f0;border-radius:5px;overflow:hidden}.thumb svg{width:100%;height:100%;pointer-events:none}.compare-copy{min-width:0}.compare-copy h3{font-size:12px;margin:0 0 6px}.compare-copy p{font-size:10px;color:#849477;margin:4px 0;line-height:1.6}.compare-count{text-align:right;font-size:21px;font-family:Arial,sans-serif;white-space:nowrap}.compare-count small{font-size:10px;display:block;margin-top:6px;color:#7e916f;font-family:"Malgun Gothic",sans-serif}.compare-badge{display:inline-block;font-size:9px;border-radius:4px;background:#dce8cc;color:#5f794b;padding:3px 5px;margin-top:3px}.compare-message{font-size:10px;line-height:1.7;color:#87967c;margin:11px 0 0}.compare-message b{font-weight:600;color:#5c7e4d}
.plan-card{border:1px solid var(--line);border-radius:14px;background:var(--white);overflow:hidden}.plan-heading{padding:17px 20px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px}.plan-heading h2{font-size:14px;margin:0}.plan-heading p{font-size:10px;color:#87987a;margin:5px 0 0}.plan-actions{display:flex;align-items:center;gap:9px}.segmented{display:flex;border:1px solid var(--line);border-radius:6px;padding:3px;background:#f3f6ec;gap:2px}.segmented button{border:0;padding:7px 10px;border-radius:4px;font-size:10px;background:transparent;color:#8a987d}.segmented button[aria-pressed=true]{background:#fff;color:#315937;box-shadow:0 1px 4px #19332110}.icon-button{border:1px solid var(--line);background:#fff;border-radius:6px;padding:9px;font-size:11px}.canvas{height:530px;position:relative;background-color:#f6f8f0;background-image:radial-gradient(#d8e0cf .7px,transparent .7px);background-size:18px 18px;overflow:hidden;touch-action:none}.canvas>.greenhouse-svg{width:100%;height:100%;user-select:none}.canvas-label{position:absolute;left:22px;top:22px;pointer-events:none;z-index:1;color:#7a9168;font:10px Consolas,monospace;letter-spacing:1px}.canvas-label small{display:block;font:9px "Malgun Gothic",sans-serif;margin-top:7px;color:#96a489}.orientation{position:absolute;right:24px;top:23px;color:#a1af93;writing-mode:vertical-rl;font-size:10px;letter-spacing:3px}.orientation b{font-size:19px;font-weight:400;line-height:1.6}.canvas-hint{position:absolute;bottom:19px;left:20px;color:#93a184;font-size:10px;pointer-events:none}.zoom-tools{position:absolute;bottom:14px;right:17px;background:#fcfdf9;border:1px solid var(--line);border-radius:7px;display:flex;align-items:center;padding:3px;box-shadow:0 2px 5px #22462208}.zoom-tools button{border:0;border-radius:4px;background:transparent;min-width:30px;height:30px;font-size:17px;color:#6c8759}.zoom-tools button:hover{background:#edf3e3}.zoom-tools output{font:10px Consolas,monospace;width:43px;text-align:center;color:#8a997b}.zoom-tools .fit{font-size:10px;border-left:1px solid var(--line);border-radius:0;padding:0 9px;margin-left:4px}.legend{border-top:1px solid var(--line);padding:13px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;font-size:10px;color:#829373}.legend span{display:flex;gap:6px;align-items:center}.swatch{width:9px;height:9px;display:inline-block;border-radius:2px}.green{background:#74915f}.sand{background:#dfcfad}.mint{background:#dbe7e1;border:1px solid #b3c9bd}.sage{background:#e0e7da;border:1px dotted #9cac8d}.hatch{background:repeating-linear-gradient(135deg,#f1f2ea,#f1f2ea 2px,#cbd4c0 2px,#cbd4c0 3px)}.detail-strip{border-top:1px solid var(--line);background:#fafbf6;padding:12px 20px;display:flex;gap:12px 20px;flex-wrap:wrap;font-size:10px;color:#8b987d}.detail-strip b{color:#5c7750;font-weight:500;margin-left:4px}.empty-state{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);padding:22px;width:280px;max-width:85%;border:1px solid var(--line);border-radius:10px;background:#fcfdf9ed;text-align:center}.empty-state p{font-size:11px;line-height:1.8;color:#819273;margin:9px 0 0}
.selection{margin-top:12px;display:flex;align-items:center;gap:12px;padding:14px 17px;border:1px solid var(--line);background:var(--white);border-radius:10px}.selection-icon{background:#edf3e4;padding:9px;border-radius:7px;color:#7b9963}.selection-icon svg{width:16px;height:16px}.selection-text{flex:1}.selection-text strong{font-size:11px}.selection-text p{font-size:10px;color:#89987c;margin:5px 0 0}.selection-dim{font:11px Consolas,"Malgun Gothic",sans-serif;text-align:right;color:#758d61}.selection-dim small{font-size:9px;display:block;margin-top:5px;color:#9ba78f}
.area-panel{margin-top:13px;padding:16px 19px;border:1px solid var(--line);border-radius:11px;background:var(--white)}.area-panel h3{font-size:11px;margin:0 0 11px}.area-bar{display:flex;width:100%;height:7px;overflow:hidden;border-radius:4px;background:#edf2e7}.area-items{display:flex;gap:11px 22px;flex-wrap:wrap;margin-top:12px;font-size:10px;color:#91a083}.area-items b{font-weight:500;color:#647d53;margin-left:5px}.export-bar{margin-top:14px;border:1px solid var(--line);border-radius:11px;background:#edf3e5;display:flex;align-items:center;justify-content:space-between;gap:15px;padding:16px 19px}.export-bar h3{font-size:12px;margin:0 0 6px}.export-bar p{font-size:10px;color:#879a75;margin:0}.export-actions{display:flex;gap:7px;flex-wrap:wrap}.export-actions button,.export-actions a{border:1px solid #ccd8bf;background:#fcfdf8;font-size:10px;border-radius:5px;padding:9px 11px;color:#537345}.export-actions .primary{background:#2c5b40;border-color:#2c5b40;color:#fff}.export-status{font-size:10px;color:#839875;margin:8px 0 0;min-height:13px}.footer{display:flex;justify-content:space-between;gap:15px;border-top:1px solid var(--line);padding-top:17px;margin-top:24px;font-size:10px;color:#99a68b}.footer b{color:#7c906b;font-weight:500}.focus-view .workspace{grid-template-columns:1fr}.focus-view .workspace>aside{display:none}.focus-view .comparison{display:none}.focus-view .canvas{height:70vh;min-height:450px}.plan-card:fullscreen{border:0;border-radius:0;display:flex;flex-direction:column;background:var(--white)}.plan-card:fullscreen .canvas{height:auto;flex:1;min-height:0}.plan-card:fullscreen .plan-heading{flex:none}.plan-card:fullscreen .legend,.plan-card:fullscreen .detail-strip{flex:none}
@media(max-width:1150px){main{padding:24px}.topbar{padding:0 24px}.workspace{grid-template-columns:250px minmax(0,1fr);gap:17px}.form-body{padding:17px}.compare-option{grid-template-columns:60px minmax(0,1fr);padding:10px;gap:8px}.compare-option .thumb{width:60px;height:75px;grid-row:span 2}.compare-count{font-size:17px;text-align:left}.compare-count small{display:inline;margin-left:6px}.compare-copy p{display:none}.plan-heading{flex-wrap:wrap}.metric{padding:15px}.export-bar{align-items:flex-start;flex-direction:column}}
@media(max-width:800px){.brand small,.topbar nav span,.version{display:none}.workspace{grid-template-columns:1fr}.intro h1{font-size:24px}.intro p{font-size:11px;line-height:1.8}.form-body{display:grid;grid-template-columns:1fr 1fr;gap:18px}.presets{grid-column:1/-1;grid-template-columns:repeat(4,1fr);margin:0}.field-section+.field-section{border:0;margin:0;padding:0}.form-actions{display:flex;flex-direction:column;justify-content:end}.apply{margin-top:0}.conditions br{display:none}.canvas{height:550px}.compare-option{grid-template-columns:73px minmax(0,1fr) auto;gap:10px}.compare-option .thumb{width:73px;grid-row:auto}.compare-count{text-align:right}.compare-count small{display:block;margin:5px 0 0}.metrics{gap:8px}.export-bar{flex-direction:row;align-items:center}.footer span:last-child{display:none}.compare-grid{gap:8px}.plan-heading{padding:15px 17px}}
@media(max-width:520px){main{padding:23px 14px}.topbar{padding:0 17px;height:62px}.intro h1{font-size:23px}.intro p{font-size:10px}.topbar nav{font-size:10px}.presets{grid-template-columns:1fr 1fr}.metric{padding:14px 11px;min-height:104px}.metric .label{font-size:10px}.metric strong{font-size:26px}.metric .unit{font-size:10px}.metric small{font-size:9px;line-height:1.5}.comparison{padding:14px 12px}.section-heading>span{font-size:9px}.compare-option{grid-template-columns:48px minmax(0,1fr);gap:7px;padding:9px}.compare-option .thumb{width:48px;height:66px;grid-row:span 2}.compare-copy h3{font-size:11px}.compare-badge{font-size:8px;padding:2px 4px}.compare-count{text-align:left;font-size:17px}.compare-count small{display:inline;margin-left:4px;font-size:9px}.plan-heading{gap:12px}.plan-actions{width:100%;justify-content:space-between}.canvas{height:520px}.canvas-label,.canvas-hint{display:none}.orientation{right:14px;top:18px;font-size:9px}.legend{padding:13px;gap:12px;font-size:9px}.detail-strip{padding:12px 13px;font-size:9px;gap:8px 12px}.selection{padding:13px;gap:9px}.selection-dim{font-size:10px}.selection-text p{font-size:9px;line-height:1.6}.export-bar{flex-direction:column;align-items:stretch}.export-actions{justify-content:flex-start}.area-items{font-size:9px;gap:9px 14px}.focus-view .canvas{height:65vh;min-height:450px}}
.orientation b{writing-mode:horizontal-tb}
@media(max-width:800px){.form-actions{grid-column:1/-1}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
@media print{.topbar,.intro,.workspace>aside,.comparison,.metrics,.plan-actions,.zoom-tools,.canvas-hint,.selection,.export-bar,.footer,.export-status{display:none}.workspace{display:block}main{padding:0}.canvas{height:65vh}.plan-card{break-inside:avoid}body{background:white;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''

PAGE=Template(r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#28563e"><title>온실연구실 · 온실 배치 계산기</title><style>$css</style></head><body>
<header class="topbar"><a href="/" class="brand">$leaf 온실연구실<small>GREENHOUSE LAB</small></a><nav><span>더 나은 재배 공간을 위한 작은 설계</span><a href="#conditions">배치 기준 ↗</a></nav></header>
<main><section class="intro"><div><div class="eyebrow">DESIGN A SPACE TO GROW</div><h1>온실 재배 구획 배치 계산기</h1><p>들어가는 길부터 자라는 공간까지. 두 가지 배치를 비교하고 나의 온실을 설계하세요.</p></div><span class="version">LAYOUT STUDIO / 02</span></section>
<div class="workspace"><aside><section class="sidebar"><div class="side-title"><h2>공간 설정</h2><span class="unit-tag">모든 길이 · m</span></div><form id="layout-form" method="get" action="/layout"><input type="hidden" name="orientation" id="orientation-input" value="$orientation"><input type="hidden" name="mode" id="mode-input" value="$mode"><div class="form-body"><div class="presets">$presets</div>
<section class="field-section"><h3 class="section-title"><span>01</span>온실 크기</h3><div class="input-row">$width_input $length_input</div></section>
<section class="field-section"><h3 class="section-title"><span>02</span>재배 구획</h3><div class="input-row">$bed_width_input $bed_length_input</div><p class="field-note">구획만 90° 회전한 배치도 함께 계산해요.</p></section>
<section class="field-section"><h3 class="section-title"><span>03</span>통로와 여유 공간</h3><div class="input-row">$path_input $main_path_input</div><div class="input-row">$margin_input $entry_input</div><p class="field-note">중앙 통로는 세로 방향, 출입구는 아래쪽 중앙.<br>외곽은 네 면에 적용하며, 0이면 생략해요.</p></section>
<section class="field-section"><h3 class="section-title"><span>04</span>작물 표현</h3><label for="crop">배치도에 표시할 작물</label><select id="crop" name="crop">$crop_options</select><p class="field-note">그림과 색상만 변경해요. 식재 간격·수량이나 재배 적합성을 의미하지 않아요.</p></section>
<div class="form-actions"><button type="submit" class="apply">두 방향 배치 계산하기<span>→</span></button><a href="/" class="reset">중앙 통로형 기본값으로</a><p class="dirty-note" id="dirty-note" hidden>변경한 값은 계산하기를 누르면 반영돼요.</p></div></div></form>
<div class="conditions" id="conditions"><strong>이 도면의 배치 기준</strong><p>고정된 구획을 동일 방향으로 배치해요.<br>중앙 통로 양쪽은 같은 폭으로 나눠요.<br>출입 작업 공간은 내부 가로 전체를 비워요.<br>기둥·설비·문 회전 반경은 포함하지 않아요.</p></div></section></aside>
<section class="results" aria-label="배치 계산 결과"><div class="metrics"><article class="metric"><span class="label">배치 가능한 구획</span><div class="value"><strong id="count-value">$count</strong><span class="unit">개</span></div><small>$orientation_label · $columns열 × $rows행</small></article><article class="metric"><span class="label">실제 재배 면적</span><div class="value"><strong id="area-value">$bed_area</strong><span class="unit">㎡</span></div><small>전체 온실 $total_area ㎡</small></article><article class="metric"><span class="label">재배 면적 비율</span><div class="value"><strong id="rate-value">$rate</strong><span class="unit">%</span></div><small>외곽·통로·작업 공간 제외</small></article></div>
<section class="comparison"><div class="section-heading"><h2>어느 방향으로 배치할까요?</h2><span>같은 조건 · 구획 방향만 비교</span></div><div class="compare-grid">$comparison</div><p class="compare-message">$compare_message</p></section>
<section class="plan-card" id="plan-card"><div class="plan-heading"><div><h2>나의 온실 배치도</h2><p>$orientation_label · 실제 비율 · 구획을 선택해 살펴보세요</p></div><div class="plan-actions"><div class="segmented" role="group" aria-label="보기 모드"><button type="button" data-mode="crop" aria-pressed="$crop_pressed">작물 보기</button><button type="button" data-mode="blueprint" aria-pressed="$blueprint_pressed">설계도 보기</button></div><button class="icon-button" id="focus-toggle" type="button" aria-pressed="false">패널 접기</button><button class="icon-button" id="fullscreen" type="button" aria-label="배치도 전체 화면">⛶ 전체 화면</button></div></div>
<div class="canvas" id="canvas"><div class="canvas-label">GREENHOUSE / $orientation_short<small>$width × $length m · $total_area ㎡</small></div><div class="orientation"><b>↑</b>세로 방향</div>$svg $empty<div class="canvas-hint">확대 후 드래그로 이동 · 구획 클릭으로 선택</div><div class="zoom-tools" role="group" aria-label="배치도 확대 축소"><button id="zoom-out" type="button" aria-label="축소">−</button><output id="zoom-value" aria-live="polite">100%</output><button id="zoom-in" type="button" aria-label="확대">+</button><button id="zoom-fit" class="fit" type="button">화면 맞춤</button></div></div>
<div class="legend"><span><i class="swatch green"></i>재배 구획</span><span><i class="swatch sand"></i>통로</span><span><i class="swatch mint"></i>출입 작업 공간</span><span><i class="swatch sage"></i>외곽 여유</span><span><i class="swatch hatch"></i>남는 공간</span></div>
<div class="detail-strip"><span>구획<b>$shown_bw × $shown_bh m</b></span><span>구획 사이<b>$path m</b></span><span>중앙 통로<b>$main_path m</b></span><span>외곽 여유<b>$margin m</b></span><span>작업 공간 깊이<b>$entry m</b></span><span>영역별 남는 폭·깊이<b>$free_width × $free_length m</b></span></div></section>
<section class="selection" aria-live="polite"><span class="selection-icon">$leaf</span><div class="selection-text"><strong id="selected-title">$selection_title</strong><p id="selected-detail">$selection_detail</p></div><div class="selection-dim">$shown_bw × $shown_bh m<small>구획 하나 · $single_area ㎡</small></div></section>
<section class="area-panel"><h3>온실 면적 구성 <span style="font-weight:400;color:#94a388">/ 전체 $total_area ㎡</span></h3><div class="area-bar" aria-hidden="true">$area_bar</div><div class="area-items">$area_items</div></section>
<section class="export-bar"><div><h3>발표 자료로 가져가세요</h3><p>제목 · 입력 조건 · 배치도 · 비교 결과를 한 장에 담아요.</p></div><div class="export-actions"><a class="report-link" id="download-svg" href="$svg_url" download="greenhouse-report.svg">SVG 저장</a><button type="button" id="download-png">PNG 저장</button><a class="report-link primary" id="print-report" href="$report_url" target="_blank" rel="noopener">인쇄 / PDF</a></div></section><p class="export-status" id="export-status" aria-live="polite"></p>
</section></div><footer class="footer"><span><b>온실연구실</b> / 작은 설계로 시작하는 나의 온실</span><span>입력 방향·90° 회전 비교 · 실제 시공 전 현장 조건 확인</span></footer></main>
<script>
const svg=document.getElementById('plan-svg'),canvas=document.getElementById('canvas');
let selected=null,zoom=1,offsetX=0,offsetY=0,drag=null,dragged=false;
let mode='$mode';
function selectBed(bed){if(selected){selected.classList.remove('selected');selected.setAttribute('aria-pressed','false');}selected=bed;bed.classList.add('selected');bed.setAttribute('aria-pressed','true');document.getElementById('selected-title').textContent='구획 '+bed.dataset.name+' 선택됨';document.getElementById('selected-detail').textContent='$orientation_label · 가로 $shown_bw m × 세로 $shown_bh m · $single_area ㎡';}
svg.addEventListener('click',e=>{const bed=e.target.closest('.bed');if(bed&&!dragged)selectBed(bed);});
svg.addEventListener('keydown',e=>{const bed=e.target.closest('.bed');if(bed&&(e.key==='Enter'||e.key===' ')){e.preventDefault();selectBed(bed);}});
function applyView(){const aspect=canvas.clientWidth/canvas.clientHeight;if(!Number.isFinite(aspect)||aspect<=0)return;const baseW=Math.max(Number(svg.dataset.fitWidth),(Number(svg.dataset.fitHeight)+(canvas.clientWidth<450?30:0))*aspect),baseH=baseW/aspect;const vw=baseW/zoom,vh=baseH/zoom;offsetX=Math.max(-(baseW-vw)/2,Math.min((baseW-vw)/2,offsetX));offsetY=Math.max(-(baseH-vh)/2,Math.min((baseH-vh)/2,offsetY));svg.setAttribute('viewBox',[Number(svg.dataset.centerX)-vw/2+offsetX,Number(svg.dataset.centerY)-vh/2+offsetY,vw,vh].join(' '));document.getElementById('zoom-value').textContent=Math.round(zoom*100)+'%';document.getElementById('zoom-out').disabled=zoom<=1;document.getElementById('zoom-in').disabled=zoom>=4;canvas.style.cursor=zoom>1?'grab':'default';}
document.getElementById('zoom-in').onclick=()=>{zoom=Math.min(4,zoom+.25);applyView();};document.getElementById('zoom-out').onclick=()=>{zoom=Math.max(1,zoom-.25);applyView();};document.getElementById('zoom-fit').onclick=()=>{zoom=1;offsetX=offsetY=0;applyView();};
svg.addEventListener('pointerdown',e=>{dragged=false;if(zoom>1&&e.button===0)drag={x:e.clientX,y:e.clientY,ox:offsetX,oy:offsetY};});svg.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>5){dragged=true;svg.setPointerCapture(e.pointerId);}if(!dragged)return;const m=svg.getScreenCTM();offsetX=drag.ox-dx/m.a;offsetY=drag.oy-dy/m.d;applyView();canvas.style.cursor='grabbing';});svg.addEventListener('pointerup',()=>{drag=null;applyView();});svg.addEventListener('pointercancel',()=>{drag=null;applyView();});svg.addEventListener('pointerleave',()=>{if(!dragged)drag=null;});new ResizeObserver(applyView).observe(canvas);applyView();
const form=document.getElementById('layout-form');form.addEventListener('input',()=>document.getElementById('dirty-note').hidden=false);
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.mode;document.querySelectorAll('.greenhouse-svg').forEach(s=>{s.classList.remove('crop','blueprint');s.classList.add(mode);});document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));document.getElementById('mode-input').value=mode;document.querySelectorAll('.report-link,.compare-option').forEach(link=>{const url=new URL(link.href);url.searchParams.set('mode',mode);link.href=url.href;});const url=new URL(location.href);url.searchParams.set('mode',mode);history.replaceState(null,'',url);}));
const focusButton=document.getElementById('focus-toggle');focusButton.onclick=()=>{const on=document.body.classList.toggle('focus-view');focusButton.textContent=on?'패널 펼치기':'패널 접기';focusButton.setAttribute('aria-pressed',String(on));};
const card=document.getElementById('plan-card'),fullButton=document.getElementById('fullscreen');fullButton.onclick=async()=>{try{if(document.fullscreenElement){await document.exitFullscreen();}else if(card.requestFullscreen){await card.requestFullscreen();}else{throw new Error('unsupported');}}catch(e){document.body.classList.add('focus-view');focusButton.textContent='패널 펼치기';focusButton.setAttribute('aria-pressed','true');document.getElementById('export-status').textContent='이 브라우저에서는 패널을 접어 넓게 표시했어요.';}};
document.addEventListener('fullscreenchange',()=>{fullButton.textContent=document.fullscreenElement?'⛶ 전체 화면 종료':'⛶ 전체 화면';fullButton.setAttribute('aria-label',document.fullscreenElement?'전체 화면 종료':'배치도 전체 화면');});
document.getElementById('download-png').onclick=async function(){const button=this,status=document.getElementById('export-status');button.disabled=true;status.textContent='발표용 이미지를 만들고 있어요…';let objectUrl;try{const url=new URL(document.getElementById('download-svg').href);url.searchParams.set('mode',mode);const response=await fetch(url);if(!response.ok)throw new Error('export');const blob=await response.blob();objectUrl=URL.createObjectURL(blob);const image=new Image();await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;image.src=objectUrl;});const c=document.createElement('canvas');c.width=2400;c.height=2040;const ctx=c.getContext('2d');ctx.fillStyle='#f7f9f2';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(image,0,0,c.width,c.height);const png=await new Promise(resolve=>c.toBlob(resolve,'image/png'));if(!png)throw new Error('png');const pngUrl=URL.createObjectURL(png),a=document.createElement('a');a.href=pngUrl;a.download='greenhouse-report.png';a.click();setTimeout(()=>URL.revokeObjectURL(pngUrl),2000);status.textContent='발표용 PNG를 저장했어요. (2400 × 2040)';}catch(e){status.textContent='이미지 저장에 실패했어요. SVG 저장이나 인쇄 / PDF를 이용해 주세요.';}finally{if(objectUrl)URL.revokeObjectURL(objectUrl);button.disabled=false;}};
</script></body></html>''')


def query_url(path, params, **extras):
    return path+'?'+urlencode({**{k:str(v) for k,v in params.items()},**extras})


def input_field(name,label,value):
    minimum='.01' if name in PARAMS[:4] else '0'
    return f'<div><label for="{name}">{label}</label><div class="input-wrap"><input id="{name}" name="{name}" type="number" min="{minimum}" max="1000" step="0.0001" required value="{value}"><span>m</span></div></div>'


def render_page(params, plans, orientation, crop, mode):
    data=plans[orientation]
    values={k:str(v) for k,v in params.items()}
    values.update({k:fmt(data[k]) for k in ('count','columns','rows','bed_area','total_area')})
    values.update(css=CSS,leaf=LEAF,orientation=orientation,orientation_label=ORIENTATIONS[orientation],
                  orientation_short='A' if orientation=='original' else 'B',mode=mode,
                  rate=f'{data["rate"]:.1f}',shown_bw=fmt(data['bed_width']),shown_bh=fmt(data['bed_length']),
                  free_width=fmt(data['zones'][0]['free_width']),free_length=fmt(data['zones'][0]['free_length']),
                  single_area=fmt(data['bed_width']*data['bed_length']),
                  crop_pressed=str(mode=='crop').lower(),blueprint_pressed=str(mode=='blueprint').lower(),
                  svg=make_svg(data,crop=crop,mode=mode),
                  crop_options=''.join(f'<option value="{k}" {"selected" if k==crop else ""}>{v}</option>' for k,v in CROPS.items()),
                  presets=''.join(f'<a class="preset" href="{escape(query_url("/layout",p,crop=crop,mode=mode))}">{n}<small>{s}</small></a>' for n,s,p in PRESETS),
                  svg_url=escape(query_url('/export.svg',params,orientation=orientation,crop=crop,mode=mode)),
                  report_url=escape(query_url('/report',params,orientation=orientation,crop=crop,mode=mode)),
                  empty='' if data['count'] else '<div class="empty-state"><strong>배치 가능한 구획이 없습니다</strong><p>이 방향의 구획이 재배 영역보다 커요.<br>다른 방향을 선택하거나 크기를 조정해 주세요.</p></div>',
                  selection_title='어떤 구획을 살펴볼까요?' if data['count'] else '다른 방향과 공간 설정을 확인해 주세요',
                  selection_detail='구획을 클릭하면 실제 크기와 면적을 확인할 수 있어요.' if data['count'] else '외곽·통로·작업 공간을 제외한 영역을 기준으로 계산해요.')
    for key,label in zip(PARAMS,('가로 길이','세로 길이','구획 가로','구획 세로','구획 사이 통로','외곽 여유 폭','중앙 통로 폭','작업 공간 깊이')):
        values[key+'_input']=input_field(key,label,params[key])
    comparison=[]
    best=max(p['count'] for p in plans.values())
    for name,plan in plans.items():
        badge='재배 면적이 더 넓어요' if plan['count']==best and plans['original']['count']!=plans['rotated']['count'] else '동일한 재배 면적'
        if plan['count']<best: badge='비교 배치'
        href=escape(query_url('/layout',params,orientation=name,crop=crop,mode=mode))
        comparison.append(f'''<a class="compare-option {'active' if name==orientation else ''}" href="{href}" aria-label="{ORIENTATIONS[name]} 배치 선택" {'aria-current="true"' if name==orientation else ''}>
          <div class="thumb">{make_svg(plan,'mini-'+name,crop,mode,False)}</div><div class="compare-copy"><h3>{'A' if name=='original' else 'B'} · {ORIENTATIONS[name]}</h3><p>구획 {fmt(plan['bed_width'])} × {fmt(plan['bed_length'])} m<br>재배 {fmt(plan['bed_area'])} ㎡ · 남는 공간 {fmt(plan['unused_area'])} ㎡</p><span class="compare-badge">{badge}</span></div><div class="compare-count">{plan['count']}<small>개 · {plan['rate']:.1f}%</small></div></a>''')
    values['comparison']=''.join(comparison)
    delta=plans['rotated']['count']-plans['original']['count']
    values['compare_message']=(f'<b>{"90° 회전" if delta>0 else "입력 방향"} 배치에 {abs(delta)}개 더 들어가요.</b> ' if delta else '<b>두 방향의 구획 수와 재배 면적이 같아요.</b> ')+ '중앙 통로는 고정합니다. 두 방향의 균일 격자 비교이며 전체 최적 배치를 뜻하지 않아요.'
    area_rows=[('재배','bed_area','#74915f'),('통로','path_area','#dfcfad'),('출입 작업','entry_area','#c5dacd'),('외곽 여유','margin_area','#b3c3a6'),('남는 공간','unused_area','#e2e6d8')]
    values['area_bar']=''.join(f'<span style="width:{data[k]/data["total_area"]*100}%;background:{color}"></span>' for _,k,color in area_rows)
    values['area_items']=''.join(f'<span>{label}<b>{fmt(data[k])} ㎡</b></span>' for label,k,_ in area_rows)
    return PAGE.substitute(values)


def make_report(params,plans,orientation,crop,mode):
    """선택한 도면, 조건, 비교 결과, 범례를 독립된 SVG 한 장으로 만듭니다."""
    d=plans[orientation]
    def t(x,y,label,size=13,fill='#526a48',extra=''):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{escape(str(label))}</text>'
    # 세로로 긴 온실도 보고서의 도면 영역 높이를 충분히 활용합니다.
    scale=min(560/float(d['width']),420/float(d['length']))
    view_width=max(float(d['width'])*scale+165,(float(d['length'])*scale+175)*745/655)
    view_height=view_width*655/745
    view=f'{410-view_width/2} {300-view_height/2} {view_width} {view_height}'
    chart=make_svg(d,'report-plan',crop,mode,False).replace('viewBox="0 0 820 660"',f'x="20" y="170" width="745" height="655" viewBox="{view}"',1)
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1020" viewBox="0 0 1200 1020" style="font-family:Malgun Gothic,Arial,sans-serif">',
         '<rect width="1200" height="1020" fill="#f7f9f2"/><rect x="30" y="30" width="1140" height="960" rx="18" fill="#fcfdf9" stroke="#dfe6d8"/>',
         t(62,73,'GREENHOUSE LAB / LAYOUT REPORT',11,'#91a47a'),t(60,116,'온실 재배 구획 배치도',29,'#294b36'),
         t(62,147,f'{ORIENTATIONS[orientation]} · {MODES[mode]} · 온실 {fmt(d["width"])} × {fmt(d["length"])} m'),
         '<path d="M60 167H1140" stroke="#dfe6d8"/>',chart,
         '<rect x="784" y="193" width="350" height="132" rx="10" fill="#2b513b"/>',
         t(806,222,'배치 가능한 구획',12,'#c9d8b9'),t(804,266,f'{d["count"]} 개',34,'white'),
         t(806,300,f'재배 {fmt(d["bed_area"])} ㎡ · 재배 면적 비율 {d["rate"]:.1f}%',14,'#d7e3cc'),
         t(789,361,'입력 조건',15,'#304e39')]
    rows=[('구획 크기 (선택 방향)',f'{fmt(d["bed_width"])} × {fmt(d["bed_length"])} m'),
          ('구획 사이 통로',f'{fmt(d["path"])} m'),('중앙 통로 폭',f'{fmt(d["main_path"])} m'),
          ('외곽 여유 폭',f'{fmt(d["margin"])} m'),('출입 작업 공간 깊이',f'{fmt(d["entry"])} m')]
    for i,(label,value) in enumerate(rows):
        out.extend([t(790,391+i*28,label,12,'#87967c'),t(1125,391+i*28,value,12,extra='text-anchor="end"')])
    out.append(t(789,559,'두 방향 비교',15,'#304e39'))
    for i,name in enumerate(ORIENTATIONS):
        plan=plans[name]
        out.append(t(790,590+i*29,f'{ORIENTATIONS[name]}: {plan["count"]}개 / {fmt(plan["bed_area"])} ㎡ / {plan["rate"]:.1f}%',12))
    out.append(t(789,665,'면적 구성',15,'#304e39'))
    for i,(label,key) in enumerate([('전체','total_area'),('재배','bed_area'),('통로','path_area'),('출입 작업','entry_area'),('외곽 여유','margin_area'),('남는 공간','unused_area')]):
        out.extend([t(790,694+i*24,label,12,'#87967c'),t(1125,694+i*24,f'{fmt(d[key])} ㎡',12,extra='text-anchor="end"')])
    out.append('<path d="M60 840H1140" stroke="#dfe6d8"/>')
    for i,(label,color) in enumerate([('재배 구획','#74915f'),('통로','#dfcfad'),('출입 작업 공간','#c5dacd'),('외곽 여유','#b3c3a6'),('남는 공간','#e2e6d8')]):
        out.append(f'<rect x="{62+i*210}" y="860" width="12" height="12" rx="2" fill="{color}"/>')
        out.append(t(82+i*210,871,label,12))
    out.extend([t(62,907,'배치 기준: 중앙 통로는 세로 방향에 고정 · 좌우 동일 폭 · 출입 작업 공간은 내부 가로 전체를 예약',12),
                t(62,932,'입력 방향과 90° 회전의 균일 격자를 비교합니다. 기둥·설비·문 회전 반경은 포함하지 않습니다.',12),
                t(62,957,f'작물 표현: {CROPS[crop]} (장식) · 실제 식재 수를 의미하지 않습니다. 실제 시공 전 현장 조건을 확인하세요.',11,'#8a9c79'),'</svg>'])
    return ''.join(out)


def error_page(message):
    return HTMLResponse(f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>입력값 확인 · 온실연구실</title><body style="font-family:Malgun Gothic,sans-serif;background:#f5f7f0;color:#294333"><main style="max-width:570px;margin:10vh auto;padding:30px;background:white;border:1px solid #dfe6d8;border-radius:13px"><p>온실연구실 / 입력 안내</p><h1 style="font-size:24px">입력값을 확인해 주세요</h1><p style="line-height:1.9">{escape(message)}</p><p style="font-size:12px;color:#809272;line-height:1.9">크기 0.01–1,000 m · 여유 공간 0–1,000 m · 소수점 넷째 자리까지<br>각 배치안 최대 2,500개 구획</p><button onclick="history.back()" style="padding:10px">이전 화면</button> <a href="/" style="padding:10px">기본 배치로 돌아가기 →</a></main></body></html>''',status_code=422)


@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,exc:RequestValidationError):
    names=dict(zip(PARAMS,('온실 가로','온실 세로','구획 가로','구획 세로','구획 사이 통로','외곽 여유','중앙 통로','작업 공간')))
    names.update(crop='작물 표현',mode='보기 모드',orientation='배치 방향')
    fields=list(dict.fromkeys(names.get(str(e['loc'][-1]),'입력값') for e in exc.errors()))
    return error_page(', '.join(fields)+' 값을 허용 범위에 맞게 입력해 주세요.')


@app.get('/',response_class=HTMLResponse)
def home(mode:Mode='crop'):
    params=PRESETS[-1][2]
    return HTMLResponse(render_page(params,plan_pair(params),'original','leaf',mode))


@app.get('/layout',response_class=HTMLResponse)
@app.get('/report',response_class=HTMLResponse)
@app.get('/export.svg')
def layout(request:Request,width:Size=Decimal('10'),length:Size=Decimal('20'),
           bed_width:Size=Decimal('1'),bed_length:Size=Decimal('4'),path:Space=Decimal('.5'),
           margin:Space=Decimal(0),main_path:Space=Decimal(0),entry:Space=Decimal(0),
           orientation:Orientation='original',crop:Crop='leaf',mode:Mode='crop'):
    params=dict(width=width,length=length,bed_width=bed_width,bed_length=bed_length,path=path,
                margin=margin,main_path=main_path,entry=entry)
    try:
        plans=plan_pair(params)
    except ValueError as exc:
        return error_page(str(exc))
    if request.url.path=='/export.svg':
        return Response(make_report(params,plans,orientation,crop,mode),media_type='image/svg+xml',
                        headers={'Content-Disposition':'attachment; filename="greenhouse-report.svg"'})
    if request.url.path=='/report':
        svg=make_report(params,plans,orientation,crop,mode)
        return HTMLResponse('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>온실 배치 발표 자료</title><style>body{margin:0;background:#eaf0e2;font-family:Malgun Gothic,sans-serif}nav{padding:15px 25px;display:flex;justify-content:space-between;align-items:center;gap:15px;font-size:13px;color:#506a44}button{padding:10px 18px;background:#2b553b;color:white;border:0;border-radius:6px;cursor:pointer}.report{max-width:1200px;margin:0 auto}.report>svg{width:100%;height:auto;display:block}@page{size:A4 landscape;margin:5mm}@media print{nav{display:none}body{background:white}.report{width:100%;height:195mm}.report>svg{width:100%;height:100%}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style><nav><span>선택한 배치와 입력 조건을 한 장으로 정리했어요.</span><button onclick="window.print()">인쇄 / PDF로 저장</button></nav><main class="report">'''+svg+'</main></html>')
    return HTMLResponse(render_page(params,plans,orientation,crop,mode))


if __name__=='__main__':
    print('온실연구실: http://127.0.0.1:8000',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8000)
