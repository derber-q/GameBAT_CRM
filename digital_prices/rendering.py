"""Локальный Pillow-рендерер. Вход — только PublicCatalog, без моделей и API."""
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
import math
from PIL import Image, ImageDraw, ImageFont
from .layout import COUNTRY_COLORS

REGIONS = {'turkey': 'Турция', 'poland': 'Польша', 'russia': 'Россия', 'usa': 'США',
           'uk': 'Великобритания', 'india': 'Индия', 'indonesia': 'Индонезия',
           'kazakhstan': 'Казахстан', 'ukraine': 'Украина', 'sng': 'СНГ',
           'firstmail': 'Firstmail', 'outlook': 'Outlook'}
REGION_ALIASES = {'tr': 'turkey', 'pl': 'poland', 'ru': 'russia', 'us': 'usa',
                  'xbox_usa': 'usa', 'in': 'india', 'id': 'indonesia', 'ua': 'ukraine',
                  'gb': 'uk', 'kz': 'kazakhstan', 'cis': 'sng'}

@dataclass(frozen=True)
class RenderedPage:
    filename: str
    png: bytes
    width: int
    height: int
    row_count: int
    section: str = ''
    family: str = ''


def wrap(text, font, width):
    lines, line = [], ''
    for word in str(text).split():
        candidate = line + ' ' + word if line else word
        if font.getlength(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ''
        # Слишком длинное слово переносится посимвольно без потери символов.
        for char in word:
            if line and font.getlength(line + char) > width:
                lines.append(line)
                line = ''
            line += char
    if line:
        lines.append(line)
    return lines or ['']


def _region_key(region):
    key = str(region).strip().casefold()
    key = next((code for code, label in REGIONS.items() if label.casefold() == key), key)
    return REGION_ALIASES.get(key, key)


def _star(draw, cx, cy, radius, fill):
    points = []
    for point in range(10):
        angle = -math.pi/2 + point*math.pi/5
        length = radius if point % 2 == 0 else radius*.4
        points.append((cx+math.cos(angle)*length, cy+math.sin(angle)*length))
    draw.polygon(points, fill=fill)


def _flag(draw, region, x, y):
    # Флаги рисуются без emoji-шрифтов и сети. СНГ — общий регион, не страна.
    region = _region_key(region)
    w, h = 32, 22
    if region == 'turkey':
        draw.rectangle((x, y, x+w, y+h), fill='#e84649')
        draw.ellipse((x+7, y+4, x+21, y+18), fill='white')
        draw.ellipse((x+11, y+3, x+23, y+17), fill='#e84649')
        _star(draw, x+24, y+11, 4, 'white')
    elif region in ('poland', 'russia', 'indonesia', 'ukraine', 'india'):
        stripes = {'poland': ('#ffffff', '#dc143c'),
                   'russia': ('#ffffff', '#0039a6', '#d52b1e'),
                   'indonesia': ('#ff0000', '#ffffff'),
                   'ukraine': ('#0057b7', '#ffd700'),
                   'india': ('#ff9933', '#ffffff', '#138808')}[region]
        for index, color in enumerate(stripes):
            draw.rectangle((x, y+index*h//len(stripes), x+w, y+(index+1)*h//len(stripes)), fill=color)
        if region == 'india':
            draw.ellipse((x+13, y+8, x+19, y+14), outline='#000080', width=1)
            draw.line((x+16, y+8, x+16, y+14), fill='#000080')
            draw.line((x+13, y+11, x+19, y+11), fill='#000080')
    elif region == 'usa':
        draw.rectangle((x, y, x+w, y+h), fill='white')
        for stripe in range(0, 13, 2):
            draw.rectangle((x, y+stripe*h//13, x+w, y+(stripe+1)*h//13), fill='#b22234')
        draw.rectangle((x, y, x+14, y+11), fill='#3c3b6e')
        # На иконке шириной 32 px звёзды представлены светлыми точками.
        for row in range(9):
            for column in range(6 if row % 2 == 0 else 5):
                draw.point((x+1+column*2+(row % 2), y+1+row), fill='white')
    elif region == 'uk':
        draw.rectangle((x, y, x+w, y+h), fill='#012169')
        draw.line((x, y, x+w, y+h), fill='white', width=5)
        draw.line((x, y+h, x+w, y), fill='white', width=5)
        draw.line((x, y, x+w, y+h), fill='#c8102e', width=2)
        draw.line((x, y+h, x+w, y), fill='#c8102e', width=2)
        draw.rectangle((x+12, y, x+20, y+h), fill='white')
        draw.rectangle((x, y+7, x+w, y+15), fill='white')
        draw.rectangle((x+14, y, x+18, y+h), fill='#c8102e')
        draw.rectangle((x, y+9, x+w, y+13), fill='#c8102e')
    elif region == 'sng':
        draw.ellipse((x+6, y+1, x+26, y+21), fill='#234666', outline='#96c9ef', width=1)
        draw.ellipse((x+11, y+1, x+21, y+21), outline='#96c9ef', width=1)
        draw.line((x+6, y+11, x+26, y+11), fill='#96c9ef', width=1)
    else:
        # Почтовые сервисы и неизвестные регионы не получают выдуманный флаг.
        return False
    return True


def render(catalog, *, font_directory):
    """Плотная карточная сетка по образцу: 6 регионов PS + 2 варианта Xbox."""
    from functools import lru_cache
    from .classification import region_code, REGION_ORDER
    from .layout import build_batches, group_key, order_group, order_row, card_info, slide_title, visible_subgroup
    width, height, margin, gap, top, footer = 3200, 2600, 38, 22, 160, 66
    columns = 8
    cell = (width-2*margin-gap*(columns-1))//columns
    assets = Path(font_directory).parent/'digital_prices'
    font_path = Path(font_directory)/'manrope.ttf'
    def font(size, weight=500):
        value = ImageFont.truetype(str(font_path), size)
        value.set_variation_by_axes([weight])
        return value
    body, small, title, price_font, brand = font(21), font(20), font(27,800), font(22,800), font(48,800)
    pending_price_font=font(20,800)
    at = datetime.fromisoformat(catalog.generated_at).astimezone(ZoneInfo('Europe/Moscow'))
    icon_names = {'PlayStation':'playstation','Xbox':'xbox','Apple':'apple','Valorant':'valorant',
                  'Google Play':'googleplay','Steam':'steam','Пополнение Steam':'steam','Nintendo':'nintendoswitch',
                  'Spotify':'spotify','ChatGPT':'openai','Roblox':'roblox','Battle.net':'battledotnet','Игры':'playstation'}
    @lru_cache(maxsize=100)
    def asset(kind, name):
        if not name or not all(char.isalnum() or char in '-_' for char in name):
            return None
        path = assets/kind/(name+'.png')
        if not path.is_file():
            return None
        with Image.open(path) as raw:
            return raw.convert('RGBA')
    def icon(image, family, x, y, size=48):
        key = icon_names.get(family.split(' ·')[0])
        raw = asset('icons', key) if key else None
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((x,y,x+size,y+size),radius=12,fill='#10212d',outline='#78a7b6',width=1)
        if raw:
            raw = raw.resize((size-12,size-12),Image.Resampling.LANCZOS)
            image.paste(raw,(x+6,y+6),raw)
        elif family == 'Пустые аккаунты':
            draw.rectangle((x+10,y+14,x+size-10,y+size-14),outline='white',width=2)
            draw.line((x+10,y+14,x+size//2,y+size//2,x+size-10,y+14),fill='white',width=2)
        elif family == 'Настройка':
            teeth=[(x+size/2+math.cos(i*math.pi/8)*(size*.4 if i%2==0 else size*.3),
                    y+size/2+math.sin(i*math.pi/8)*(size*.4 if i%2==0 else size*.3)) for i in range(16)]
            draw.polygon(teeth,fill='#a9d5e5')
            draw.ellipse((x+size*.35,y+size*.35,x+size*.65,y+size*.65),fill='#10212d')
        else:
            draw.text((x+10,y+5),'G' if family!='Настройка' else '+',font=title,fill='white')
    def flag(image, code, x, y):
        raw = asset('flags',region_code(code))
        if raw:
            raw=raw.resize((44,33),Image.Resampling.LANCZOS)
            image.paste(raw,(x,y),raw)
        elif code:
            _flag(ImageDraw.Draw(image),code,x+5,y+5)
    def base(section, family=''):
        if width*height>80_000_000:
            raise ValueError('Объём изображения превышает безопасный размер рендера')
        image=Image.new('RGB',(width,height),'#0b0e15');draw=ImageDraw.Draw(image)
        # Ненавязчивые геометрические детали не мешают таблицам.
        for index in range(15):
            xx=(index*487+110)%width; yy=(index*317+280)%height
            draw.ellipse((xx,yy,xx+12,yy+12),outline='#14202b',width=1)
        caption=slide_title(section, family)
        narrow=section=='codes' and width<2400
        draw.text((margin,92 if narrow else 38),caption,font=title,fill='white')
        text='GameBAT';draw.text((margin if narrow else (width-brand.getlength(text))/2,23),text,font=brand,fill='#f0c76b')
        stamp=at.strftime('%d.%m.%Y · %H:%M');draw.text((width-margin-body.getlength(stamp),40),stamp,font=body,fill='#c2ccdb')
        return image
    def prepare(row, span):
        available=cell*span+gap*(span-1)-38
        pf=pending_price_font if row.price=='Цена уточняется' else price_font
        price_width=min(205,max(120,pf.getlength(row.price)))
        pp=wrap(row.price,pf,price_width)
        nn=wrap(row.label or row.name,body,available-price_width-16)
        extra=25 if row.availability in ('unknown','no') else 0
        return row,nn,pp,pf,max(len(nn)*31,len(pp)*33)+18+extra
    def heading(info):
        available=cell*info[4]+gap*(info[4]-1)-140
        title_font=title
        lines=wrap(info[2],title_font,available)
        if len(lines)>2:
            title_font=small
            lines=wrap(info[2],title_font,available)
        head=max(100 if info[3] else 76,20+len(lines)*30+(30 if info[3] else 0))
        return title_font,lines,head
    def pieces(key, rows, *, paginate=True):
        info=card_info(key,rows);span=info[4]
        head=heading(info)[2]
        # Режим аккаунта уже вынесен в заголовок Xbox, повторять его в теле не нужно.
        prepared=[prepare(row,span) for row in sorted(rows,key=order_row)]
        current=[];used=head+12;previous=None
        for record in prepared:
            row=record[0]
            sub=visible_subgroup(row)
            addition=record[-1]+(44 if sub and sub!=previous else 0)
            if paginate and head+addition+12>height-top-footer:raise ValueError('Название слишком длинное для читаемой страницы')
            if paginate and current and used+addition>height-top-footer:
                yield info,current,used+12
                current=[];used=head+12;previous=None
                addition=record[-1]+(44 if sub else 0)
            current.append(record);used+=addition;previous=sub
        if current:yield info,current,used+12
    def paint(image, x, y, info, records, card_height):
        family,region,label,subtitle,span,color=info
        card_width=cell*span+gap*(span-1)
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((x,y,x+card_width,y+card_height),radius=24,fill='#141820',outline=color,width=2)
        title_font,title_lines,header=heading(info)
        draw.rounded_rectangle((x,y,x+card_width,y+header),radius=24,fill=color)
        draw.rectangle((x+1,y+header-22,x+card_width-1,y+header),fill=color)
        icon(image,family,x+12,y+12)
        # В заголовке сохраняется полный текст; высота учитывает переносы.
        for index,line in enumerate(title_lines):draw.text((x+72,y+12+index*28),line,font=title_font,fill='white')
        if subtitle:draw.text((x+72,y+header-32),subtitle,font=small,fill='white')
        if region:flag(image,region,x+card_width-57,y+20)
        yy=y+header+10;previous=None
        for row,names,prices,pf,rh in records:
            subgroup=visible_subgroup(row)
            if subgroup and subgroup!=previous:
                shade='#aab1bd' if subgroup=='Essential' else '#dfae27' if subgroup=='Extra' else '#d44347' if subgroup=='EA Play' else '#303743'
                draw.rounded_rectangle((x+12,yy,x+card_width-12,yy+35),radius=10,fill=shade)
                foreground='#ffd351' if subgroup in ('Deluxe','Premium') else '#18212c' if subgroup in ('Essential','Extra') else 'white'
                sx=x+(card_width-small.getlength(subgroup))/2
                draw.text((sx,yy+3),subgroup,font=small,fill=foreground)
                yy+=44
            unavailable=row.availability=='no'
            if unavailable:draw.rounded_rectangle((x+12,yy+2,x+card_width-12,yy+rh-4),radius=10,fill='#511c26')
            left=x+23
            for j,line in enumerate(names):draw.text((left,yy+6+j*31),line,font=body,fill='#bba6ae' if unavailable else '#dce1e9')
            for j,line in enumerate(prices):
                px=x+card_width-20-pf.getlength(line)
                draw.text((px,yy+5+j*33),line,font=pf,fill='#bba6ae' if unavailable else 'white')
            if unavailable:draw.line((x+18,yy+rh//2,x+card_width-18,yy+rh//2),fill='#f13a4d',width=4)
            if row.availability=='unknown':draw.text((left,yy+rh-25),'Наличие уточняется',font=small,fill='#e3b76e')
            elif unavailable:draw.text((left,yy+rh-25),'Нет в наличии',font=small,fill='#ff8292')
            draw.line((x+18,yy+rh-1,x+card_width-18,yy+rh-1),fill='#242b36',width=1)
            yy+=rh;previous=subgroup
    pages=[]
    def save(image,count,section,number,positions,family=''):
        actual=min(height,max(650,max(positions)+footer))
        image=image.crop((0,0,width,actual));draw=ImageDraw.Draw(image)
        note=f'GameBAT · {number} · Цены и наличие уточняйте при заказе'
        draw.text((margin,actual-46),note,font=small,fill='#73859d')
        buffer=BytesIO();image.save(buffer,format='PNG',optimize=True);data=buffer.getvalue()
        if len(data)>=50*1024*1024:
            raise ValueError('Изображение превышает допустимый размер PNG-файла')
        suffix=''
        if family:
            platform=family.split(' ·')[0]
            slug=icon_names.get(platform,'other')
            suffix='_'+slug+('_subscriptions' if family.endswith(' · подписки') else '_topup')
        pages.append(RenderedPage(f'GameBAT_{section}{suffix}_{at:%Y%m%d}_{number:02d}.png',
                                  data,width,actual,count,section,family))
    batches=build_batches(catalog.rows)
    numbers={'services':0,'codes':0}
    for section,batch_family,batch_rows in batches:
        groups={}
        for row in batch_rows:
            groups.setdefault(group_key(row),[]).append(row)
        if not groups:continue
        columns=8 if section=='services' else max(2,min(8,len(groups)))
        width=3200 if columns==8 else 2*margin+columns*cell+(columns-1)*gap
        height=2600
        top=190 if section=='codes' and width<2400 else 160
        # Новая платформа или тип кодов всегда начинается с новой страницы.
        # Даже при свободном месте на предыдущей странице категории не смешиваются.
        numbers[section]+=1
        number=numbers[section]
        if section=='codes':
            # Вся категория строится одним изображением. Сначала измеряем
            # блоки и ряды, затем выделяем холст нужной высоты без разрезания стран.
            cards=[card for key,rows in sorted(groups.items(),key=order_group)
                   for card in pieces(key,rows,paginate=False)]
            grid_rows=[cards[start:start+columns] for start in range(0,len(cards),columns)]
            height=max(650,top+sum(max(card[2] for card in row)+gap for row in grid_rows)+footer)
            image=base(section,batch_family);positions=[top]*columns;count=0
            row_top=top
            for row in grid_rows:
                row_height=max(card[2] for card in row)
                # Все заголовки ряда имеют один Y. Следующий ряд начинается
                # после самого высокого блока; пустые места не заполняются вразнобой.
                for column,(info,records,card_height) in enumerate(row):
                    paint(image,margin+column*(cell+gap),row_top,info,records,card_height)
                    count+=len(records)
                row_top+=row_height+gap
                positions=[row_top]*columns
            if count:save(image,count,section,number,positions,batch_family)
            numbers[section]=number
            continue
        image=base(section,batch_family);positions=[top]*columns;count=0
        for key,rows in sorted(groups.items(),key=order_group):
            for info,records,card_height in pieces(key,rows):
                family,region,_,_,span,_=info
                slots=list(range(columns-span+1))
                preferred=None
                if section=='services' and number==1:
                    if family in ('PlayStation','Игры') and region in REGION_ORDER:preferred=REGION_ORDER.index(region)
                    elif family=='Xbox':preferred=6 if key[2]=='Старый аккаунт' else 7
                    elif family in ('Пустые аккаунты','ChatGPT'):preferred=6
                    elif family in ('Пополнение Steam','Spotify'):preferred=7
                fitting=[col for col in slots if max(positions[col:col+span])+card_height<=height-footer]
                if not fitting:
                    save(image,count,section,number,positions,batch_family)
                    image=base(section,batch_family);positions=[top]*columns;count=0;number+=1;fitting=slots
                column=preferred if preferred in fitting else min(fitting,key=lambda col:(max(positions[col:col+span]),col))
                yy=max(positions[column:column+span]);xx=margin+column*(cell+gap)
                paint(image,xx,yy,info,records,card_height)
                for col in range(column,column+span):positions[col]=yy+card_height+gap
                count+=len(records)
        if count:save(image,count,section,number,positions,batch_family)
        numbers[section]=number
    return pages
