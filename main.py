import sys
import traceback

try:
    import cv2
    import random
    import numpy as np
    from datetime import datetime
    from PyQt6 import QtWidgets, QtGui, QtCore
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
except ImportError as e:
    print("\n" + "=" * 50)
    print(f"🚨 KÜTÜPHANE EKSİK: {e}")
    print("=" * 50)
    print("Lütfen terminali açıp şu komutu çalıştırın:")
    print("pip install PyQt6 opencv-python numpy\n")
    input("Pencereyi kapatmak için Enter'a basın...")
    sys.exit()


# --- 1. GELENEKSEL (NORMAL) PUSULA ---
class DigitalCompassHUD(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.setMinimumSize(180, 180)

    def set_angle(self, angle):
        self.angle = angle
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)

        radius = 60

        # Arka plan ve dış çerçeve
        painter.setPen(QtGui.QPen(QtGui.QColor("#1e293b"), 3))
        painter.setBrush(QtGui.QColor("#0f172a"))
        painter.drawEllipse(-radius, -radius, radius * 2, radius * 2)

        # Yön Harfleri (N, E, S, W)
        painter.setPen(QtGui.QColor("#38bdf8"))
        painter.setFont(QtGui.QFont("Consolas", 12, QtGui.QFont.Weight.Bold))
        painter.drawText(QtCore.QRectF(-15, -radius - 28, 30, 20), Qt.AlignmentFlag.AlignCenter, "N")
        painter.drawText(QtCore.QRectF(-15, radius + 8, 30, 20), Qt.AlignmentFlag.AlignCenter, "S")
        painter.drawText(QtCore.QRectF(radius + 8, -10, 20, 20), Qt.AlignmentFlag.AlignCenter, "E")
        painter.drawText(QtCore.QRectF(-radius - 28, -10, 20, 20), Qt.AlignmentFlag.AlignCenter, "W")

        # Derece Çizgileri (Tick marks)
        painter.setPen(QtGui.QPen(QtGui.QColor("#64748b"), 1))
        for i in range(0, 360, 15):
            painter.save()
            painter.rotate(i)
            if i % 90 == 0:
                painter.setPen(QtGui.QPen(QtGui.QColor("#38bdf8"), 2))
                painter.drawLine(0, -radius, 0, -radius + 8)
            else:
                painter.drawLine(0, -radius, 0, -radius + 4)
            painter.restore()

        # İbre (Pusula İğnesi)
        painter.rotate(self.angle)

        # Kuzey İğnesi (Kırmızı)
        poly_n = QtGui.QPolygon([QtCore.QPoint(0, -radius + 10), QtCore.QPoint(6, 0), QtCore.QPoint(-6, 0)])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#ef4444"))
        painter.drawPolygon(poly_n)

        # Güney İğnesi (Gümüş/Beyaz)
        poly_s = QtGui.QPolygon([QtCore.QPoint(0, radius - 10), QtCore.QPoint(6, 0), QtCore.QPoint(-6, 0)])
        painter.setBrush(QtGui.QColor("#f8fafc"))
        painter.drawPolygon(poly_s)

        # Merkez Noktası
        painter.setBrush(QtGui.QColor("#38bdf8"))
        painter.drawEllipse(-4, -4, 8, 8)


# --- 2. VİDEO HUD ---
class HUDVideoLabel(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.setPen(QtGui.QPen(QtGui.QColor(56, 189, 248, 120), 2))
        cx, cy = w // 2, h // 2
        painter.drawLine(cx - 30, cy, cx + 30, cy)
        painter.drawLine(cx, cy - 30, cx, cy + 30)
        painter.drawEllipse(cx - 15, cy - 15, 30, 30)


# --- 3. HAFİFLETİLMİŞ KAMERA KONTROLÜ (AI ÇIKARILDI) ---
class DualStreamThread(QThread):
    video_signal = pyqtSignal(QtGui.QImage, str)

    def run(self):
        cap = cv2.VideoCapture(0)
        while True:
            ret, frame = cap.read()
            if ret:
                # Saf Görüntü (Sistemi yormaz)
                rgb_main = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_main.shape
                qt_img_main = QtGui.QImage(rgb_main.data, w, h, ch * w, QtGui.QImage.Format.Format_RGB888)
                self.video_signal.emit(qt_img_main, "CAM_1")

                # İkincil Kamera Filtresi (Mini ROV Simülasyonu)
                mini_frame = cv2.applyColorMap(frame, cv2.COLORMAP_OCEAN)
                rgb_mini = cv2.cvtColor(mini_frame, cv2.COLOR_BGR2RGB)
                qt_img_mini = QtGui.QImage(rgb_mini.data, w, h, ch * w, QtGui.QImage.Format.Format_RGB888)
                self.video_signal.emit(qt_img_mini, "CAM_2")
            else:
                blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank_frame, "KAMERA BAGLANTISI YOK", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 0, 255), 2)
                rgb_blank = cv2.cvtColor(blank_frame, cv2.COLOR_BGR2RGB)
                qt_blank = QtGui.QImage(rgb_blank.data, 640, 480, 3 * 640, QtGui.QImage.Format.Format_RGB888)
                self.video_signal.emit(qt_blank, "CAM_1")
                self.video_signal.emit(qt_blank, "CAM_2")

            QtCore.QThread.msleep(30)


# --- 4. ANA YER İSTASYONU ---
class ROVGroundStation(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YAVUZ ROV - MISSION COMMANDER 2026")
        self.setMinimumSize(1450, 900)

        self.setDockNestingEnabled(True)
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QtWidgets.QTabWidget.TabPosition.South)

        self.mission_time = 300
        self.is_emergency = False
        self.is_recording = False
        self.active_main = "CAM_1"
        self.heading = 45

        self.mission_index = 0
        self.missions = [
            "SIZDIRMAZLIK TESTİ",
            "TEMA 1: YÖNLENDİRME HATTI",
            "TEMA 1: MINI ROV BORU",
            "TEMA 2: OTONOM İNTİKAL",
            "TEMA 2: BİTİŞ ALANI"
        ]

        self.mission_details = [
            "AÇIKLAMA: Aracın havuza indirilmesi ve 1 dakika boyunca su alıp almadığının, motorların stabil çalışıp çalışmadığının kontrol edilmesi.",
            "AÇIKLAMA: Havuz tabanındaki renkli yönlendirme hattının tespit edilmesi ve hattın sonuna kadar stabil şekilde takip edilmesi.",
            "AÇIKLAMA: Ana ROV'dan ayrılan Mini ROV'un, su altındaki boru simülasyonu içerisine girerek hasar tespiti yapması.",
            "AÇIKLAMA: Aracın hedef çemberlerden veya kapılardan insan müdahalesi olmadan (otonom) olarak geçiş yapması.",
            "AÇIKLAMA: Tüm görevlerin tamamlanmasının ardından aracın belirlenen bitiş/park alanına giderek su yüzeyine güvenle çıkması."
        ]

        self.init_ui()

        self.thread = DualStreamThread()
        self.thread.video_signal.connect(self.update_video)
        self.thread.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.system_tick)
        self.timer.start(100)

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #020617; }
            QMainWindow::separator { background: #1e293b; width: 4px; height: 4px; }
            QMainWindow::separator:hover { background: #ef4444; }

            QFrame#Panel { background-color: #0f172a; border: 1px solid #1e293b; border-radius: 8px; }
            QFrame#HeaderPanel { background-color: #0f172a; border-bottom: 2px solid #ef4444; border-radius: 0px; }

            QLabel { color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
            QLabel#Value { font-size: 24px; font-weight: bold; font-family: 'Consolas'; color: #ffffff; }
            QLabel#Tag { font-size: 11px; font-weight: bold; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px;}

            QProgressBar { background-color: #020617; border: none; height: 8px; border-radius: 4px; text-align: center; color: transparent; }
            QProgressBar::chunk { background-color: #38bdf8; border-radius: 4px; }

            QPushButton#Action { background-color: #1e293b; color: #38bdf8; font-weight: bold; border-radius: 4px; padding: 6px; border: 1px solid #38bdf8; }
            QPushButton#Action:hover { background-color: #38bdf8; color: #020617; }

            QPushButton#Rec { background-color: #020617; border: 1px solid #ef4444; color: #ef4444; border-radius: 4px; font-weight: bold; padding: 8px; }
            QPushButton#Stop { background-color: #be123c; color: white; font-weight: bold; border-radius: 6px; font-size: 13px; }
            QPushButton#Resume { background-color: #10b981; color: white; font-weight: bold; border-radius: 6px; font-size: 13px; }

            QTextEdit#Log { background-color: #000000; color: #38bdf8; border: 1px solid #1e293b; font-family: 'Consolas'; font-size: 11px; border-radius: 4px; }
            QDockWidget { color: #38bdf8; font-weight: bold; font-size: 11px; text-transform: uppercase; }
            QDockWidget::title { background: #0f172a; padding: 8px; text-align: center; border: 1px solid #1e293b; border-radius: 4px;}
        """)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(10, 0, 10, 10)
        main_layout.setSpacing(10)

        # ==========================================
        # 1. KURUMSAL BAŞLIK
        # ==========================================
        header_panel = QtWidgets.QFrame(objectName="HeaderPanel")
        header_panel.setFixedHeight(90)
        h_layout = QtWidgets.QHBoxLayout(header_panel)
        h_layout.setContentsMargins(15, 5, 15, 5)

        self.lbl_yavuz_logo = QtWidgets.QLabel()
        self.lbl_yavuz_logo.setFixedSize(70, 70)
        self.lbl_yavuz_logo.setStyleSheet("background: transparent;")
        self.lbl_yavuz_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        yavuz_pix = QtGui.QPixmap("yavuz_logo.png")
        if not yavuz_pix.isNull():
            self.lbl_yavuz_logo.setPixmap(yavuz_pix.scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation))

        title_box = QtWidgets.QVBoxLayout()
        lbl_team = QtWidgets.QLabel("YAVUZ YAZILIM SİSTEMLERİ")
        lbl_team.setStyleSheet("color: #ef4444; font-size: 24px; font-weight: bold; letter-spacing: 3px;")

        lbl_uni = QtWidgets.QLabel("SÜLEYMAN DEMİREL ÜNİVERSİTESİ (SDÜ)")
        lbl_uni.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold; letter-spacing: 1px;")

        title_box.addWidget(lbl_team)
        title_box.addWidget(lbl_uni)

        right_header = QtWidgets.QHBoxLayout()
        self.lbl_control = QtWidgets.QLabel("🎮 MANUAL")
        self.lbl_control.setStyleSheet("font-weight: bold; color: #facc15; font-size: 16px;")
        self.lbl_clock = QtWidgets.QLabel("05:00")
        self.lbl_clock.setStyleSheet("font-size: 32px; font-weight: bold; color: #ffffff;")
        self.btn_rec = QtWidgets.QPushButton("⚫ STANDBY", objectName="Rec")
        self.btn_rec.setFixedSize(110, 40)
        self.btn_rec.clicked.connect(self.toggle_record)

        right_header.addWidget(self.lbl_control)
        right_header.addSpacing(30)
        right_header.addWidget(self.lbl_clock)
        right_header.addSpacing(30)
        right_header.addWidget(self.btn_rec)

        h_layout.addWidget(self.lbl_yavuz_logo)
        h_layout.addSpacing(20)
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        h_layout.addLayout(right_header)

        main_layout.addWidget(header_panel)

        # ==========================================
        # 2. ORTA BÖLÜM
        # ==========================================
        mid_layout = QtWidgets.QHBoxLayout()

        # --- GÖREV PANELİ VE AÇIKLAMALAR ---
        mission_panel = QtWidgets.QFrame(objectName="Panel")
        mission_panel.setFixedWidth(280)
        mission_lay = QtWidgets.QVBoxLayout(mission_panel)
        mission_lay.addWidget(QtWidgets.QLabel("📋 GÖREV TAKİP SİSTEMİ", objectName="Tag"))
        self.lbl_mission_status = QtWidgets.QLabel("AWAITING DEPLOYMENT...")
        self.lbl_mission_status.setStyleSheet(
            "color: #facc15; font-weight: bold; font-size: 14px; border-bottom: 1px solid #1e293b; padding-bottom: 5px;")
        mission_lay.addWidget(self.lbl_mission_status)

        self.mission_labels = []
        for i, m_name in enumerate(self.missions):
            lbl = QtWidgets.QLabel(f"○ {m_name}")
            lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 5px;")
            self.mission_labels.append(lbl)
            mission_lay.addWidget(lbl)

        mission_lay.addSpacing(10)

        mission_lay.addWidget(QtWidgets.QLabel("🔍 GÖREV DETAYI:", objectName="Tag"))
        self.lbl_mission_desc = QtWidgets.QLabel(self.mission_details[0])
        self.lbl_mission_desc.setWordWrap(True)
        self.lbl_mission_desc.setStyleSheet(
            "color: #38bdf8; font-size: 17px; font-style: italic; background: #020617; padding: 10px; border-radius: 4px; border: 1px solid #1e293b;")
        self.lbl_mission_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        mission_lay.addWidget(self.lbl_mission_desc, stretch=1)

        mid_layout.addWidget(mission_panel)

        # --- KAMERA PANELİ ---
        cam_panel = QtWidgets.QVBoxLayout()
        self.lbl_main_title = QtWidgets.QLabel("PRIMARY OPTICAL FEED [MAIN ROV]")
        self.lbl_main_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px; letter-spacing: 1px;")
        self.lbl_main_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_panel.addWidget(self.lbl_main_title)

        self.main_cam = HUDVideoLabel()
        self.main_cam.setObjectName("Panel")
        self.main_cam.setFixedSize(720, 480)
        self.main_cam.setStyleSheet("background: #000; border: 2px solid #1e293b;")
        cam_panel.addWidget(self.main_cam, alignment=Qt.AlignmentFlag.AlignCenter)
        mid_layout.addLayout(cam_panel, stretch=1)

        # --- SAĞ PANEL (Pusula ve Butonlar) ---
        right_panel = QtWidgets.QFrame(objectName="Panel")
        right_panel.setFixedWidth(280)
        r_lay = QtWidgets.QVBoxLayout(right_panel)

        r_lay.addWidget(QtWidgets.QLabel("🧭 NAVİGASYON PUSULASI", objectName="Tag"),
                        alignment=Qt.AlignmentFlag.AlignCenter)
        self.compass = DigitalCompassHUD()
        r_lay.addWidget(self.compass, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_head = QtWidgets.QLabel("045.0° NE")
        self.lbl_head.setStyleSheet("font-size: 19px; font-weight: bold; color: #38bdf8;")
        r_lay.addWidget(self.lbl_head, alignment=Qt.AlignmentFlag.AlignCenter)

        r_lay.addSpacing(20)
        r_lay.addWidget(QtWidgets.QLabel("🎮 KONTROL PANELİ", objectName="Tag"))

        self.btn_swap = QtWidgets.QPushButton("🔄 KAMERA GEÇİŞİ", objectName="Action")
        self.btn_swap.setFixedHeight(40)
        self.btn_swap.clicked.connect(self.swap_feeds)
        r_lay.addWidget(self.btn_swap)

        self.btn_next = QtWidgets.QPushButton("⏭ GÖREVİ TAMAMLA", objectName="Action")
        self.btn_next.setFixedHeight(40)
        self.btn_next.clicked.connect(self.advance_mission)
        r_lay.addWidget(self.btn_next)

        r_lay.addStretch()
        mid_layout.addWidget(right_panel)

        main_layout.addLayout(mid_layout)

        # ==========================================
        # 3. ALT BÖLÜM (Telemetri)
        # ==========================================
        bottom_panel = QtWidgets.QFrame(objectName="Panel")
        bottom_panel.setFixedHeight(120)
        bot_lay = QtWidgets.QHBoxLayout(bottom_panel)
        bot_lay.setContentsMargins(30, 0, 30, 0)

        thruster_lay = QtWidgets.QVBoxLayout()
        thruster_lay.addWidget(QtWidgets.QLabel("Thruster Power Distribution", objectName="Tag"))
        bar_layout = QtWidgets.QHBoxLayout()
        self.bars = []
        for i in range(1, 5):
            box = QtWidgets.QHBoxLayout()
            box.addWidget(QtWidgets.QLabel(f"T{i}",
                                           styleSheet="color: #94a3b8; font-family: Consolas; font-size: 11px; font-weight: bold; width: 15px;"))
            bar = QtWidgets.QProgressBar()
            bar.setMaximum(100)
            bar.setValue(0)
            self.bars.append(bar)
            box.addWidget(bar)
            bar_layout.addLayout(box)
            if i < 4: bar_layout.addSpacing(15)
        thruster_lay.addLayout(bar_layout)
        bot_lay.addLayout(thruster_lay, stretch=1)

        bot_lay.addSpacing(60)

        tele_lay = QtWidgets.QHBoxLayout()

        col1 = QtWidgets.QVBoxLayout()
        col1.addWidget(QtWidgets.QLabel("🔋 SİSTEM GERİLİMİ", objectName="Tag"))
        self.lbl_volt = QtWidgets.QLabel("14.8V", objectName="Value")
        col1.addWidget(self.lbl_volt)
        col1.addWidget(QtWidgets.QLabel("🚢 DERİNLİK", objectName="Tag"))
        self.lbl_depth = QtWidgets.QLabel("04.2m", objectName="Value")
        col1.addWidget(self.lbl_depth)
        tele_lay.addLayout(col1)

        tele_lay.addSpacing(40)

        col2 = QtWidgets.QVBoxLayout()
        col2.addWidget(QtWidgets.QLabel("🌡️ DIŞ SICAKLIK", objectName="Tag"))
        self.lbl_temp = QtWidgets.QLabel("18.5°C", objectName="Value")
        col2.addWidget(self.lbl_temp)
        col2.addWidget(QtWidgets.QLabel("💧 SIZDIRMAZLIK", objectName="Tag"))
        self.lbl_leak = QtWidgets.QLabel("GÜVENLİ", objectName="Value")
        self.lbl_leak.setStyleSheet("color: #4ade80; font-size: 22px; font-weight: bold;")
        col2.addWidget(self.lbl_leak)
        tele_lay.addLayout(col2)

        bot_lay.addLayout(tele_lay, stretch=1)
        bot_lay.addStretch()

        main_layout.addWidget(bottom_panel)

        # ==========================================
        # 4. DOCK WIDGETS (Paneller)
        # ==========================================

        # Terminal Dock
        self.dock_log = QtWidgets.QDockWidget("MISSION TERMINAL & CONTROL", self)
        self.dock_log.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        log_container = QtWidgets.QFrame(objectName="Panel")
        log_lay = QtWidgets.QVBoxLayout(log_container)
        btn_lay = QtWidgets.QHBoxLayout()
        self.btn_stop = QtWidgets.QPushButton("🛑 ACİL STOP", objectName="Stop")
        self.btn_stop.setFixedHeight(35)
        self.btn_stop.clicked.connect(self.trigger_emergency)
        self.btn_resume = QtWidgets.QPushButton("▶ SİSTEMİ BAŞLAT", objectName="Resume")
        self.btn_resume.setFixedHeight(35)
        self.btn_resume.setEnabled(False)
        self.btn_resume.clicked.connect(self.resume_system)
        btn_lay.addWidget(self.btn_stop)
        btn_lay.addWidget(self.btn_resume)
        log_lay.addLayout(btn_lay)
        self.log_area = QtWidgets.QTextEdit()
        self.log_area.setObjectName("Log")
        self.log_area.setReadOnly(True)
        log_lay.addWidget(self.log_area)
        self.dock_log.setWidget(log_container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_log)

        # Mini Kamera Dock
        self.dock_mini = QtWidgets.QDockWidget("SECONDARY FEED [MINI ROV]", self)
        self.dock_mini.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        mini_container = QtWidgets.QFrame(objectName="Panel")
        mini_lay = QtWidgets.QVBoxLayout(mini_container)
        self.mini_cam = QtWidgets.QLabel("NO SIGNAL")
        self.mini_cam.setMinimumHeight(180)
        self.mini_cam.setStyleSheet("background: #000; border-radius: 4px;")
        self.mini_cam.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mini_lay.addWidget(self.mini_cam)
        self.dock_mini.setWidget(mini_container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_mini)

        self.update_mission_ui()

    # --- FONKSİYONLAR ---
    def advance_mission(self):
        if self.mission_index < len(self.missions):
            self.add_log(f"[YAVUZ] '{self.missions[self.mission_index]}' completed.")
            self.mission_index += 1
            self.update_mission_ui()
            self.mission_time = 300
            self.add_log("[YAVUZ] Mission timer reset to 05:00.")

    def update_mission_ui(self):
        for i, lbl in enumerate(self.mission_labels):
            if i < self.mission_index:
                lbl.setText(f"✔ {self.missions[i]}")
                lbl.setStyleSheet("color: #4ade80; font-size: 12px; font-weight: bold;")
            elif i == self.mission_index:
                lbl.setText(f"▶ {self.missions[i]}")
                lbl.setStyleSheet(
                    "color: #ef4444; font-size: 13px; font-weight: bold; background: #1e293b; border-radius: 4px; padding: 4px;")
                self.lbl_mission_status.setText(f"IN PROGRESS: {self.missions[i]}")
                self.lbl_mission_status.setStyleSheet(
                    "color: #ef4444; font-weight: bold; font-size: 13px; border-bottom: 1px solid #1e293b; padding-bottom: 5px;")
                if i < len(self.mission_details):
                    self.lbl_mission_desc.setText(self.mission_details[i])
            else:
                lbl.setText(f"○ {self.missions[i]}")
                lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 5px;")

        if self.mission_index >= len(self.missions):
            self.lbl_mission_status.setText("ALL MISSIONS ACCOMPLISHED")
            self.lbl_mission_status.setStyleSheet(
                "color: #38bdf8; font-weight: bold; font-size: 13px; border-bottom: 1px solid #1e293b; padding-bottom: 5px;")
            self.lbl_mission_desc.setText("TÜM GÖREVLER BAŞARIYLA TAMAMLANDI. ARAÇ YÜZEYE ALINIYOR.")
            self.btn_next_mission.setEnabled(False)

    def swap_feeds(self):
        self.active_main = "CAM_2" if self.active_main == "CAM_1" else "CAM_1"
        if self.active_main == "CAM_2":
            self.lbl_main_title.setText("PRIMARY FEED [MINI ROV - PIPELINE MODE]")
            self.lbl_main_title.setStyleSheet(
                "font-weight: bold; color: #facc15; font-size: 13px; letter-spacing: 1px;")
        else:
            self.lbl_main_title.setText("PRIMARY OPTICAL FEED [MAIN ROV]")
            self.lbl_main_title.setStyleSheet(
                "font-weight: bold; color: #38bdf8; font-size: 13px; letter-spacing: 1px;")

    def toggle_record(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.btn_rec.setStyleSheet(
                "background-color: #ef4444; color: white; border-radius: 4px; font-weight: bold; padding: 8px;")
            self.btn_rec.setText("🔴 RECORDING")
        else:
            self.btn_rec.setStyleSheet(
                "background-color: #020617; border: 1px solid #ef4444; color: #ef4444; border-radius: 4px; font-weight: bold; padding: 8px;")
            self.btn_rec.setText("⚫ STANDBY")

    def system_tick(self):
        if not self.is_emergency:
            for bar in self.bars:
                power = random.randint(10, 85)
                bar.setValue(power)
                color = "#facc15" if power > 75 else "#38bdf8"
                bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}")

            if self.mission_time > 0 and random.random() < 0.1:
                self.mission_time -= 1
                m, s = divmod(self.mission_time, 60)
                self.lbl_clock.setText(f"{m:02d}:{s:02d}")
                if self.mission_time <= 60: self.lbl_clock.setStyleSheet(
                    "font-size: 32px; font-weight: bold; color: #facc15;")
                if self.mission_time <= 30: self.lbl_clock.setStyleSheet(
                    "font-size: 32px; font-weight: bold; color: #ef4444;")

            v = 14.8 + random.uniform(-0.3, 0.3)
            d = 4.2 + random.uniform(-0.1, 0.1)
            t = 18.5 + random.uniform(-0.05, 0.05)

            self.lbl_volt.setText(f"{v:.1f}V")
            if v > 48.0 or v < 12.0:
                self.lbl_volt.setStyleSheet(
                    "color: #ef4444; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
            else:
                self.lbl_volt.setStyleSheet(
                    "color: #ffffff; font-size: 24px; font-weight: bold; font-family: 'Consolas';")

            self.lbl_depth.setText(f"{d:.1f}m")
            if d > 18.0:
                self.lbl_depth.setStyleSheet(
                    "color: #ef4444; font-size: 24px; font-weight: bold; font-family: 'Consolas';")
            else:
                self.lbl_depth.setStyleSheet(
                    "color: #ffffff; font-size: 24px; font-weight: bold; font-family: 'Consolas';")

            self.lbl_temp.setText(f"{t:.1f}°C")

            self.heading = (self.heading + random.uniform(-1, 1)) % 360
            self.compass.set_angle(self.heading)
            self.lbl_head.setText(f"{int(self.heading):03d}.0° NE")

    def trigger_emergency(self):
        self.is_emergency = True
        self.btn_resume.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_control.setText("🛑 HALTED")
        self.lbl_control.setStyleSheet("font-weight: bold; color: #ef4444; font-size: 16px;")
        self.lbl_leak.setText("WARNING!")
        self.lbl_leak.setStyleSheet("color: #ef4444; font-size: 22px; font-weight: bold; font-family: 'Consolas';")

        for bar in self.bars:
            bar.setValue(0)
            bar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")
        self.add_log("[CRITICAL] YAVUZ EMERGENCY STOP ACTIVATED.")

    def resume_system(self):
        self.is_emergency = False
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_control.setText("🎮 MANUAL")
        self.lbl_control.setStyleSheet("font-weight: bold; color: #facc15; font-size: 16px;")
        self.lbl_leak.setText("GÜVENLİ")
        self.lbl_leak.setStyleSheet("color: #4ade80; font-size: 22px; font-weight: bold; font-family: 'Consolas';")
        self.add_log("[INFO] YAVUZ System Resumed.")

    def update_video(self, img, source):
        if not self.is_emergency:
            pix = QtGui.QPixmap.fromImage(img)
            if source == self.active_main:
                self.main_cam.setPixmap(pix.scaled(self.main_cam.size(), Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.mini_cam.setPixmap(pix.scaled(self.mini_cam.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def add_log(self, msg):
        time = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{time}] {msg}")


if __name__ == "__main__":
    try:
        app = QtWidgets.QApplication(sys.argv)
        window = ROVGroundStation()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print("\n" + "=" * 50)
        print("🚨 BEKLENMEYEN BİR HATA OLUŞTU:")
        traceback.print_exc()
        print("=" * 50)
        input("Pencereyi kapatmak için Enter'a basın...")