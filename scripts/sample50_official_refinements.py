from __future__ import annotations

from dataclasses import replace

from sample50_validate import Action


# Exchange/company implementation-announcement values used in the ex-right reference
# formula.  These are deliberately separate from the nominal Eastmoney event feed:
# nominal cash/bonus terms are useful discovery data, but repurchase accounts,
# compensation shares and other non-participating shares require the virtual/effective
# distribution used by the exchange reference-price calculation.
REFINEMENTS = {
    ('002236.SZ', '2023-11-16'): {'cash_per_share': 0.3082725},
    ('002236.SZ', '2024-05-22'): {'cash_per_share': 0.3797018},
    ('002236.SZ', '2024-09-20'): {'cash_per_share': 0.1828923},
    ('002236.SZ', '2025-04-30'): {'cash_per_share': 0.4552485},
    ('002236.SZ', '2025-12-09'): {'cash_per_share': 0.1829635},

    ('300827.SZ', '2025-07-04'): {
        'cash_per_share': 0.1190897,
        'cap_ratio': 0.3969656,
    },

    ('600232.SH', '2022-05-09'): {
        'cash_per_share': 357_009_202 * 0.2 / 364_718_544,
    },

    ('002318.SZ', '2022-05-26'): {
        'cash_per_share': 960_370_655 * 0.4 / 977_170_720,
    },
    ('002318.SZ', '2024-05-30'): {
        'cash_per_share': 462_036_124.80 / 977_170_720,
    },
    ('002318.SZ', '2025-04-24'): {'cash_per_share': 0.9416660},

    ('002627.SZ', '2022-07-11'): {
        'cash_per_share': 730_887_462 * 0.1 / 738_148_117,
    },
    ('002627.SZ', '2024-06-14'): {'cash_per_share': 0.0933948},
    ('002627.SZ', '2025-06-27'): {'cash_per_share': 0.0951409},

    ('601225.SH', '2021-07-09'): {'cash_per_share': 0.7756},

    ('002001.SZ', '2022-05-25'): {
        'cash_per_share': 0.7 * (2_562_562_984 / 2_578_394_760),
        'cap_ratio': 0.2 * (2_562_562_984 / 2_578_394_760),
    },
    ('002001.SZ', '2023-06-14'): {'cash_per_share': 0.4971714},
    ('002001.SZ', '2024-05-29'): {'cash_per_share': 0.4474542},
    ('002001.SZ', '2025-05-21'): {'cash_per_share': 0.4997937},
    ('002001.SZ', '2025-10-20'): {'cash_per_share': 0.1990358},

    ('301327.SZ', '2024-10-11'): {'cash_per_share': 0.2810802},
    ('301327.SZ', '2025-05-30'): {
        'cash_per_share': 1.15 * (123_953_391 / 124_800_000),
        'cap_ratio': 0.4 * (123_953_391 / 124_800_000),
    },

    ('002658.SZ', '2021-10-19'): {'cash_per_share': 0.1476181},
    ('002658.SZ', '2024-05-22'): {'cash_per_share': 0.2946946},
    ('002658.SZ', '2025-04-30'): {'cash_per_share': 0.2455788},

    ('600641.SH', '2021-07-13'): {
        'cash_per_share': 910_629_936 * 0.105 / 957_930_404,
    },
    ('600641.SH', '2022-07-15'): {'cash_per_share': 0.1185},
    ('600641.SH', '2024-08-22'): {'cash_per_share': 0.0489},
    ('600641.SH', '2025-07-11'): {'cash_per_share': 0.04234},
}

# The nominal corporate-action feed omitted this completed special dividend.
ADDITIONAL_ACTIONS = {
    '002001.SZ': [
        Action(
            '002001.SZ',
            '2025-01-22',
            cash_per_share=0.2,
            source='OFFICIAL_SPECIAL_DIVIDEND_2025-01-22',
        )
    ]
}


def refine_actions(symbol: str, actions: list[Action]) -> list[Action]:
    out: list[Action] = []
    seen_dates: set[str] = set()
    for action in actions:
        updates = REFINEMENTS.get((symbol, action.ex_date))
        if updates:
            action = replace(
                action,
                **updates,
                source=(action.source + '+OFFICIAL_VIRTUAL_DISTRIBUTION').strip('+'),
            )
        out.append(action)
        seen_dates.add(action.ex_date)

    for action in ADDITIONAL_ACTIONS.get(symbol, []):
        if action.ex_date not in seen_dates:
            out.append(action)

    out.sort(key=lambda x: x.ex_date)
    return out
