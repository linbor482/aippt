"""Independent layout families. Geometry is shared by preview and PPTX export."""
import re
from presentation_design import _text, _rect, _units

STYLES = {
    'default': ('#F3F6FA', '#163451', '#2863DC', '#65768A'),
    'modern': ('#FCFBF8', '#222923', '#527B56', '#74796F'),
    'creative': ('#FFF4DF', '#302556', '#EF603F', '#6D5F7C'),
    'luxury': ('#142C29', '#F6F3E7', '#C9E596', '#B0C3B7'),
}


def cover(s, title, subtitle, final, t, ink, a, muted):
    if t == 'default':
        _rect(s, 0, 0, .25, 7.5, a)
        _rect(s, 9.2, 0, 4.13, 7.5, '#163451')
        for j in range(3):
            _rect(s, 9.7, 2.25+j*.94, 2.9-j*.6, .55, ['#2863DC','#5484DF','#AEC7EF'][j])
        _text(s, title, .85, 2.12, 7.8, 2.1, 45, ink, True)
        _rect(s, .85, 4.62, 1.05, .06, a)
        _text(s, subtitle, .85, 5.0, 7.65, 1.12, 21, ink)
        _text(s, 'Q&A' if final else 'BRIEF', 9.7, 5.75, 3, .6, 28, '#FFFFFF', True)
    elif t == 'modern':
        _rect(s, .8, 1.3, 11.7, .012, '#CDD1C7')
        _text(s, 'Q&A' if final else '01', 10.1, 1.55, 2.4, 1.1, 58, '#D5DBD0', False, 'Georgia')
        _text(s, title, .8, 2.6, 10.5, 2.05, 48, ink, False, 'Microsoft YaHei Light')
        _text(s, subtitle, 5.45, 5.14, 7.0, 1.15, 20, muted)
        _rect(s, .8, 5.27, 2.0, .035, a)
    elif t == 'creative':
        _rect(s, 8.45, .85, 4.1, 4.1, '#B4A3E5', 'ellipse')
        _rect(s, 9.65, 3.55, 2.65, 2.65, a)
        _rect(s, 8.05, 4.8, 1.35, 1.35, '#EABC38', 'ellipse')
        _text(s, title, .7, 2.55, 7.4, 2.4, 53, ink, True)
        _text(s, subtitle, .7, 5.42, 7.2, 1.0, 21, ink)
        _text(s, '+' if final else '*', 9.13, 1.23, 2.6, 2.8, 135, ink, True, 'Arial')
    else:
        _rect(s, 8.65, 0, 4.68, 7.5, '#25483F')
        for j in range(4):
            _rect(s, 9.1+j*.78, 1.55+j*.55, .035, 3.7-j*.45, '#547465')
        _rect(s, 9.1, 5.3, 3.15, .035, a)
        _text(s, 'Q / A' if final else '01', 9.05, 2.7, 3.15, 1.6, 84, a, False, 'Georgia')
        _text(s, title, .75, 2.07, 7.35, 2.65, 48, ink, True)
        _text(s, subtitle, .75, 5.13, 7.0, 1.1, 21, muted)


def content(s, title, items, layout, with_image, t, ink, a, muted, page):
    count = max(1, len(items))
    x, top, width, height = .75, 2.52, 11.8, 3.95
    if t == 'default':
        _rect(s, 0, 0, .22, 7.5, a)
        _text(s, title, .75, 1.1, 11.8, .98, 33, ink, True)
    elif t == 'modern':
        _text(s, title, .75, 1.2, 11.8, .95, 35, ink, False, 'Microsoft YaHei Light')
        _rect(s, .75, 2.28, 11.8, .012, '#CDD1C7')
    elif t == 'creative':
        _rect(s, 11.15, .25, 1.7, 1.7, '#B4A3E5', 'ellipse')
        _text(s, title, .75, 1.1, 10.3, 1.05, 38, ink, True)
        _rect(s, .75, 2.18, 1.1, .08, a)
    else:
        _rect(s, 0, 0, 3.52, 6.85, '#203D35')
        _text(s, title, .6, 1.55, 2.42, 3.0, 29, ink, True)
        _text(s, page, .6, 5.47, 2.2, 1.0, 48, a, False, 'Georgia')
        x, top, width, height = 4.0, 1.04, 8.55, 5.25
    if with_image:
        width = 4.15 if t == 'luxury' else 7.05
        image_x = 8.65 if t == 'luxury' else 8.45
        s['image'] = dict(x=image_x, y=top, w=3.9 if t == 'luxury' else 4.1, h=height)
        _rect(s, image_x, top, s['image']['w'], height, '#335147' if t == 'luxury' else '#E5E7E1')
        _text(s, 'IMAGE', image_x+.3, top+height/2-.2, 3.0, .4, 15, muted)
        for el in s['elements'][-2:]:
            el['role'] = 'image-placeholder'
        layout = 'editorial'
    s['layout'] = layout
    if layout == 'timeline':
        if t in ('modern', 'luxury'):
            row = height/count
            _rect(s, x+.08, top+.1, .018, height-.25, muted)
            for j, item in enumerate(items):
                y = top+j*row
                _rect(s, x, y+.1, .18, .18, a, 'ellipse')
                dated = bool(re.match(r'^\d{4}\b', item))
                _text(s, item[:4] if dated else f'{j+1:02d}', x+.4, y, 1.18, .48, 24, a, True)
                _text(s, item[4:].strip() if dated else item, x+1.85, y, width-1.85, row-.2, 22, ink)
        else:
            cell = width/count
            _rect(s, x, top+1.02, width-.2, .03, a)
            for j, item in enumerate(items):
                xx = x+j*cell
                dated = bool(re.match(r'^\d{4}\b', item))
                _text(s, item[:4] if dated else f'{j+1:02d}', xx, top+.16, cell-.22, .6, 30, ink, True)
                _rect(s, xx, top+.92, .23, .23, a, 'ellipse' if t == 'creative' else 'rect')
                _text(s, item[4:].strip() if dated else item, xx, top+1.5, cell-.35, height-1.6, 22, ink)
    elif layout == 'columns':
        cell = width/count
        for j, item in enumerate(items):
            xx = x+j*cell
            offset = .22*(j%2) if t == 'creative' else 0
            yy = top+offset
            if t in ('default', 'creative', 'luxury'):
                fill = '#FFFFFF' if t == 'default' else ('#25473C' if t == 'luxury' else ['#E6DDF5','#F6CDBB','#F3E4A1'][j%3])
                _rect(s, xx, yy, cell-.2, height-offset, fill)
                if t == 'default':
                    _rect(s, xx, yy, cell-.2, .05, a)
            _text(s, f'{j+1:02d}', xx+.2, yy+.24, cell-.6, .78, 37, a if t!='creative' else ink, True, 'Georgia' if t=='modern' else 'Microsoft YaHei')
            _text(s, item, xx+.2, yy+1.44, cell-.6, height-offset-1.64, 23, ink)
    else:
        row = height/count
        for j, item in enumerate(items):
            yy = top+j*row
            if t == 'default':
                _rect(s, x, yy, width, row-.15, '#FFFFFF')
                _rect(s, x, yy, .055, row-.15, a)
            elif t == 'creative':
                _rect(s, x+.1*(j%2), yy, width-.1, row-.15, ['#E6DDF5','#F6CDBB','#F3E4A1','#DCE8D2'][j%4])
            else:
                _rect(s, x, yy+row-.12, width, .012, '#CDD1C7' if t=='modern' else '#466054')
            _text(s, f'{j+1:02d}', x+.18, yy+.12, .64, .48, 21, a if t!='creative' else ink, True)
            _text(s, item, x+1.02, yy+.12, width-1.23, row-.28, 23, ink)


def design_scene(data, slide, items, part, source_index, index, total, template, image_mode):
    paper, ink, accent, muted = STYLES[template]
    scene = dict(background=paper, elements=[], sourceIndex=source_index, layout='cover', style=template)
    title = str(slide.get('title', '')) + (' / continued' if part else '')
    if slide.get('type') in ('cover', 'final'):
        cover(scene, title, ' / '.join(items), slide.get('type')=='final', template, ink, accent, muted)
    else:
        layout = slide.get('layout', 'auto')
        if layout == 'auto':
            layout = 'timeline' if items and all(re.match(r'^\d{4}\b', item) for item in items) else ('columns' if len(items)<=3 else 'editorial')
        if layout not in ('columns', 'timeline', 'editorial') or any(_units(item)>72 for item in items):
            layout = 'editorial'
        content(scene, title, items, layout, image_mode in ('blank','real','ai'), template, ink, accent, muted, f'{index+1:02d}')
    return scene
