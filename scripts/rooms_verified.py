"""
検証済み部屋定義（前セッションで現場確認・確定した座標）
auto抽出が信頼できない低品質スキャン時に、この確定値で清書図を出すためのモード。
良質スキャンが用意できたら run.py --mode auto に切替える。
単位m / 原点=NW内部角(0,0) / X=東+ Y=南+
"""
C_WASHI = (255, 245, 220)
C_YO = (232, 224, 240)
C_MIZU = (215, 235, 240)
C_GENK = (250, 240, 215)
C_KAID = (238, 238, 238)
C_OSI = (228, 216, 200)
C_TOKO = (252, 232, 208)
C_ROKA = (242, 242, 232)

# ── 1F ──
_W_W, _W_E, _W_N, _W_S = 0.92, 7.45, 0.67, 9.44
_X_MID1, _X_KIT_R = 4.06, 6.50
_Y_MID, _Y_MID2 = 3.29, 5.76
_rooms_1f_abs = [
    ("洋室", _W_W, _W_N, _X_MID1 - _W_W, 3.22 - _W_N, C_YO),
    ("トイレ", 4.19, _W_N, 5.02 - 4.19, 2.45 - _W_N, C_MIZU),
    ("玄関", 5.02, _W_N, 6.68 - 5.02, 2.57 - _W_N, C_GENK),
    ("物置", 6.81, _W_N, _W_E - 6.81, 2.57 - _W_N, C_OSI),
    ("和室(北)", _W_W, _Y_MID, 4.96 - _W_W, _Y_MID2 - _Y_MID, C_WASHI),
    ("玄関広間", 4.96, 2.57, 6.68 - 4.96, _Y_MID2 - 2.57, C_GENK),
    ("階段", 6.68, 3.39, _W_E - 6.68, 5.99 - 3.39, C_KAID),
    ("和室(南)", _W_W, _Y_MID2, _X_MID1 - _W_W, _W_S - _Y_MID2, C_WASHI),
    ("台所", _X_MID1, _Y_MID2, _X_KIT_R - _X_MID1, _W_S - _Y_MID2, C_WASHI),
    ("洗面脱衣", _X_KIT_R, 6.04, _W_E - _X_KIT_R, 7.69 - 6.04, C_MIZU),
    ("風呂", _X_KIT_R, 7.69, _W_E - _X_KIT_R, _W_S - 7.69, C_MIZU),
]

FLOOR_1F = {
    "rooms": [(n, x - _W_W, y - _W_N, w, h, c) for (n, x, y, w, h, c) in _rooms_1f_abs],
    "bldg_w": _W_E - _W_W,
    "bldg_h": _W_S - _W_N,
    "x_dims_top": [0, _X_MID1 - _W_W, _X_KIT_R - _W_W, _W_E - _W_W],
    "y_dims_left": [0, _Y_MID - _W_N, _Y_MID2 - _W_N, _W_S - _W_N],
}

# ── 2F ──
_NS, _TOKO, _WN, _WSE, _YS, _BE, _BS, _WSW = 2.78, 0.90, 4.75, 5.67, 1.84, 7.41, 5.56, 3.81
_STAIR_W = 0.77          # 階段幅: 1Fと同一(0.77m)に補正。旧1.74mは階段+踊り場を一括計上していた
_STAIR_X = _BE - _STAIR_W  # 東端に配置(1Fと同位置=上下階で揃う)
FLOOR_2F = {
    "rooms": [
        ("床の間", 0.0, 0.0, _TOKO, _NS, C_TOKO),
        ("和室(北)", _TOKO, 0.0, _WN - _TOKO, _NS, C_WASHI),
        ("洋室", _WN, 0.0, _BE - _WN, _YS, C_YO),
        ("廊下", _WN, _YS, _BE - _WN, _NS - _YS, C_ROKA),
        ("押入", 0.0, _NS, _TOKO, _BS - _NS, C_OSI),
        ("和室(南西)", _TOKO, _NS, _WSW - _TOKO, _BS - _NS, C_WASHI),
        ("和室(南東)", _WSW, _NS, _WSE - _WSW, _BS - _NS, C_WASHI),
        # 階段を 0.77m に絞り、余った西側(踊り場)を廊下化
        ("廊下", _WSE, _NS, _STAIR_X - _WSE, _BS - _NS, C_ROKA),
        ("階段", _STAIR_X, _NS, _STAIR_W, _BS - _NS, C_KAID),
    ],
    "bldg_w": _BE,
    "bldg_h": _BS,
    "x_dims_top": [0, _TOKO, _WN, _WSE, _STAIR_X, _BE],
    "y_dims_left": [0, _YS, _NS, _BS],
}

VERIFIED = {"1f": FLOOR_1F, "2f": FLOOR_2F}
