import unittest

import special_exright_provenance_v482 as mod


class SpecialExrightProvenanceV482Tests(unittest.TestCase):
    def test_rank_prefers_restructuring_exright_announcement(self):
        items=[
            {'announcementTitle':'关于股票交易异常波动的公告','announcementTime':1766707200000,'announcementId':'x'},
            {'announcementTitle':'关于重整计划资本公积金转增股本实施暨股票除权的公告','announcementTime':1766707200000,'announcementId':'y'},
        ]
        ranked=mod.rank_candidates(items,'2025-12-29')
        self.assertEqual(ranked[0]['announcementId'],'y')

    def test_text_match_requires_adjusted_reference_price_and_exright_context(self):
        text='本次重整实施后，股票除权参考价格调整为6.87元/股。'
        self.assertTrue(mod.text_matches_reference(text,6.87))
        self.assertFalse(mod.text_matches_reference('公司股票收盘价为6.87元。',6.87))

    def test_materialized_row_requires_cninfo_pdf_sha(self):
        row=mod.make_provenance_row(
            {'symbol':'000430.SZ','ex_date':'2025-12-29','adjusted_reference_price':6.87},
            {'announcementId':'1212345678','announcementTitle':'重整除权公告','adjunctUrl':'finalpage/2025-12-27/1212345678.PDF'},
            'a'*64,
        )
        self.assertEqual(row['source'],'CNINFO_OFFICIAL_PDF')
        self.assertEqual(row['materialized_sha256'],'a'*64)
        self.assertEqual(row['announcement_id'],'1212345678')


if __name__=='__main__': unittest.main()
