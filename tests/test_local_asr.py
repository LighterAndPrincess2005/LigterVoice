import io
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock, patch
from local_asr import LocalRecognizer, has_recognition_loop


def wav(level=1000):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(int(level).to_bytes(2,'little',signed=True)*16000)
    return out.getvalue()


def segment(confidence=-.2):
    return SimpleNamespace(start=.1,end=.8,text='你好',avg_logprob=confidence,no_speech_prob=.1,compression_ratio=1,
        words=[SimpleNamespace(start=.1,end=.8,word='你好')])


class RecognitionQualityTest(unittest.TestCase):
    def recognizer(self,passes):
        recognizer=LocalRecognizer();recognizer.model=Mock()
        recognizer.model.transcribe.side_effect=[(iter(parts),SimpleNamespace(language='zh')) for parts in passes]
        return recognizer

    def test_background_warm_and_foreground_warm_load_model_once(self):
        import sys
        constructor=Mock(return_value=Mock())
        r=LocalRecognizer()
        with patch.dict(sys.modules,{'faster_whisper':SimpleNamespace(WhisperModel=constructor)}):
            r.start();r.warm();r.warm()
            self.assertEqual(constructor.call_count,1);self.assertEqual(r.state,'ready')
            self.assertTrue(constructor.call_args.kwargs['local_files_only'])

    def test_empty_vad_result_is_audited_without_vad(self):
        r=self.recognizer([[],[segment()]])
        result=r.recognize(wav(),'auto')
        self.assertEqual(result['words'][0]['word'],'你好');self.assertTrue(result['recovery_attempted'])
        self.assertFalse(result['uncertain_audio']);self.assertIsNone(r.model.transcribe.call_args_list[0].kwargs['language'])
        self.assertTrue(r.model.transcribe.call_args_list[0].kwargs['vad_filter']);self.assertFalse(r.model.transcribe.call_args_list[1].kwargs['vad_filter'])

    def test_low_confidence_recovery_is_flagged_instead_of_invented(self):
        r=self.recognizer([[],[segment(-1.5)]])
        result=r.recognize(wav(),'zh')
        self.assertEqual(result['words'],[]);self.assertTrue(result['uncertain_audio'])

    def test_recognition_loop_is_retried_and_never_emitted(self):
        loop=segment()
        loop.text='everything, '*74
        r=self.recognizer([[loop],[segment()]])
        result=r.recognize(wav(),'auto')
        self.assertEqual([word['word'] for word in result['words']],['你好'])
        self.assertTrue(result['recovery_attempted'])
        self.assertFalse(result['uncertain_audio'])

    def test_short_repeated_dialogue_is_preserved(self):
        self.assertFalse(has_recognition_loop('No, no, no! Wait.'))
        self.assertTrue(has_recognition_loop('谢谢，'*12))

    def test_silence_does_not_trigger_extra_recognition(self):
        r=self.recognizer([[]]);result=r.recognize(wav(0),'auto')
        self.assertEqual(result['words'],[]);self.assertEqual(r.model.transcribe.call_count,1)

    def test_primary_confidence_is_retained_for_downstream_review(self):
        r=self.recognizer([[segment()]])
        result=r.recognize(wav(),'auto')
        self.assertEqual(result['segments'][0]['avg_logprob'],-.2)


if __name__=='__main__':unittest.main()
