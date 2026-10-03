"""실행: python -m unittest -v (HTTP 검사에는 httpx 필요)."""
from decimal import Decimal
import unittest
from xml.etree import ElementTree

from fastapi.testclient import TestClient
from greenhouse import app, calculate_layout, make_svg, row_name, plan_pair, PRESETS, make_report


class LayoutTests(unittest.TestCase):
    def test_example_and_area_conservation(self):
        d = calculate_layout(10, 20, 1, 4, .5)
        self.assertEqual((d['columns'], d['rows'], d['count']), (7, 4, 28))
        self.assertEqual((d['bed_area'], d['path_area'], d['unused_area']), (112, 63, 25))
        self.assertEqual(d['rate'], 56)
        self.assertEqual(d['total_area'], d['bed_area'] + d['path_area'] + d['unused_area'])

    def test_wider_path_reduces_beds(self):
        d = calculate_layout(10, 20, 1, 4, 1)
        self.assertEqual((d['count'], d['bed_area'], d['rate']), (20, 80, 40))

    def test_decimal_exact_fit(self):
        d = calculate_layout('0.3', '0.3', '0.1', '0.1', 0)
        self.assertEqual(d['count'], 9)
        self.assertEqual(d['unused_area'], 0)
        self.assertEqual(d['rate'], 100)

    def test_no_outer_path(self):
        d = calculate_layout(10, 20, 10, 20, 999)
        self.assertEqual(d['count'], 1)
        self.assertEqual(d['path_area'], 0)

    def test_bed_too_large(self):
        for sizes in [(2, 3, 4, 4, .5), (2, 20, 4, 4, .5)]:
            with self.subTest(sizes=sizes):
                d = calculate_layout(*sizes)
                self.assertEqual((d['count'], d['columns'], d['rows']), (0, 0, 0))
                self.assertEqual(d['total_area'], d['unused_area'])
                self.assertEqual(d['path_area'], 0)

    def test_geometry_fits_and_is_maximal(self):
        for width in [Decimal('.3'), Decimal('4.8'), Decimal('10'), Decimal('24')]:
            for path in [Decimal(0), Decimal('.1'), Decimal('.5'), Decimal('3')]:
                with self.subTest(width=width, path=path):
                    d = calculate_layout(width, 12, '.2', '3', path)
                    self.assertLessEqual(d['used_width'], width)
                    self.assertLessEqual(d['used_length'], 12)
                    self.assertGreater(d['used_width'] + Decimal('.2') + path, width)
                    self.assertGreater(d['used_length'] + 3 + path, 12)
                    self.assertGreaterEqual(d['unused_area'], 0)
                    self.assertEqual(d['bed_area'] + d['path_area'] + d['unused_area'], d['total_area'])

    def test_dense_view_is_bounded(self):
        with self.assertRaises(ValueError):
            calculate_layout(1000, 1000, '.01', '.01', 0)

    def test_row_labels(self):
        self.assertEqual([row_name(n) for n in (0, 25, 26, 51, 52)], ['A', 'Z', 'AA', 'AZ', 'BA'])

    def test_svg_is_valid_and_matches_calculation(self):
        d = calculate_layout(10, 20, 1, 4, .5)
        root = ElementTree.fromstring(make_svg(d))
        beds = [g for g in root.iter() if g.attrib.get('class') == 'bed']
        self.assertEqual(len(beds), d['count'])
        self.assertEqual(beds[0].attrib['data-name'], 'A01')
        self.assertEqual(beds[-1].attrib['data-name'], 'D07')


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_html_and_direct_query(self):
        r = self.client.get('/layout?width=10&length=20&bed_width=1&bed_length=4&path=1')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/html', r.headers['content-type'])
        self.assertIn('id="count-value">20</strong>', r.text)
        self.assertIn('id="rate-value">40.0</strong>', r.text)

    def test_empty_layout_is_explained(self):
        r = self.client.get('/layout?width=2&length=3&bed_width=4')
        self.assertEqual(r.status_code, 200)
        self.assertIn('배치 가능한 구획이 없습니다', r.text)
        self.assertNotIn('class="bed"', r.text)

    def test_bad_input_is_explained(self):
        for query in ['width=-1', 'width=0', 'path=-1', 'width=abc', 'width=nan',
                      'width=Infinity', 'width=1001', 'width=0.01001',
                      'width=1000&length=1000&bed_width=.01&bed_length=.01&path=0']:
            with self.subTest(query=query):
                r = self.client.get('/layout?' + query)
                self.assertEqual(r.status_code, 422)
                self.assertIn('입력값을 확인해 주세요', r.text)

    def test_input_does_not_inject_html(self):
        r = self.client.get('/layout', params={'width': '<script>alert(1)</script>'})
        self.assertEqual(r.status_code, 422)
        self.assertNotIn('<script>alert(1)</script>', r.text)

    def test_new_home_and_direct_rotation(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="count-value">24</strong>', response.text)
        params = dict(PRESETS[-1][2], orientation='rotated')
        response = self.client.get('/layout', params=params)
        self.assertIn('id="count-value">28</strong>', response.text)

    def test_reserved_space_validation(self):
        for query in ['margin=5', 'margin=1&main_path=8', 'entry=20', 'margin=-1',
                      'entry=nan', 'main_path=-1', 'orientation=bad', 'crop=bad', 'mode=bad']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/layout?' + query).status_code, 422)

    def test_report_export_matches_selected_orientation(self):
        params = dict(PRESETS[-1][2], orientation='rotated', mode='blueprint', crop='strawberry')
        r = self.client.get('/export.svg', params=params)
        self.assertEqual(r.status_code, 200)
        self.assertIn('image/svg+xml', r.headers['content-type'])
        self.assertIn('attachment', r.headers['content-disposition'])
        root = ElementTree.fromstring(r.text)
        self.assertEqual(root.attrib['viewBox'], '0 0 1200 1020')
        beds = [g for g in root.iter() if g.attrib.get('class') == 'bed']
        self.assertEqual(len(beds), 28)
        self.assertIn('28 개', r.text)
        self.assertIn('딸기 (장식)', r.text)
        self.assertIn('greenhouse-svg blueprint', r.text)
        self.assertIn('남는 공간', r.text)
        report = self.client.get('/report', params=params)
        self.assertEqual(report.status_code, 200)
        self.assertIn('window.print()', report.text)


class ReservedSpaceTests(unittest.TestCase):
    def test_reserved_area_conservation(self):
        for _, _, params in PRESETS:
            for orientation, d in plan_pair(params).items():
                with self.subTest(params=params, orientation=orientation):
                    parts = [d[k] for k in ['bed_area', 'path_area', 'entry_area', 'margin_area', 'unused_area']]
                    self.assertEqual(sum(parts), d['total_area'])
                    self.assertTrue(all(v >= 0 for v in parts))
                    self.assertEqual(len(d['beds']), d['count'])
                    self.assertEqual(len({b['name'] for b in d['beds']}), d['count'])

    def test_beds_do_not_overlap_reserved_spaces_or_each_other(self):
        def overlap(a, b):
            return a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width'] and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height']
        for _, _, params in PRESETS:
            for d in plan_pair(params).values():
                m, a, e = d['margin'], d['main_path'], d['entry']
                for i, bed in enumerate(d['beds']):
                    self.assertGreaterEqual(bed['x'], m)
                    self.assertGreaterEqual(bed['y'], m)
                    self.assertLessEqual(bed['x'] + bed['width'], d['width'] - m)
                    self.assertLessEqual(bed['y'] + bed['height'], d['length'] - m - e)
                    if a:
                        aisle = dict(x=(d['width']-a)/2,y=m,width=a,height=d['grow_height'])
                        self.assertFalse(overlap(bed, aisle))
                    for other in d['beds'][i+1:]:
                        self.assertFalse(overlap(bed, other))

    def test_rotation_does_not_rotate_aisle_or_change_reservations(self):
        pair = plan_pair(PRESETS[-1][2])
        a,b = pair['original'],pair['rotated']
        self.assertEqual((a['count'],b['count']), (24,28))
        self.assertEqual(a['bed_width'],b['bed_length'])
        self.assertEqual(a['bed_length'],b['bed_width'])
        for key in ['width','length','main_path','margin','entry','margin_area','entry_area']:
            self.assertEqual(a[key],b[key])

    def test_empty_layout_keeps_reserved_area(self):
        d = calculate_layout(10,20,30,30,.5,margin=.5,main_path=1,entry=2)
        self.assertEqual(d['count'],0)
        self.assertEqual(d['margin_area'],29)
        self.assertEqual(d['entry_area'],18)
        self.assertEqual(d['path_area'],17)
        self.assertEqual(d['unused_area'],136)

    def test_only_rotated_direction_fits(self):
        params=dict(width=3,length=6,bed_width=4,bed_length=2,path=.5,margin=0,main_path=0,entry=0)
        pair=plan_pair(params)
        self.assertEqual(pair['original']['count'],0)
        self.assertEqual(pair['rotated']['count'],1)


if __name__ == '__main__':
    unittest.main()
