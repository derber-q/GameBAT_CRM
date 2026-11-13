"""Общий порядок слайдов, блоков, строк и цветов для PNG и каталога CRM."""
from .classification import region_code, REGION_ORDER, row_sort

# Постоянная палитра регионов. Цвет не зависит от платформы, порядка импорта
# или набора стран в конкретном прайсе; первые шесть цветов сохранены по образцу.
COUNTRY_COLORS = {
    'ae': '#1b941b', 'ar': '#151573', 'at': '#735b15', 'au': '#d16994',
    'be': '#6b1573', 'bh': '#81944a', 'br': '#1b9494', 'ca': '#5221b5',
    'ch': '#731524', 'cn': '#d126d1', 'co': '#15735b', 'cz': '#b769d1',
    'de': '#1b4d94', 'es': '#b5715b', 'eu': '#487339', 'fi': '#7a69d1',
    'fr': '#944a7b', 'gb': '#d12698', 'global': '#53647b', 'gr': '#2634d1',
    'hk': '#5b8fb5', 'hr': '#4a9463', 'hu': '#73394d', 'id': '#9638b4',
    'ie': '#6b941b', 'in': '#cc731d', 'iq': '#393973', 'it': '#94391b',
    'jp': '#941b8a', 'kr': '#946b32', 'kw': '#268ad1', 'kz': '#941b57',
    'lb': '#6f4a94', 'lu': '#5e47d1', 'mx': '#7b26d1', 'my': '#4a948e',
    'ng': '#d14226', 'nl': '#2f1b94', 'no': '#d14775', 'nz': '#347315',
    'om': '#327394', 'ph': '#d147ba', 'pl': '#bb3358', 'pt': '#329443',
    'qa': '#b5513e', 'ro': '#157334', 'ru': '#b521b5', 'sa': '#948a1b',
    'se': '#6e7339', 'sg': '#b53e8d', 'sk': '#441573', 'sng': '#b99a13',
    'th': '#603973', 'tr': '#b92030', 'tw': '#275a73', 'ua': '#944a50',
    'us': '#3e64c5', 'vn': '#1b946b', 'za': '#4a4a94',
}


priority = {'PlayStation':0,'Xbox':1,'Игры':2,'Пустые аккаунты':3,'Пополнение Steam':4,'Spotify':5,'ChatGPT':6,'Настройка':7}
plans = {'Essential':0,'Extra':1,'Deluxe':2,'Premium':2,'EA Play':3,
         'Core':0,'PC':1,'Ultimate':3,'Ручные тарифы':0,'Валюты API':1}

def group_key(row):
    family=row.family or row.category
    code=region_code(row.region)
    if row.section=='codes':return family,code,''
    if family=='PlayStation' or family=='Игры':return family,code,''
    if family=='Xbox':return family,'',row.subgroup
    return family,'',''
def order_group(item):
    (family,region,mode),members=item
    if members[0].section=='codes':
        # Внутри отдельного платформенного блока идут только страны,
        # без примешивания избранных карточек других сервисов.
        primary=0
    else:primary=priority.get(family,20)
    rr=REGION_ORDER.index(region) if region in REGION_ORDER else len(REGION_ORDER)
    return primary,rr,region,0 if mode=='Старый аккаунт' else 1,mode,family
def order_row(row):
    group=plans.get(row.subgroup,10)
    label=row.label or row.name
    if row.family=='Spotify':
        group=next((i for i,plan in enumerate(['individual','duo','family']) if label.casefold().startswith(plan)),10)
    if row.family=='Пополнение Steam' and row.subgroup=='Ручные тарифы':group=-1
    return group,row.order,row_sort(label)


def visible_subgroup(row):
    """Клиент не видит технические отметки об источнике тарифов."""
    if row.family == 'Xbox' or row.subgroup in ('Ручные тарифы', 'Валюты API'):
        return ''
    return row.subgroup
def card_info(key, rows):
    family,region,mode=key
    is_code=rows[0].section=='codes'
    span=2 if family=='Настройка' and not is_code else 1
    if is_code:
        label=family;subtitle='Коды '+(rows[0].region_label or region or 'Global')
    elif family=='PlayStation':label='PS — '+(rows[0].region_label or region);subtitle=''
    elif family=='Xbox':label='Xbox — '+mode;subtitle=''
    elif family=='Игры':label='Игры '+(rows[0].region_label or region);subtitle=''
    else:label=family;subtitle=''
    color=COUNTRY_COLORS.get(region_code(region),'#247d99') if region else '#247d99'
    if not region:
        if family.startswith('Xbox') or family=='Spotify':color='#218d2b'
        elif family=='Пустые аккаунты':color='#a0652b'
        elif family=='ChatGPT':color='#315b99'
    return family,region,label,subtitle,span,color

def build_batches(rows):
    batches=[('services','',[row for row in rows if row.section=='services'])]
    code_families={}
    for row in rows:
        if row.section=='codes':
            code_families.setdefault(row.family or row.category,[]).append(row)
    platforms=['PlayStation','Xbox','Nintendo','Steam','Apple','Google Play','Valorant','Roblox','Battle.net','ChatGPT']
    def family_order(family):
        platform=family.split(' ·')[0]
        return (platforms.index(platform) if platform in platforms else len(platforms),
                1 if family.endswith(' · подписки') else 0,family)
    batches.extend(('codes',family,code_families[family]) for family in sorted(code_families,key=family_order))
    return batches


def slide_title(section, family):
    if section == "services":
        return "Главная"
    kind = "Коды подписок" if family.endswith(" · подписки") else "Коды пополнения"
    return family.split(" ·")[0] + " — " + kind
