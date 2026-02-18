from PyQt5.QtWidgets import (QMainWindow, QToolBar, QAction, QDockWidget,
                             QSplitter, QVBoxLayout, QWidget, QMessageBox,
                             QGridLayout, QFrame, QLabel, QUndoView, QUndoGroup,
                             QDialog)
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QPainterPath, QDrag, QFont, QBrush, QFontMetrics

from canvas import Canvas
from solver import CircuitSolver
from simulation_results import SimulationResults
from file_handler import FileHandler
from commands import *
from settings_dialog import SettingsDialog


class ElementWidget(QLabel):
    """Виджет элемента в библиотеке компонентов"""
    
    WIDTH = 120
    SYMBOL_HEIGHT = 70
    PADDING = 5

    def __init__(self, element_type, element_name, parent=None):
        super().__init__(parent)
        self.element_type = element_type
        self.element_name = element_name

        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setAlignment(Qt.AlignCenter)

        self.setStyleSheet("""
            QLabel {
                background-color: white;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin: 2px;
            }
            QLabel:hover {
                border: 2px solid #0066cc;
                background-color: #f0f8ff;
            }
        """)

        self.create_element_image()

    def create_element_image(self):
        font = QFont()
        font.setPointSize(10)
        metrics = QFontMetrics(font)

        text_width = self.WIDTH - 2 * self.PADDING

        text_rect = metrics.boundingRect(
            0, 0,
            text_width, 1000,
            Qt.TextWordWrap,
            self.element_name
        )

        text_height = text_rect.height()
        total_height = self.SYMBOL_HEIGHT + text_height + 2 * self.PADDING

        pixmap = QPixmap(self.WIDTH, total_height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        self.draw_element_symbol(painter)

        painter.setFont(font)
        painter.setPen(QPen(Qt.black, 1))

        painter.drawText(
            QRectF(
                self.PADDING,
                self.SYMBOL_HEIGHT,
                text_width,
                text_height
            ),
            Qt.AlignCenter | Qt.TextWordWrap,
            self.element_name
        )

        painter.end()

        self.setPixmap(pixmap)
        self.setFixedSize(self.WIDTH, total_height)

    def draw_element_symbol(self, painter):
        painter.setPen(QPen(Qt.black, 2))

        if self.element_type == "Resistor":
            path = QPainterPath()
            path.moveTo(20, 40)
            path.lineTo(30, 40)
            path.lineTo(35, 30)
            path.lineTo(45, 50)
            path.lineTo(55, 30)
            path.lineTo(65, 50)
            path.lineTo(75, 30)
            path.lineTo(85, 40)
            path.lineTo(100, 40)
            painter.drawPath(path)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(18, 38, 4, 4)
            painter.drawEllipse(98, 38, 4, 4)
            painter.drawText(10, 55, "in")
            painter.drawText(95, 55, "out")

        elif self.element_type == "Capacitor":
            painter.drawLine(50, 25, 50, 55)
            painter.drawLine(70, 25, 70, 55)
            painter.drawLine(20, 40, 50, 40)
            painter.drawLine(70, 40, 100, 40)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(18, 38, 4, 4)
            painter.drawEllipse(98, 38, 4, 4)
            painter.drawText(10, 55, "in")
            painter.drawText(95, 55, "out")

        elif self.element_type == "Inductor":
            painter.drawLine(20, 40, 35, 40)
            painter.drawLine(85, 40, 100, 40)
            for i in range(4):
                x_start = 35 + i * 12.5
                rect = QRectF(x_start, 30, 12.5, 20)
                painter.drawArc(rect, 0, 180 * 16)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(18, 38, 4, 4)
            painter.drawEllipse(98, 38, 4, 4)
            painter.drawText(10, 55, "in")
            painter.drawText(95, 55, "out")

        elif self.element_type == "Voltage Source":
            painter.drawEllipse(40, 20, 40, 40)
            painter.drawLine(70, 35, 70, 45)
            painter.drawLine(65, 40, 75, 40)
            painter.drawLine(45, 40, 55, 40)
            painter.drawLine(20, 40, 40, 40)
            painter.drawLine(80, 40, 100, 40)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(18, 38, 4, 4)
            painter.drawEllipse(98, 38, 4, 4)
            painter.drawText(15, 55, "-")
            painter.drawText(95, 55, "+")
            
        elif self.element_type == "Switch":
            painter.drawLine(20, 40, 35, 40)
            painter.drawLine(35, 40, 65, 40)
            painter.drawLine(65, 40, 100, 40)
            
            painter.setBrush(QBrush(Qt.white))
            painter.drawEllipse(33, 38, 4, 4)
            painter.drawEllipse(63, 38, 4, 4)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(18, 38, 4, 4)
            painter.drawEllipse(98, 38, 4, 4)
            
            painter.drawText(10, 55, "in")
            painter.drawText(95, 55, "out")
            painter.drawText(45, 25, "K")

        elif self.element_type == "Ground":
            painter.drawLine(60, 20, 60, 40)
            painter.drawLine(40, 40, 80, 40)
            painter.drawLine(45, 45, 75, 45)
            painter.drawLine(50, 50, 70, 50)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(58, 18, 4, 4)
            painter.drawText(50, 65, "gnd")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.element_type)
            drag.setMimeData(mime_data)

            pixmap = QPixmap(80, 60)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setOpacity(0.7)
            painter.scale(0.7, 0.7)
            self.draw_element_symbol(painter)
            painter.end()

            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(40, 30))
            drag.exec_(Qt.CopyAction)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Симулятор электрических цепей")
        self.setGeometry(100, 100, 1600, 900)

        self.undo_group = QUndoGroup(self)
        
        self.file_handler = FileHandler(self)
        
        # Создаем экземпляр решателя цепей
        self.solver = None  # Будет создан при первом анализе
        
        self.init_ui()
        
        if hasattr(self.canvas, 'undo_stack'):
            self.undo_group.addStack(self.canvas.undo_stack)
            self.undo_group.setActiveStack(self.canvas.undo_stack)
        
        # Окно истории создаем, но НЕ показываем
        self.history_dock = None

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)

        from PyQt5.QtWidgets import QGraphicsScene
        self.scene = QGraphicsScene()
        self.canvas = Canvas(self.scene)

        self.results_widget = SimulationResults()

        splitter.addWidget(self.canvas)
        splitter.addWidget(self.results_widget)
        splitter.setSizes([1000, 600])

        layout.addWidget(splitter)

        self.create_elements_dock()
        self.create_toolbar()
        self.create_menu()
    
    def toggle_history_dock(self):
        """Показать/скрыть окно истории действий"""
        if not self.history_dock:
            if hasattr(self.canvas, 'undo_stack'):
                self.history_dock = QDockWidget("История действий", self)
                undo_view = QUndoView(self.canvas.undo_stack)
                undo_view.setEmptyLabel("Нет действий")
                self.history_dock.setWidget(undo_view)
                self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)
        else:
            if self.history_dock.isVisible():
                self.history_dock.hide()
            else:
                self.history_dock.show()

    def create_elements_dock(self):
        elements_dock = QDockWidget("Компоненты", self)
        elements_widget = QWidget()
        layout = QGridLayout()
        layout.setSpacing(5)

        element_data = [
            ("Resistor", "Резистор"),
            ("Capacitor", "Конденсатор"),
            ("Inductor", "Катушка индуктивности"),
            ("Voltage Source", "Источник напряжения"),
            ("Switch", "Рубильник"),
            ("Ground", "Земля")
        ]

        for i, (element_type, element_name) in enumerate(element_data):
            row = i // 2
            col = i % 2
            element_widget = ElementWidget(element_type, element_name)
            layout.addWidget(element_widget, row, col)

        elements_widget.setLayout(layout)
        elements_dock.setWidget(elements_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, elements_dock)

    def create_toolbar(self):
        toolbar = QToolBar("Главная панель")
        self.addToolBar(toolbar)

        new_action = QAction("Новый", self)
        new_action.triggered.connect(self.file_handler.new_file)
        toolbar.addAction(new_action)

        open_action = QAction("Открыть", self)
        open_action.triggered.connect(self.file_handler.open_file)
        toolbar.addAction(open_action)

        save_action = QAction("Сохранить", self)
        save_action.triggered.connect(self.file_handler.save_file)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        if hasattr(self.canvas, 'undo_stack'):
            self.undo_action = self.canvas.undo_stack.createUndoAction(self, "Отменить")
            self.undo_action.setShortcut("Ctrl+Z")
            toolbar.addAction(self.undo_action)
            
            self.redo_action = self.canvas.undo_stack.createRedoAction(self, "Повторить")
            self.redo_action.setShortcut("Ctrl+Y")
            toolbar.addAction(self.redo_action)
        
        toolbar.addSeparator()
        
        # Кнопка истории действий
        history_action = QAction("История", self)
        history_action.triggered.connect(self.toggle_history_dock)
        history_action.setShortcut("Ctrl+H")
        toolbar.addAction(history_action)
        
        toolbar.addSeparator()

        simulate_action = QAction("Анализ", self)
        simulate_action.triggered.connect(self.calculate_circuit)
        toolbar.addAction(simulate_action)
        
        clear_action = QAction("Очистить", self)
        clear_action.triggered.connect(self.clear_canvas)
        toolbar.addAction(clear_action)

    def create_menu(self):
        menu_bar = self.menuBar()

        # --- Меню "Файл" ---
        file_menu = menu_bar.addMenu("Файл")

        new_action = file_menu.addAction("Новый")
        new_action.triggered.connect(self.file_handler.new_file)

        open_action = file_menu.addAction("Открыть")
        open_action.triggered.connect(self.file_handler.open_file)

        save_action = file_menu.addAction("Сохранить")
        save_action.triggered.connect(self.file_handler.save_file)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Выход")
        exit_action.triggered.connect(self.close)
        
        # --- Меню "Правка" ---
        edit_menu = menu_bar.addMenu("Правка")
        
        if hasattr(self, 'undo_action'):
            edit_menu.addAction(self.undo_action)
        if hasattr(self, 'redo_action'):
            edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        
        # Добавляем пункт меню для истории
        history_menu_action = edit_menu.addAction("История действий")
        history_menu_action.triggered.connect(self.toggle_history_dock)
        history_menu_action.setShortcut("Ctrl+H")
        edit_menu.addSeparator()
        
        clear_all_action = edit_menu.addAction("Очистить все")
        clear_all_action.triggered.connect(self.clear_canvas)
        clear_all_action.setShortcut("Ctrl+Shift+Del")
        
        select_all_action = edit_menu.addAction("Выделить все")
        select_all_action.triggered.connect(self.select_all_items)
        select_all_action.setShortcut("Ctrl+A")

        # --- Меню "Схема" ---
        circuit_menu = menu_bar.addMenu("Схема")
        
        toggle_all_action = circuit_menu.addAction("Разомкнуть все рубильники")
        toggle_all_action.triggered.connect(self.toggle_all_switches)
        
        close_all_action = circuit_menu.addAction("Замкнуть все рубильники")
        close_all_action.triggered.connect(self.close_all_switches)

        # --- Меню "Настройки" ---
        settings_menu = menu_bar.addMenu("Настройки")
        
        source_settings_action = settings_menu.addAction("Тип источника напряжения")
        source_settings_action.triggered.connect(self.show_settings_dialog)
        
        settings_menu.addSeparator()
        
        grid_action = settings_menu.addAction("Показать/скрыть сетку (G)")
        grid_action.triggered.connect(self.toggle_grid)

        # --- Меню "Справка" ---
        help_menu = menu_bar.addMenu("Справка")
        about_action = help_menu.addAction("О программе")
        about_action.triggered.connect(
            lambda: QMessageBox.information(
                self, 
                "О программе", 
                "Симулятор электрических цепей\n"
                "Поддерживаемые элементы:\n"
                "- Резисторы, конденсаторы, катушки\n"
                "- Источники напряжения\n"
                "- Рубильники\n"
                "- Земля\n\n"
                "Анализ методом узловых напряжений\n"
                "в операторной форме (Лаплас)\n\n"
                "Управление:\n"
                "• Левая кнопка мыши - выделение элементов\n"
                "• Правая кнопка мыши - контекстное меню\n"
                "• Зажатое колесико мыши - перемещение по рабочему пространству\n"
                "• Ctrl+Z - Отменить действие\n"
                "• Ctrl+Y - Повторить действие\n"
                "• Ctrl+H - История действий\n"
                "• Ctrl+A - Выделить всё\n"
                "• Delete - Удалить выделенное\n"
                "• Перетаскивание компонентов из библиотеки - добавление на схему\n"
                "• Перетаскивание проводов - изменение их формы\n"
                "• Выделенные объекты перемещаются с шагом сетки (10 пикселей)"
            )
        )

    def toggle_grid(self):
        """Переключение видимости сетки"""
        if hasattr(self.canvas, 'grid_background'):
            if self.canvas.grid_background.isVisible():
                self.canvas.grid_background.hide()
            else:
                self.canvas.grid_background.show()

    def select_all_items(self):
        for item in self.scene.items():
            from canvas import InfiniteGridBackground
            if not isinstance(item, InfiniteGridBackground):
                try:
                    item.setSelected(True)
                except:
                    pass

    def toggle_all_switches(self):
        for item in self.scene.items():
            if hasattr(item, 'element_type') and item.element_type == "Switch":
                if item.properties.get("State") == "closed":
                    if hasattr(self.canvas, 'undo_stack'):
                        old_props = item.properties.copy()
                        item.toggle_switch()
                        new_props = item.properties.copy()
                        
                        from commands import ChangePropertiesCommand
                        command = ChangePropertiesCommand(
                            self.scene, item, old_props, new_props
                        )
                        self.canvas.undo_stack.push(command)
                    else:
                        item.toggle_switch()
        
        self.scene.update()

    def close_all_switches(self):
        for item in self.scene.items():
            if hasattr(item, 'element_type') and item.element_type == "Switch":
                if item.properties.get("State") == "open":
                    if hasattr(self.canvas, 'undo_stack'):
                        old_props = item.properties.copy()
                        item.toggle_switch()
                        new_props = item.properties.copy()
                        
                        from commands import ChangePropertiesCommand
                        command = ChangePropertiesCommand(
                            self.scene, item, old_props, new_props
                        )
                        self.canvas.undo_stack.push(command)
                    else:
                        item.toggle_switch()
        
        self.scene.update()

    def clear_canvas(self):
        """Очистка всех элементов с рабочего поля"""
        grid_background = None
        grid_size = 10
        if hasattr(self.canvas, 'grid_background') and self.canvas.grid_background:
            grid_size = self.canvas.grid_background.grid_size
            grid_background = self.canvas.grid_background
        
        from PyQt5.QtWidgets import QUndoCommand
        
        class ClearCanvasCommand(QUndoCommand):
            def __init__(self, scene, canvas, grid_size):
                super().__init__("Очистка схемы")
                self.scene = scene
                self.canvas = canvas
                self.grid_size = grid_size
                self.saved_commands = []
                
                # Сохраняем все элементы перед очисткой
                for item in self.scene.items():
                    from canvas import InfiniteGridBackground
                    from wire import Wire
                    
                    if isinstance(item, InfiniteGridBackground):
                        continue
                    
                    try:
                        if hasattr(item, 'element_type') and hasattr(item, 'remove'):
                            from commands import RemoveComponentCommand
                            cmd = RemoveComponentCommand(self.scene, item)
                            self.saved_commands.append(cmd)
                        elif isinstance(item, Wire):
                            from commands import RemoveWireCommand
                            cmd = RemoveWireCommand(self.scene, item)
                            self.saved_commands.append(cmd)
                    except Exception as e:
                        print(f"Ошибка при сохранении элемента {item}: {e}")
                        continue
            
            def redo(self):
                # Очищаем сцену, удаляя все элементы кроме фона
                items_to_remove = []
                for item in self.scene.items():
                    from canvas import InfiniteGridBackground
                    if not isinstance(item, InfiniteGridBackground):
                        items_to_remove.append(item)
                
                for item in items_to_remove:
                    try:
                        if item.scene():
                            self.scene.removeItem(item)
                    except:
                        pass
                
                # Добавляем фон заново
                from canvas import InfiniteGridBackground
                self.canvas.grid_background = InfiniteGridBackground(self.grid_size)
                self.scene.addItem(self.canvas.grid_background)
            
            def undo(self):
                # Восстанавливаем все сохраненные элементы
                # Сначала удаляем текущий фон
                for item in self.scene.items():
                    from canvas import InfiniteGridBackground
                    if isinstance(item, InfiniteGridBackground):
                        self.scene.removeItem(item)
                        break
                
                # Восстанавливаем все элементы в обратном порядке
                for cmd in reversed(self.saved_commands):
                    try:
                        cmd.undo()
                    except Exception as e:
                        print(f"Ошибка при восстановлении: {e}")
                        continue
        
        if hasattr(self.canvas, 'undo_stack'):
            command = ClearCanvasCommand(self.scene, self.canvas, grid_size)
            self.canvas.undo_stack.push(command)
        else:
            self.scene.clear()
            if grid_background:
                from canvas import InfiniteGridBackground
                self.canvas.grid_background = InfiniteGridBackground(grid_size)
                self.scene.addItem(self.canvas.grid_background)
        
        if hasattr(self, 'results_widget'):
            self.results_widget.clear_all()

    def calculate_circuit(self):
        """Анализ цепи"""
        # Создаем solver при первом анализе
        if self.solver is None:
            self.solver = CircuitSolver(self.scene)
        else:
            # Обновляем сцену в существующем solver
            self.solver.scene = self.scene
        
        results = self.solver.analyze_circuit()
        self.results_widget.display_results(results, self.solver)
    
    def show_settings_dialog(self):
        """Показ диалога настроек"""
        # Создаем solver, если его еще нет
        if self.solver is None:
            self.solver = CircuitSolver(self.scene)
        
        from settings_dialog import SettingsDialog
        
        dialog = SettingsDialog(self.solver, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            
            # Передаем настройки в solver
            self.solver.set_source_type(
                settings['source_type'],
                settings['source_params']
            )
            
            # Показываем сообщение о применении настроек
            source_type_text = "постоянный" if settings['source_type'] == "DC" else "синусоидальный"
            QMessageBox.information(
                self,
                "Настройки применены",
                f"Тип источника напряжения изменен на {source_type_text}.\n"
                "Для применения новых настроек выполните анализ схемы заново."
            )