from PyQt5.QtWidgets import (QGraphicsItem, QMenu, QDialog)
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QBrush, QTransform
from properties_dialog import PropertiesDialog


class GraphicsCircuitItem(QGraphicsItem):
    """Базовый класс для всех электронных компонентов"""
    
    def __init__(self, element_type, x, y):
        super().__init__()
        self.element_type = element_type
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # Список подключенных проводов
        self.wires = []
        self.properties = {"Name": element_type}
        
        # Специальные свойства для рубильника
        if element_type == "Switch":
            self.properties["State"] = "closed"
            self.properties["Resistance_closed"] = 1e-6
            self.properties["Resistance_open"] = 1e12
        
        self.terminal_size = 4
        self.terminal_hover_size = 12
        self.font = QFont()
        self.font.setPointSize(8)
        self.show_label = False
        
        # Ориентация и поворот компонента
        self.rotation_angle = 0
        self.is_flipped = False
        
        # Важно: устанавливаем точку трансформации в центр
        self.setTransformOriginPoint(0, 0)

        self.setAcceptHoverEvents(True)

        # Инициализация свойств компонентов
        if element_type == "Resistor":
            self.properties["Resistance"] = 1000.0
        elif element_type == "Capacitor":
            self.properties["Capacitance"] = 1e-6
        elif element_type == "Inductor":
            self.properties["Inductance"] = 1e-3
        elif element_type == "Voltage Source":
            self.properties["Voltage"] = 5.0
        elif element_type == "Switch":
            self.properties["Name"] = "K1"
            self.properties["State"] = "closed"
            self.properties["Resistance_closed"] = 1e-6
            self.properties["Resistance_open"] = 1e12

    def get_terminal_rect(self, terminal):
        """Получение прямоугольной области терминала для обнаружения кликов"""
        if isinstance(terminal, tuple):
            terminal_point = QPointF(terminal[0], terminal[1])
        else:
            terminal_point = terminal
        return QRectF(
            terminal_point.x() - self.terminal_hover_size/2,
            terminal_point.y() - self.terminal_hover_size/2,
            self.terminal_hover_size,
            self.terminal_hover_size
        )

    def itemChange(self, change, value):
        """Обработка изменений элемента (перемещение, поворот, трансформация)"""
        if change == QGraphicsItem.ItemPositionChange:
            return super().itemChange(change, value)
            
        elif change == QGraphicsItem.ItemPositionHasChanged:
            QTimer.singleShot(0, self.update_connected_wires)
            
        elif change == QGraphicsItem.ItemRotationChange:
            return super().itemChange(change, value)
            
        elif change == QGraphicsItem.ItemRotationHasChanged:
            self.rotation_angle = self.rotation()
            QTimer.singleShot(0, self.update_connected_wires)
            
        elif change == QGraphicsItem.ItemTransformChange:
            return super().itemChange(change, value)
            
        elif change == QGraphicsItem.ItemTransformHasChanged:
            QTimer.singleShot(0, self.update_connected_wires)
            
        return super().itemChange(change, value)

    def update_connected_wires(self):
        """Обновление всех подключенных проводов"""
        # Создаем копию списка проводов, чтобы избежать проблем при изменении во время итерации
        wires_copy = self.wires[:]
        for wire in wires_copy:
            if wire and wire.scene():
                try:
                    wire.update_path()
                except RuntimeError:
                    pass

    def add_wire(self, wire):
        """Добавление провода к списку подключенных проводов"""
        if wire not in self.wires:
            self.wires.append(wire)

    def remove_wire(self, wire):
        """Удаление провода из списка подключенных проводов"""
        if wire in self.wires:
            self.wires.remove(wire)

    def boundingRect(self):
        """Определение границ компонента"""
        return QRectF(-35, -35, 70, 70)

    def drawLabel(self, painter):
        """Отрисовка подписи компонента"""
        if self.show_label:
            painter.save()
            painter.setFont(self.font)
            painter.setPen(QPen(Qt.black))
            text = self.properties.get("Name", self.element_type)
            
            if self.element_type == "Switch":
                state = self.properties.get("State", "closed")
                state_text = "замкнут" if state == "closed" else "разомкнут"
                text += f" [{state_text}]"
            
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(text)
            painter.drawText(int(-text_width/2), int(-35), text)
            painter.restore()

    def paint(self, painter, option, widget):
        """Основная функция отрисовки компонента"""
        painter.setRenderHint(QPainter.Antialiasing)
        painter.save()

        # Подсветка выделенного компонента
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 215, 100), 2, Qt.DashLine))
            painter.drawRect(self.boundingRect().adjusted(2, 2, -2, -2))

        # Отрисовка символа компонента
        painter.setPen(QPen(Qt.black, 2))
        self.drawComponent(painter)

        # Отрисовка терминалов (точек подключения)
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QBrush(Qt.black))
        terminals = self.get_terminals()
        for (x, y), label in terminals.items():
            rect = QRectF(
                x - self.terminal_size/2,
                y - self.terminal_size/2,
                self.terminal_size,
                self.terminal_size
            )
            painter.drawEllipse(rect)

            painter.setFont(self.font)
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label)
            painter.drawText(
                int(x - text_width/2),
                int(y + 20),
                label
            )

        painter.restore()
        
        self.drawLabel(painter)

    def drawComponent(self, painter):
        """Отрисовка символа компонента"""
        if self.element_type == "Resistor":
            path = QPainterPath()
            path.moveTo(-25, 0)
            path.lineTo(-15, 0)
            path.lineTo(-10, -8)
            path.lineTo(-2, 8)
            path.lineTo(6, -8)
            path.lineTo(14, 8)
            path.lineTo(18, 0)
            path.lineTo(25, 0)
            painter.drawPath(path)

        elif self.element_type == "Capacitor":
            painter.drawLine(-5, -15, -5, 15)
            painter.drawLine(5, -15, 5, 15)
            painter.drawLine(-25, 0, -5, 0)
            painter.drawLine(5, 0, 25, 0)

        elif self.element_type == "Inductor":
            painter.drawLine(-25, 0, -15, 0)
            painter.drawLine(15, 0, 25, 0)
            for i in range(4):
                x_start = -15 + i * 7.5
                rect = QRectF(x_start, -7.5, 7.5, 15)
                painter.drawArc(rect, 0, 180 * 16)

        elif self.element_type == "Voltage Source":
            painter.drawEllipse(-15, -15, 30, 30)
            painter.drawLine(8, -5, 8, 5)
            painter.drawLine(5, 0, 11, 0)
            painter.drawLine(-8, 0, -4, 0)
            painter.drawLine(-25, 0, -15, 0)
            painter.drawLine(15, 0, 25, 0)

        elif self.element_type == "Ground":
            painter.drawLine(0, -15, 0, 0)
            painter.drawLine(-15, 0, 15, 0)
            painter.drawLine(-9, 5, 9, 5)
            painter.drawLine(-3, 10, 3, 10)
            
        elif self.element_type == "Switch":
            state = self.properties.get("State", "closed")
            
            painter.drawLine(-25, 0, -10, 0)
            
            if state == "closed":
                painter.drawLine(-10, 0, 10, 0)
                painter.setBrush(QBrush(Qt.white))
                painter.drawEllipse(-12, -2, 4, 4)
                painter.drawEllipse(8, -2, 4, 4)
                painter.setBrush(QBrush(Qt.black))
            else:
                painter.drawLine(-10, 0, 0, -15)
                painter.setBrush(QBrush(Qt.white))
                painter.drawEllipse(-12, -2, 4, 4)
                painter.drawEllipse(8, -2, 4, 4)
                painter.setBrush(QBrush(Qt.black))
                painter.drawEllipse(-2, -17, 4, 4)
            
            painter.drawLine(10, 0, 25, 0)

    def contextMenuEvent(self, event):
        """Контекстное меню компонента"""
        menu = QMenu()
        properties_action = menu.addAction("Свойства")
        rotate_cw_action = menu.addAction("Повернуть на 90° по часовой")
        rotate_ccw_action = menu.addAction("Повернуть на 90° против часовой")
        flip_action = menu.addAction("Отразить горизонтально")
        
        if self.element_type == "Switch":
            menu.addSeparator()
            current_state = self.properties.get("State", "closed")
            toggle_action = menu.addAction(
                "Разомкнуть" if current_state == "closed" else "Замкнуть"
            )
            toggle_action.triggered.connect(self.toggle_switch)
        
        delete_action = menu.addAction("Удалить")
        
        action = menu.exec_(event.globalPos())

        if action == properties_action:
            self.show_properties_dialog()
        elif action == rotate_cw_action:
            self.rotate_clockwise()
        elif action == rotate_ccw_action:
            self.rotate_counterclockwise()
        elif action == flip_action:
            self.flip_horizontal()
        elif action == delete_action:
            self.remove()
    
    def toggle_switch(self):
        """Переключение состояния рубильника"""
        if self.element_type == "Switch":
            current_state = self.properties.get("State", "closed")
            new_state = "open" if current_state == "closed" else "closed"
            self.properties["State"] = new_state
            self.update()
            self.update_connected_wires()
    
    def rotate_clockwise(self):
        """Поворот элемента на 90 градусов по часовой стрелке"""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.prepareGeometryChange()
        
        # Правильная комбинация трансформаций
        transform = QTransform()
        transform.rotate(self.rotation_angle)
        if self.is_flipped:
            transform.scale(-1, 1)
        
        self.setTransform(transform)
        self.update_connected_wires()
        self.update()
    
    def rotate_counterclockwise(self):
        """Поворот элемента на 90 градусов против часовой стрелки"""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self.prepareGeometryChange()
        
        # Правильная комбинация трансформаций
        transform = QTransform()
        transform.rotate(self.rotation_angle)
        if self.is_flipped:
            transform.scale(-1, 1)
        
        self.setTransform(transform)
        self.update_connected_wires()
        self.update()
    
    def flip_horizontal(self):
        """Горизонтальное отражение элемента"""
        self.is_flipped = not self.is_flipped
        self.prepareGeometryChange()
        
        # Правильная комбинация трансформаций: сначала поворот, потом отражение
        transform = QTransform()
        transform.rotate(self.rotation_angle)
        transform.scale(-1 if self.is_flipped else 1, 1)
        
        self.setTransform(transform)
        self.update_connected_wires()
        self.update()

    def show_properties_dialog(self):
        """Показ диалога свойств компонента"""
        dialog = PropertiesDialog(self.properties, self.element_type)
        if dialog.exec_() == QDialog.Accepted:
            self.properties = dialog.get_properties()
            self.update()
            self.update_connected_wires()

    def get_terminals(self):
        """
        Получение позиций терминалов с учетом поворота и отражения.
        Возвращаем кортежи (x, y) в локальных координатах компонента.
        """
        if self.element_type in ("Resistor", "Capacitor", "Inductor", "Switch"):
            base_terminals = {(-25, 0): "in", (25, 0): "out"}
        elif self.element_type == "Voltage Source":
            base_terminals = {(-25, 0): "-", (25, 0): "+"}
        elif self.element_type == "Current Source":
            base_terminals = {(-25, 0): "-", (25, 0): "+"}
        elif self.element_type == "Ground":
            base_terminals = {(0, -15): "gnd"}
        else:
            base_terminals = {}
        
        return base_terminals.copy()
    
    def get_terminal_scene_pos(self, terminal_pos):
        """
        Получить глобальную позицию терминала.
        Используем mapToScene с учетом всех трансформаций.
        """
        if isinstance(terminal_pos, tuple):
            return self.mapToScene(QPointF(terminal_pos[0], terminal_pos[1]))
        return self.mapToScene(terminal_pos)
    
    def remove(self):
        """Удаление компонента"""
        for wire in self.wires[:]:
            if wire and wire.scene():
                wire.remove()
        
        if self.scene():
            self.scene().removeItem(self)