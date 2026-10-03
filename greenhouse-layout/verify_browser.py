"""실행 중인 localhost 앱에 대한 실제 브라우저 검사.

선택 설치: python -m pip install playwright pypdf
실행: python verify_browser.py
기존 Chrome과 분리된 headless 브라우저를 사용합니다.
"""
from pathlib import Path
from xml.etree import ElementTree
import struct
from playwright.sync_api import sync_playwright
from pypdf import PdfReader


def run():
    output=Path(__file__).parent/'artifacts'
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.goto('http://127.0.0.1:8000/',wait_until='networkidle')
        assert page.locator('#count-value').inner_text()=='24'
        assert page.locator('#margin').get_attribute('value')=='0.5'
        assert page.locator('label[for="margin"]').inner_text()=='외곽 여유 폭'
        page.screenshot(path=str(output/'v2-desktop.png'),full_page=True)
        page.locator('[data-mode="blueprint"]').click()
        assert 'blueprint' in page.locator('#plan-svg').get_attribute('class')
        assert page.locator('#plan-svg .plants').first.is_hidden()
        assert page.locator('#plan-svg .draft-dimension').first.is_visible()
        assert 'mode=blueprint' in page.url
        page.screenshot(path=str(output/'v2-blueprint.png'),full_page=True)
        page.locator('.compare-option').nth(1).click()
        assert page.locator('#count-value').inner_text()=='28'
        assert 'blueprint' in page.locator('#plan-svg').get_attribute('class')
        page.locator('#plan-svg .bed').first.click()
        assert 'A01' in page.locator('#selected-title').inner_text()
        page.locator('#plan-svg .bed').nth(1).focus()
        page.keyboard.press('Enter')
        assert page.locator('#selected-title').inner_text().endswith('선택됨')
        before=page.locator('#plan-svg').get_attribute('viewBox')
        page.locator('#zoom-in').click();page.locator('#zoom-in').click()
        assert page.locator('#zoom-value').inner_text()=='150%'
        box=page.locator('#plan-svg').bounding_box()
        x,y=box['x']+box['width']/2,box['y']+box['height']/2
        prior=page.locator('#plan-svg').get_attribute('viewBox')
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+60,y+30,steps=8);page.mouse.up()
        assert page.locator('#plan-svg').get_attribute('viewBox')!=prior
        page.locator('#zoom-fit').click()
        assert page.locator('#plan-svg').get_attribute('viewBox')==before
        page.locator('#focus-toggle').click()
        assert page.locator('.workspace>aside').is_hidden()
        assert page.locator('.comparison').is_hidden()
        page.locator('#focus-toggle').click()
        assert page.locator('.workspace>aside').is_visible()
        page.locator('#fullscreen').click()
        page.wait_for_function('document.fullscreenElement !== null')
        assert page.evaluate('document.fullscreenElement.id')=='plan-card'
        page.locator('#fullscreen').click()
        page.wait_for_function('document.fullscreenElement === null')
        with page.expect_download() as download:
            page.locator('#download-svg').click()
        svg_path=output/'greenhouse-report.svg'
        download.value.save_as(str(svg_path))
        root=ElementTree.parse(svg_path).getroot()
        assert root.attrib['viewBox']=='0 0 1200 1020'
        assert len([el for el in root.iter() if el.attrib.get('class')=='bed'])==28
        with page.expect_download(timeout=20000) as download:
            page.locator('#download-png').click()
        png_path=output/'greenhouse-report.png'
        download.value.save_as(str(png_path))
        assert struct.unpack('>II',png_path.read_bytes()[16:24])==(2400,2040)
        with page.expect_popup() as opened:
            page.locator('#print-report').click()
        report=opened.value
        report.wait_for_load_state('networkidle')
        assert '90° 회전' in report.locator('.report').inner_text()
        report.set_viewport_size({'width':1240,'height':1120})
        report.screenshot(path=str(output/'v2-report.png'),full_page=True)
        report.pdf(path=str(output/'greenhouse-report.pdf'),prefer_css_page_size=True,print_background=True)
        assert len(PdfReader(output/'greenhouse-report.pdf').pages)==1
        report.close()
        page.locator('#crop').select_option('strawberry')
        assert page.locator('#dirty-note').is_visible()
        page.locator('.apply').click();page.wait_for_load_state('networkidle')
        assert 'crop=strawberry' in page.url
        assert page.locator('#count-value').inner_text()=='28'
        page.locator('[data-mode="crop"]').click()
        assert page.locator('#plan-svg .plants').first.is_visible()
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(output/'v2-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#zoom-in').click();page.locator('#zoom-fit').click()
        for preset in range(4):
            page.locator('.preset').nth(preset).click()
            page.wait_for_load_state('networkidle')
            assert page.locator('#plan-svg').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.goto('http://127.0.0.1:8000/layout?width=3&length=6&bed_width=4&bed_length=2')
        assert page.locator('.empty-state').is_visible()
        page.locator('.compare-option').nth(1).click()
        assert page.locator('#count-value').inner_text()=='1'
        assert page.locator('.empty-state').count()==0
        response=page.goto('http://127.0.0.1:8000/layout?margin=8')
        assert response.status==422
        assert not errors,errors
        print('PASS: orientation comparison, blueprint/crop modes, selection, keyboard, zoom/pan, panel toggle, fullscreen, SVG/PNG, single-page PDF, crop selection, mobile, presets and validation.')
        browser.close()


if __name__=='__main__':
    run()
