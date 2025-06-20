from datetime import time

STITCHING_START = time(hour=8, minute=30)
STITCHING_END = time(hour=17, minute=30)

operationSections = [
        {'value': None, 'text': 'All',},
        {'value': 'SP', 'text': 'Small Parts',},
        {'value': 'B', 'text': 'Back',},
        {'value': 'F', 'text': 'Front',},
        {'value': 'A1', 'text': 'Assembly 1',},
        {'value': 'A2', 'text': 'Assembly 2',},
        {'value': 'FIN', 'text': 'Finishing',},
]

operationCategories = [
    {'value': 'Hemming', 'text': 'Hemming'},
    {'value': 'Tracing', 'text': 'Tracing'},
    {'value': 'Over Lock', 'text': 'Over Lock'},
    {'value': 'Attach', 'text': 'Attach'},
    {'value': 'Top Stitch', 'text': 'Top Stitch'},
    {'value': 'Press', 'text': 'Press'},
    {'value': 'Set Stitch', 'text': 'Set Stitch'},
    {'value': 'Safety', 'text': 'Safety'},
    {'value': 'Tacking Stitch', 'text': 'Tacking Stitch'},
    {'value': 'Feedo', 'text': 'Feedo'},
    {'value': 'Deco Stitch', 'text': 'Deco Stitch'},
    {'value': 'J Stitch', 'text': 'J Stitch'},
    {'value': 'Clipping', 'text': 'Clipping'},
    {'value': 'Turn Up', 'text': 'Turn Up'},
    {'value': 'Bartack', 'text': 'Bartack'},
    {'value': 'Eyelet', 'text': 'Eyelet'},
    {'value': 'CBE', 'text': 'CBE'},
    {'value': 'Loop', 'text': 'Loop'},
    {'value': 'Matching', 'text': 'Matching'},
    {'value': 'Mock', 'text': 'Mock'},
    {'value': 'Buffer', 'text': 'Buffer'},
]

machineTypes = [
    {'value': 'null', 'text': 'All',},
    {'value': 'SNLS', 'text': 'Single Needle Lock Stitch',},
    {'value': 'DNLS', 'text': 'Double Needle Lock Stitch',},
    {'value': 'Manu', 'text': 'Manual',},
    {'value': 'OL', 'text': 'Overlock',},
    {'value': 'SFTY', 'text': 'Safety',},
    {'value': 'Feedo', 'text': 'Feed of Arm',},
    {'value': 'BTK', 'text': 'Bartack',},
    {'value': 'Eyelet', 'text': 'Eyelet',},
    {'value': 'WB', 'text': 'Waistband',},
    {'value': 'Loop', 'text': 'Loop Machine',},
    {'value': 'SNCS', 'text': 'Single Needle Chain Stitch',},
    {'value': 'DNCS', 'text': 'Double Needle Chain Stitch',},
    {'value': 'Buffer', 'text': 'Buffer',},
    {'value': 'AutoBone', 'text': 'Auto Bone',},
    {'value': 'CoverStitch', 'text': 'Cover Stitch',},
    {'value': 'Flat', 'text': 'Flat Lock',},
    {'value': 'Plotter', 'text': 'Plotter',},
    {'value': 'Template', 'text': 'Template',},
    {'value': 'ZigZag', 'text': 'Zig Zag',},
]

machineManufacturers = [
    {'value': 'null', 'text': 'All'},
    {'value': 'Baoyu', 'text': 'Baoyu'},
    {'value': 'Zoje', 'text': 'Zoje'},
    {'value': 'Juki', 'text': 'Juki'},
    {'value': 'Brother', 'text': 'Brother'},
    {'value': 'Kansai', 'text': 'Kansai'},
    {'value': 'XTypical', 'text': 'X Typical'},
    {'value': 'Siruba', 'text': 'Siruba'},
    {'value': 'Typical', 'text': 'Typical'},
    {'value': 'Duma', 'text': 'Duma'},
    {'value': 'Lijia', 'text': 'Lijia'},
    {'value': 'Pegasus', 'text': 'Pegasus'},
    {'value': 'GoldenWheel', 'text': 'Golden Wheel'},
    {'value': 'AGM', 'text': 'AGM'},
    {'value': 'Jack', 'text': 'Jack'},
    {'value': 'AMFReece', 'text': 'AMF Reece'},
    {'value': 'DUMA', 'text': 'DUMA'},
    {'value': 'WOOSUN', 'text': 'WOOSUN'},
    {'value': 'Oxford', 'text': 'Oxford'},
    {'value': 'Gintex', 'text': 'Gintex'},
    {'value': 'Algotex', 'text': 'Algotex'},
    {'value': 'Fabcare', 'text': 'Fabcare'},
]

changeOverTimes = {
    'AutoBone': 4,
    'BTK': 1,
    'CoverStitch': 1,
    'DNCS': 0.5,
    'DNLS': 0.3,
    'Eyelet': 0.5,
    'Feedo': 3,
    'Flat': 4,
    'Loop': 0.3,
    'OL': 1,
    'SFTY': 0.5,
    'SNCS': 0.5,
    'SNLS': 0.3,
    'WB': 3,
    'ZigZag': 4,
    'Manu': 0,
}

stitchingLines = [
    {'value': 'B', 'text':'Blue'},
    {'value': 'G', 'text':'Green'},
]