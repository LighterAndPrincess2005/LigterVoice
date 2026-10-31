"""Background companion; video, captions and narration stay in Chrome."""
from pathlib import Path
import sys,threading
from http.server import ThreadingHTTPServer
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon,QFont,QAction
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,QFormLayout,QPlainTextEdit,QSystemTrayIcon,QMenu,QMessageBox,QProgressBar
import app as backend


class Center(QMainWindow):
    def __init__(self,server):
        super().__init__();self.server=server;self.last_revision=None
        self.setWindowTitle('Ligter Voice');self.resize(570,650)
        screens=[s for s in QApplication.screens() if s!=QApplication.primaryScreen()]
        if screens:self.move(screens[0].availableGeometry().left()+35,screens[0].availableGeometry().top()+70)
        self.setStyleSheet('QWidget{background:#f5f7f7;color:#203638;font-family:"Segoe UI";font-size:14px}QPushButton{background:#126b62;color:white;border:0;border-radius:5px;padding:10px}QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #c5d3d3;border-radius:5px;padding:7px}')
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).parent));self.icon=QIcon(str(base/'extension/icons/32.png'));self.setWindowIcon(self.icon)
        root=QWidget();layout=QVBoxLayout(root);layout.setContentsMargins(22,20,22,18);layout.setSpacing(12);self.setCentralWidget(root)
        title=QLabel('Ligter Voice');title.setStyleSheet('font-size:27px;font-weight:700');layout.addWidget(title)
        intro=QLabel('Dịch và thuyết minh ngay trên Douyin web.\nMở tiện ích Chrome rồi bấm Dịch video.');intro.setWordWrap(True);layout.addWidget(intro)
        self.status=QLabel('Đang chuẩn bị giọng đọc tại máy…');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,1000);self.progress.setValue(0);self.progress.setFormat('Chưa có video đang xử lý');layout.addWidget(self.progress)
        self.progress.setStyleSheet('QProgressBar{border:1px solid #c5d3d3;border-radius:5px;text-align:center;min-height:20px;background:white}QProgressBar::chunk{background:#76bea7;border-radius:4px}')
        self.progress_detail=QLabel();self.progress_detail.setWordWrap(True);self.progress_detail.setStyleSheet('font-size:12px;color:#42615e');layout.addWidget(self.progress_detail)
        self.voice_state=QLabel();layout.addWidget(self.voice_state)
        form=QFormLayout();layout.addLayout(form)
        self.voice=QComboBox();self.voice.addItems(['Giọng nam','Giọng nữ','Tắt giọng đọc']);self.voice.setCurrentIndex(2 if not backend.settings.get('speak',True) else (1 if 'HoaiMy' in backend.settings['voice'] else 0));self.voice.currentIndexChanged.connect(self.change_voice);form.addRow('Thuyết minh',self.voice)
        self.language=QComboBox();self.language.addItems(['Tự nhận diện','Tiếng Trung','Tiếng Anh']);self.language.setCurrentIndex({'auto':0,'zh':1,'en':2}.get(backend.settings.get('language'),0));form.addRow('Tiếng video',self.language)
        self.key=QLineEdit(backend.settings.get('key',''));self.key.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('Khóa Groq API',self.key)
        save=QPushButton('Lưu cài đặt');save.clicked.connect(self.save);form.addRow('',save)
        pair=QPushButton('Sao chép mã kết nối Chrome');pair.clicked.connect(lambda:QApplication.clipboard().setText(backend.settings['token']));layout.addWidget(pair)
        self.transcript=QPlainTextEdit();self.transcript.setReadOnly(True);self.transcript.setPlaceholderText('Lời thoại từ video đang dịch trên Chrome…');layout.addWidget(self.transcript,1)
        hide=QPushButton('Thu xuống khay hệ thống');hide.clicked.connect(self.hide);layout.addWidget(hide)
        foot=QLabel('Bạn xem và lướt video trong Chrome. Đóng cửa sổ này vẫn tiếp tục chạy nền.');foot.setWordWrap(True);layout.addWidget(foot)
        self.tray=QSystemTrayIcon(self.icon,self);menu=QMenu()
        show=QAction('Mở Ligter Voice',self);show.triggered.connect(self.show_center);menu.addAction(show)
        quit_action=QAction('Thoát Ligter Voice',self);quit_action.triggered.connect(self.exit);menu.addAction(quit_action)
        self.tray.setContextMenu(menu);self.tray.setToolTip('Ligter Voice đang chạy nền');self.tray.activated.connect(lambda r:self.show_center() if r==QSystemTrayIcon.ActivationReason.DoubleClick else None);self.tray.show()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(500);backend.engine.local_speech.start()

    def save(self):
        backend.settings.update(key=self.key.text().strip(),provider='groq',language=['auto','zh','en'][self.language.currentIndex()],preload_all=False)
        backend.save_settings();self.status.setText('Đã lưu. Tiếp tục dùng tiện ích trên Chrome.')

    def change_voice(self,index):
        backend.settings.update(speak=index!=2,voice='vi-VN-HoaiMyNeural' if index==1 else 'vi-VN-NamMinhNeural');backend.save_settings()

    def tick(self):
        if backend.show_requested.is_set():
            backend.show_requested.clear();self.show_center()
        state=backend.engine.local_speech.state
        self.voice_state.setText('Giọng nam / nữ tại máy: '+{'cold':'chưa khởi động','loading':'đang chuẩn bị…','ready':'sẵn sàng','error':'chưa sẵn sàng'}.get(state,state))
        jobs=[j for j in backend.engine.jobs.values() if not j.get('prefetch') and not j['cancel'].is_set()]
        if not jobs:
            self.progress.setRange(0,1000);self.progress.setValue(0);self.progress.setFormat('Chưa chọn video');self.progress_detail.setText('Chọn video trên Douyin rồi bấm Dịch video này trong tiện ích.')
            if state=='ready':self.status.setText('Sẵn sàng. Bấm Dịch video trong tiện ích Chrome.')
            return
        snapshot=backend.engine.snapshot(jobs[-1]['id']);identity=(snapshot['id'],snapshot['revision']);self.status.setText(snapshot['message'])
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
        desired=2 if not backend.settings.get('speak',True) else (1 if 'HoaiMy' in backend.settings['voice'] else 0)
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
