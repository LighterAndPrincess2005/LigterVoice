import unittest

from douyin_captions import clean_cues, covered_cues, parse_caption


class DouyinCaptionTests(unittest.TestCase):
    def test_vtt_and_srt_timestamps(self):
        for prefix, timestamp in [('WEBVTT\n\n', '00:00:00.640'), ('1\n', '00:00:00,640')]:
            rows = parse_caption(prefix + timestamp + ' --> 00:00:02.120\n<c>你好</c>')
            self.assertEqual(rows, [[.64, 2.12, '你好']])

    def test_json_explicit_milliseconds(self):
        self.assertEqual(parse_caption('{"utterances":[{"start_time":640,"end_time":2120,"text":"你好"}]}'),
                         [[.64, 2.12, '你好']])

    def test_a_gap_does_not_count_as_translated(self):
        rows = clean_cues([[0, 2, '你好'], [6, 8, '谢谢'], [11, 60, 'wrong video']], 8)
        self.assertEqual(covered_cues(rows, 0, 8), [])
        self.assertEqual(covered_cues(rows, 6, 8), [{'word':'谢谢','start':6,'end':8}])
