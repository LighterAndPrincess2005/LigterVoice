import unittest
from progress import job_progress


class ProgressTest(unittest.TestCase):
    def job(self,**extra):
        return {'created':10,'duration':100,'coverage':[],'state':'working','phase':'recognize','phase_since':20,'metrics':{},**extra}

    def test_overlapping_ranges_are_counted_once_and_gaps_stay_visible(self):
        p=job_progress(self.job(coverage=[[0,10],[5,20],[50,60],[-2,0],[90,120]]),now=30)
        self.assertEqual(p['processed_seconds'],40);self.assertEqual(p['percent'],40)
        self.assertEqual(p['phase_seconds'],10);self.assertIn('00:40 / 01:40',p['coverage_text'])

    def test_readiness_requires_audio_and_all_voice_not_just_state_ready(self):
        j=self.job(state='ready',coverage=[[0,100]])
        voice={'enabled':True,'total':4,'ready':2,'pending':2,'failed':0}
        p=job_progress(j,voice,now=30);self.assertEqual(p['percent'],100);self.assertFalse(p['ready']);self.assertEqual(p['phase'],'speech')
        voice.update(ready=4,pending=0);self.assertTrue(job_progress(j,voice,now=30)['ready'])
        j['coverage']=[[0,40],[60,100]];self.assertFalse(job_progress(j,voice,now=30)['ready'])

    def test_unknown_initial_progress_is_indeterminate_not_fake_percent(self):
        p=job_progress(self.job(duration=0),now=30);self.assertIsNone(p['percent']);self.assertTrue(p['indeterminate'])
        p=job_progress(self.job(),now=30);self.assertEqual(p['percent'],0);self.assertTrue(p['indeterminate'])

    def test_error_and_buffering_do_not_spin_as_if_working(self):
        p=job_progress(self.job(state='error',error='CDN không phản hồi'),now=30)
        self.assertEqual(p['phase'],'error');self.assertEqual(p['error'],'CDN không phản hồi');self.assertFalse(p['indeterminate'])
        p=job_progress(self.job(state='buffered',coverage=[[0,20]]),now=30);self.assertEqual(p['phase'],'waiting')

    def test_review_is_not_presented_as_verified_complete(self):
        p=job_progress(self.job(state='ready',coverage=[[0,100]],metrics={'uncertain_asr_windows':[[10,20]]}),now=30)
        self.assertTrue(p['ready']);self.assertFalse(p['done']);self.assertFalse(p['quality_ok']);self.assertEqual(p['phase'],'review')


if __name__=='__main__':unittest.main()
