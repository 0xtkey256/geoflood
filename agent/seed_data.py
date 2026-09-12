"""
Sample critical-infrastructure graph for the lower Arakawa / eastern Tokyo lowlands.
*** Sample data for the hackathon demo — names & coordinates are illustrative, not real assets. ***
"""

AREAS = {
    "荒川下流": {"west": 139.76, "south": 35.65, "east": 139.90, "north": 35.80,
              "desc": "足立区・葛飾区・江戸川区・墨田区・江東区の低地（海抜ゼロメートル地帯）"},
    "江東・墨田": {"west": 139.78, "south": 35.64, "east": 139.86, "north": 35.72,
              "desc": "江東区・墨田区"},
    "多摩川下流": {"west": 139.66, "south": 35.52, "east": 139.78, "north": 35.60,
              "desc": "大田区・川崎市"},
}
DEFAULT_AREA = "荒川下流"

FACILITIES = [
    # substations (sample)
    {"id": "SUB-01", "name": "北千住変電所(sample)", "type": "substation", "lat": 35.7490, "lon": 139.8050},
    {"id": "SUB-02", "name": "亀有変電所(sample)",   "type": "substation", "lat": 35.7610, "lon": 139.8480},
    {"id": "SUB-03", "name": "西葛西変電所(sample)", "type": "substation", "lat": 35.6640, "lon": 139.8590},
    {"id": "SUB-04", "name": "錦糸町変電所(sample)", "type": "substation", "lat": 35.6970, "lon": 139.8140},
    {"id": "SUB-05", "name": "赤羽変電所(sample)",   "type": "substation", "lat": 35.7780, "lon": 139.7210},
    # hospitals (sample)
    {"id": "HOS-01", "name": "綾瀬総合病院(sample)", "type": "hospital", "lat": 35.7620, "lon": 139.8250},
    {"id": "HOS-02", "name": "新小岩病院(sample)",   "type": "hospital", "lat": 35.7160, "lon": 139.8580},
    {"id": "HOS-03", "name": "葛西中央病院(sample)", "type": "hospital", "lat": 35.6630, "lon": 139.8730},
    {"id": "HOS-04", "name": "上野台地病院(sample)", "type": "hospital", "lat": 35.7120, "lon": 139.7770},
    {"id": "HOS-05", "name": "赤羽台病院(sample)",   "type": "hospital", "lat": 35.7800, "lon": 139.7180},
    # shelters (sample)
    {"id": "SHL-01", "name": "堀切避難所(sample)",   "type": "shelter", "lat": 35.7440, "lon": 139.8270},
    {"id": "SHL-02", "name": "平井避難所(sample)",   "type": "shelter", "lat": 35.7060, "lon": 139.8420},
    {"id": "SHL-03", "name": "竹ノ塚避難所(sample)", "type": "shelter", "lat": 35.7920, "lon": 139.7920},
    {"id": "SHL-04", "name": "王子台地避難所(sample)", "type": "shelter", "lat": 35.7530, "lon": 139.7380},
]

# (from, rel, to)  — hospitals/shelters draw power from a substation; shelters serve wards
RELATIONS = [
    ("HOS-01", "POWERED_BY", "SUB-01"),
    ("HOS-02", "POWERED_BY", "SUB-02"),
    ("HOS-03", "POWERED_BY", "SUB-03"),
    ("HOS-04", "POWERED_BY", "SUB-01"),  # upland hospital fed by lowland substation -> cascade risk
    ("HOS-05", "POWERED_BY", "SUB-05"),
    ("SHL-01", "POWERED_BY", "SUB-01"),
    ("SHL-02", "POWERED_BY", "SUB-04"),
    ("SHL-03", "POWERED_BY", "SUB-02"),
    ("SHL-04", "POWERED_BY", "SUB-05"),
    ("SUB-02", "BACKUP_OF", "SUB-01"),
    ("SUB-04", "BACKUP_OF", "SUB-03"),
    ("SUB-05", "BACKUP_OF", "SUB-02"),
]
