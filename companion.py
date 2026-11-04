"""Background companion; video, captions and narration stay in Chrome."""
from pathlib import Path
import sys,threading,winsound
from http.server import ThreadingHTTPServer
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QIcon,QFont,QAction
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,QFormLayout,QPlainTextEdit,QSystemTrayIcon,QMenu,QMessageBox,QProgressBar
import app as backend
from local_speech import FEMALE_PRESETS


class Center(QMainWindow):
    def __init__(self,server):
        super().__init__();self.server=server;self.last_revision=None
        self.setWindowTitle('Ligter Voice');self.resize(800,560);self.setMinimumSize(690,500)
        screens=[s for s in QApplication.screens() if s!=QApplication.primaryScreen()]
        if screens:self.move(screens[0].availableGeometry().left()+35,screens[0].availableGeometry().top()+70)
        self.setStyleSheet("""
            QMainWindow, QWidget#workspace { background: #0c121c; }
            QWidget { color: #e7eff8; font-family: "Segoe UI"; font-size: 14px; }
            QWidget#card { background: #141e2b; border: 1px solid #2a3b50; border-radius: 12px; }
            QLabel#eyebrow { color: #8ce5d3; font-size: 11px; font-weight: 700; }
            QLabel#appTitle { font-size: 28px; font-weight: 700; }
            QLabel#cardTitle { font-size: 17px; font-weight: 650; }
            QLabel#muted { color: #aab9cb; font-size: 12px; }
            QLabel#status { font-size: 15px; font-weight: 650; }
            QPushButton { background: #223249; border: 1px solid #364a64;
                border-radius: 7px; padding: 8px 12px; text-align: left; }
            QPushButton:hover { background: #2b405b; }
            QPushButton:disabled { background: #182435; color: #8c9db3; }
            QPushButton#preview { background: #89e5d0; color: #0d2824;
                border-color: #89e5d0; font-weight: 650; }
            QPushButton#preview:hover { background: #b3f3e5; }
            QPushButton#preview:disabled { background: #273949; border-color: #364a64; color: #aab9cb; }
            QPushButton#quiet { background: transparent; border: none; color: #aab9cb; }
            QPushButton#quiet:hover { color: #e7eff8; background: #223249; }
            QLineEdit, QComboBox, QPlainTextEdit { background: #0e1723;
                border: 1px solid #34465d; border-radius: 7px; padding: 8px; }
            QComboBox QAbstractItemView { background: #162233; selection-background-color: #2d4864; }
            QProgressBar { background: #0e1723; border: 1px solid #34465d;
                border-radius: 6px; min-height: 20px; text-align: center; color: #effaf9; }
            QProgressBar::chunk { background: #20695f; border-radius: 5px; }
            QMenu { background: #141e2b; border: 1px solid #34465d; }
            QMenu::item:selected { background: #2b405b; }
        """)
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
        self.icon=QIcon(str(base/'extension/icons/32.png'))
        self.setWindowIcon(self.icon)

        root=QWidget()
        root.setObjectName('workspace')
        self.setCentralWidget(root)
        layout=QVBoxLayout(root)
        layout.setContentsMargins(22,18,22,15)
        layout.setSpacing(12)
        header=QHBoxLayout()
        heading=QVBoxLayout()
        heading.setSpacing(1)
        label=QLabel('DOUYIN  /  THUYẾT MINH TIẾNG VIỆT')
        label.setObjectName('eyebrow')
        title=QLabel('Ligter Voice')
        title.setObjectName('appTitle')
        heading.addWidget(label)
        heading.addWidget(title)
        header.addLayout(heading,1)
        self.voice_state=QLabel()
        self.voice_state.setObjectName('muted')
        header.addWidget(self.voice_state,alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)

        columns=QHBoxLayout()
        columns.setSpacing(12)
        controls=QWidget()
        controls.setObjectName('card')
        left=QVBoxLayout(controls)
        left.setContentsMargins(14,13,14,13)
        left.setSpacing(8)
        self.video_title=QLabel('Chưa chọn video')
        self.video_title.setObjectName('cardTitle')
        self.video_title.setTextFormat(Qt.TextFormat.PlainText)
        self.video_title.setWordWrap(True)
        left.addWidget(self.video_title)
        self.status=QLabel('Đang chuẩn bị giọng đọc tại máy…')
        self.status.setObjectName('status')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.progress=QProgressBar()
        self.progress.setRange(0,1000)
        self.progress.setValue(0)
        self.progress.setFormat('Chưa có video đang xử lý')
        left.addWidget(self.progress)
        self.progress_detail=QLabel()
        self.progress_detail.setObjectName('muted')
        self.progress_detail.setWordWrap(True)
        left.addWidget(self.progress_detail)
        left.addSpacing(4)

        voice_title=QLabel('Giọng thuyết minh')
        voice_title.setObjectName('cardTitle')
        left.addWidget(voice_title)
        self.voice=QComboBox()
        self.voice.addItems(['Giọng nam Quang Minh','Giọng nữ Bảo Trang','Tắt giọng đọc','Giọng nữ Hà My','Giọng nữ Kim Oanh','Giọng nữ Mai Chi'])
        self.voice.setCurrentIndex(self.voice_index())
        self.voice.currentIndexChanged.connect(self.change_voice)
        left.addWidget(self.voice)
        self.preview_button=QPushButton('▶  Nghe thử giọng nữ')
        self.preview_button.setObjectName('preview')
        self.preview_button.clicked.connect(self.preview_voice)
        left.addWidget(self.preview_button)
        self.preview_status=QLabel()
        self.preview_status.setObjectName('muted')
        self.preview_status.setWordWrap(True)
        left.addWidget(self.preview_status)

        settings_button=QPushButton('Cài đặt kết nối')
        settings_button.setCheckable(True)
        settings=QWidget()
        settings_layout=QVBoxLayout(settings)
        settings_layout.setContentsMargins(0,0,0,0)
        settings_layout.setSpacing(7)
        form=QFormLayout()
        self.language=QComboBox()
        self.language.addItems(['Tự nhận diện','Tiếng Trung','Tiếng Anh'])
        self.language.setCurrentIndex({'auto':0,'zh':1,'en':2}.get(backend.settings.get('language'),0))
        form.addRow('Tiếng video',self.language)
        self.key=QLineEdit(backend.settings.get('key',''))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Khóa Groq API',self.key)
        settings_layout.addLayout(form)
        save=QPushButton('Lưu cài đặt')
        save.clicked.connect(self.save)
        settings_layout.addWidget(save)
        pair=QPushButton('Sao chép mã kết nối Chrome')
        pair.clicked.connect(lambda:QApplication.clipboard().setText(backend.settings['token']))
        settings_layout.addWidget(pair)
        settings.setVisible(False)
        settings_button.toggled.connect(settings.setVisible)
        left.addWidget(settings_button)
        left.addWidget(settings)
        left.addStretch()
        columns.addWidget(controls,5)

        script_panel=QWidget()
        script_panel.setObjectName('card')
        right=QVBoxLayout(script_panel)
        right.setContentsMargins(14,13,14,13)
        right.setSpacing(8)
        transcript_title=QLabel('Lời thoại & bản dịch')
        transcript_title.setObjectName('cardTitle')
        right.addWidget(transcript_title)
        self.transcript=QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText('Lời thoại từ video đang dịch trên Chrome…')
        right.addWidget(self.transcript,1)
        columns.addWidget(script_panel,7)
        layout.addLayout(columns,1)

        footer=QHBoxLayout()
        foot=QLabel('Mở video trên Douyin và bấm Dịch video này trong tiện ích Chrome.')
        foot.setObjectName('muted')
        foot.setWordWrap(True)
        footer.addWidget(foot,1)
        hide=QPushButton('Thu xuống khay')
        hide.setObjectName('quiet')
        hide.clicked.connect(self.hide)
        footer.addWidget(hide)
        layout.addLayout(footer)
        self.tray=QSystemTrayIcon(self.icon,self);menu=QMenu()
        show=QAction('Mở Ligter Voice',self);show.triggered.connect(self.show_center);menu.addAction(show)
        quit_action=QAction('Thoát Ligter Voice',self);quit_action.triggered.connect(self.exit);menu.addAction(quit_action)
        self.tray.setContextMenu(menu);self.tray.setToolTip('Ligter Voice đang chạy nền');self.tray.activated.connect(lambda r:self.show_center() if r==QSystemTrayIcon.ActivationReason.DoubleClick else None);self.tray.show()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(500);backend.engine.local_speech.start()
        if backend.settings.get('asr')=='local':backend.engine.local_asr.start()

    def save(self):
        backend.settings.update(key=self.key.text().strip(),provider='groq',language=['auto','zh','en'][self.language.currentIndex()],preload_all=False)
        backend.save_settings();self.status.setText('Đã lưu. Tiếp tục dùng tiện ích trên Chrome.')

    def voice_index(self):
        if not backend.settings.get('speak',True):
            return 2
        if 'HoaiMy' in backend.settings['voice']:
            return {'hamy':3,'kimoanh':4,'maichi':5}.get(backend.settings.get('female_preset'),1)
        return 0

    def change_voice(self,index):
        if index==2:
            backend.settings['speak']=False
        else:
            female=index!=0
            backend.settings.update(speak=True,voice='vi-VN-HoaiMyNeural' if female else 'vi-VN-NamMinhNeural',tts='local')
            if female:
                backend.settings['female_preset']=FEMALE_PRESETS[0 if index==1 else index-2]
        backend.save_settings()

    def preview_voice(self):
        index=self.voice.currentIndex()
        if index not in (1,3,4,5):
            return
        preset=FEMALE_PRESETS[0 if index==1 else index-2]
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
        path=base/'voice-previews'/(preset+'.wav')
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            self.preview_status.setText('Xin chào buổi sáng, Bảo Long.')
        except (OSError,RuntimeError):
            self.preview_status.setText('Chưa phát được mẫu giọng.')

    def tick(self):
        self.preview_button.setEnabled(self.voice.currentIndex() in (1,3,4,5))

        if backend.show_requested.is_set():
            backend.show_requested.clear();self.show_center()
        state=backend.engine.local_speech.state
        self.voice_state.setText('Giọng nam / nữ tại máy: '+{'cold':'chưa khởi động','loading':'đang chuẩn bị…','ready':'sẵn sàng','error':'chưa sẵn sàng'}.get(state,state))
        jobs=[j for j in backend.engine.jobs.values() if not j.get('prefetch') and not j['cancel'].is_set()]
        if not jobs:
            self.video_title.setText('Chưa chọn video')
            self.video_title.setToolTip('')
            if self.last_revision is not None:
                self.last_revision=None
                self.transcript.clear()
            self.progress.setRange(0,1000);self.progress.setValue(0);self.progress.setFormat('Chưa chọn video');self.progress_detail.setText('Chọn video trên Douyin rồi bấm Dịch video này trong tiện ích.')
            if state=='ready':self.status.setText('Sẵn sàng. Bấm Dịch video trong tiện ích Chrome.')
            return
        snapshot=backend.engine.snapshot(jobs[-1]['id']);identity=(snapshot['id'],snapshot['revision']);self.status.setText(snapshot['message'])
        title=str(snapshot.get('title') or 'Video đang dịch')
        self.video_title.setText(title if len(title)<=85 else title[:82]+'…')
        self.video_title.setToolTip(title.replace('<','＜').replace('>','＞'))
        p=snapshot['progress'];voice=p['speech'];self.status.setText(p['error'] or p['label'])
        self.progress.setRange(0,0 if p['indeterminate'] else 1000)
        if not p['indeterminate']:self.progress.setValue(round((p['percent'] or 0)*10))
        self.progress.setFormat(p['coverage_text'])
        details=[p['coverage_text']]
        if p['interval_text'] and not p['done']:details.append('Đoạn '+p['interval_text'])
        if voice['enabled']:details.append(f"Giọng: {voice['ready']}/{voice['total']} câu"+(f" · {voice['failed']} lỗi" if voice['failed'] else ''))
        if not p['done'] and p['phase'] not in ('error','cancelled','waiting'):details.append(f"Bước hiện tại: {p['phase_seconds']} giây")
        self.progress_detail.setText(' · '.join(details))
        if identity!=self.last_revision:
            self.last_revision=identity;self.transcript.setPlainText('\n\n'.join(f"{int(x['start']//60):02}:{int(x['start']%60):02}  {x['source']}\n{x['translation']}" for x in snapshot['lines']))
        desired=self.voice_index()
        if desired!=self.voice.currentIndex():
            self.voice.blockSignals(True);self.voice.setCurrentIndex(desired);self.voice.blockSignals(False)

    def show_center(self):self.showNormal();self.raise_();self.activateWindow()

    def closeEvent(self,event):event.ignore();self.hide()

    def exit(self):
        self.tray.hide();backend.engine.close();self.server.shutdown();QApplication.quit()


def main():
    application=QApplication(sys.argv);application.setQuitOnLastWindowClosed(False);application.setFont(QFont('Segoe UI',10))
    try:server=ThreadingHTTPServer(('127.0.0.1',backend.PORT),backend.Handler)
    except OSError:
        if '--background' not in sys.argv:
            try:
                backend.requests.post(f'http://127.0.0.1:{backend.PORT}/companion/show',json={},headers={'Authorization':'Bearer '+backend.settings['token']},timeout=3).raise_for_status()
            except Exception:
                QMessageBox.information(None,'Ligter Voice','Ligter Voice đã chạy nền. Mở từ biểu tượng LV ở khay hệ thống.')
        return
    threading.Thread(target=server.serve_forever,daemon=True).start();center=Center(server)
    if '--background' not in sys.argv:center.show()
    application.exec()


if __name__=='__main__':main()
