"""
Модуль для работы с проводами в электрической схеме.
Провода соединяют только компоненты, узловые точки отсутствуют.
"""

from PyQt5.QtWidgets import QGraphicsPathItem, QMenu, QAction
from PyQt5.QtCore import QPointF, Qt, QTimer
from PyQt5.QtGui import QPainterPath, QPen, QColor, QPainter


class Wire(QGraphicsPathItem):
    """
    Провод, соединяющий два компонента.
    Провода всегда идут напрямую от компонента к компоненту,
    без промежуточных узловых точек.
    """
    
    def __init__(self, path_data=None):
        """
        Конструктор провода.
        
        Args:
            path_data (dict, optional): Данные пути для восстановления провода
        """
        super().__init__()
        
        # Подключения к компонентам
        self.start_item = None
        self.start_terminal = None
        self.end_item = None
        self.end_terminal = None
        
        # Сохраненный путь для восстановления формы
        self.saved_path = None
        if path_data:
            self.saved_path = self._path_from_data(path_data)
        
        # Настройка внешнего вида
        self.normal_pen = QPen(QColor(0, 0, 0), 2)
        self.selected_pen = QPen(QColor(0, 100, 255), 3)
        self.hover_pen = QPen(QColor(0, 120, 215), 2.5)
        
        self.setPen(self.normal_pen)
        self.setZValue(10)
        
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        
        # Флаг для отслеживания перетаскивания
        self.is_dragging = False
        self.drag_start_path = None
    
    def _path_from_data(self, path_data):
        """Восстановление пути из сохраненных данных"""
        if not path_data or 'elements' not in path_data:
            return None
        
        path = QPainterPath()
        elements = path_data['elements']
        
        for elem in elements:
            if elem['type'] == 'move':
                path.moveTo(elem['x'], elem['y'])
            elif elem['type'] == 'line':
                path.lineTo(elem['x'], elem['y'])
        
        return path
    
    def _path_to_data(self):
        """Сохранение пути в данные для файла"""
        path = self.path()
        if path.isEmpty():
            return None
        
        data = {'elements': []}
        
        for i in range(path.elementCount()):
            elem = path.elementAt(i)
            if elem.isMoveTo():
                data['elements'].append({
                    'type': 'move',
                    'x': elem.x,
                    'y': elem.y
                })
            elif elem.isLineTo():
                data['elements'].append({
                    'type': 'line',
                    'x': elem.x,
                    'y': elem.y
                })
        
        return data
    
    def connect_to_component(self, component, terminal, is_start=True):
        """Подключить провод к компоненту"""
        if not component or not terminal:
            return False
            
        if is_start:
            # Отключаем от предыдущего компонента, если был
            if self.start_item:
                self.start_item.remove_wire(self)
            self.start_item = component
            self.start_terminal = terminal
            component.add_wire(self)
        else:
            # Отключаем от предыдущего компонента, если был
            if self.end_item:
                self.end_item.remove_wire(self)
            self.end_item = component
            self.end_terminal = terminal
            component.add_wire(self)
        
        self.update_path()
        return True
    
    def get_start_pos(self):
        """Получить начальную позицию провода в координатах сцены"""
        if self.start_item and self.start_terminal:
            return self.start_item.mapToScene(
                QPointF(self.start_terminal[0], self.start_terminal[1])
            )
        return None
    
    def get_end_pos(self):
        """Получить конечную позицию провода в координатах сцены"""
        if self.end_item and self.end_terminal:
            return self.end_item.mapToScene(
                QPointF(self.end_terminal[0], self.end_terminal[1])
            )
        return None
    
    def is_connected(self):
        """Проверка, подключен ли провод с обоих концов"""
        return (self.start_item is not None and 
                self.start_terminal is not None and
                self.end_item is not None and 
                self.end_terminal is not None)
    
    def update_path(self):
        """Обновление пути провода с сохранением пользовательской формы"""
        if not self.is_connected():
            return
        
        start_pos = self.get_start_pos()
        end_pos = self.get_end_pos()
        
        if start_pos is None or end_pos is None:
            return
        
        # Если есть сохраненный пользовательский путь, адаптируем его к новым позициям
        if self.saved_path and not self.saved_path.isEmpty():
            self._adapt_saved_path(start_pos, end_pos)
        else:
            # Иначе создаем ортогональный путь по умолчанию
            self._create_default_path(start_pos, end_pos)
    
    def _adapt_saved_path(self, start_pos, end_pos):
        """Адаптирует сохраненный путь к текущим позициям компонентов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if not self.saved_path or self.saved_path.isEmpty():
            self._create_default_path(start_pos, end_pos)
            return
        
        try:
            # Получаем первую и последнюю точки сохраненного пути
            first_elem = self.saved_path.elementAt(0)
            last_elem = self.saved_path.elementAt(self.saved_path.elementCount() - 1)
            
            # Сохраняем относительные смещения, а не абсолютные координаты
            # Это позволяет правильно адаптировать путь при перемещении компонентов
            
            # Создаем новый путь в координатах сцены
            scene_path = QPainterPath()
            scene_path.moveTo(start_pos)
            
            # Если путь имеет промежуточные точки, сохраняем их относительные смещения
            if self.saved_path.elementCount() > 2:
                # Вычисляем векторы между точками сохраненного пути
                vectors = []
                prev_point = QPointF(first_elem.x, first_elem.y)
                
                for i in range(1, self.saved_path.elementCount()):
                    elem = self.saved_path.elementAt(i)
                    if elem.isLineTo():
                        current_point = QPointF(elem.x, elem.y)
                        # Сохраняем вектор относительно предыдущей точки
                        vectors.append(current_point - prev_point)
                        prev_point = current_point
                
                # Восстанавливаем путь с теми же относительными смещениями
                current_point = start_pos
                for vec in vectors:
                    current_point += vec
                    scene_path.lineTo(current_point)
            
            # Убеждаемся, что путь заканчивается в конечной точке
            if scene_path.elementCount() > 0:
                last_point = scene_path.elementAt(scene_path.elementCount() - 1)
                last_point_qpoint = QPointF(last_point.x, last_point.y)
                if (last_point_qpoint - end_pos).manhattanLength() > 5:
                    scene_path.lineTo(end_pos)
            
            # Преобразуем в локальные координаты
            local_path = self.mapFromScene(scene_path)
            self.setPath(local_path)
            
        except Exception as e:
            print(f"Ошибка при адаптации пути: {e}")
            self._create_default_path(start_pos, end_pos)
    
    def _create_default_path(self, start_pos, end_pos):
        """Создает путь по умолчанию (ортогональный)"""
        path = QPainterPath()
        path.moveTo(start_pos)
        
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        
        if abs(dx) > abs(dy):
            # Сначала горизонталь, потом вертикаль
            path.lineTo(QPointF(end_pos.x(), start_pos.y()))
            path.lineTo(end_pos)
        else:
            # Сначала вертикаль, потом горизонталь
            path.lineTo(QPointF(start_pos.x(), end_pos.y()))
            path.lineTo(end_pos)
        
        # Преобразуем путь в локальные координаты
        local_path = self.mapFromScene(path)
        self.setPath(local_path)
    
    def set_custom_path(self, path):
        """Установка пользовательского пути (при перетаскивании)"""
        # Сохраняем путь как есть (он уже в локальных координатах)
        self.setPath(path)
        # НЕ сохраняем как saved_path сразу, чтобы можно было отменить
    
    def save_current_path(self):
        """Сохранить текущий путь как постоянный"""
        self.saved_path = self.path()
    
    def paint(self, painter, option, widget):
        """Отрисовка провода с учётом состояния"""
        if self.isSelected():
            painter.setPen(self.selected_pen)
        elif self.isUnderMouse():
            painter.setPen(self.hover_pen)
        else:
            painter.setPen(self.normal_pen)
        
        painter.drawPath(self.path())
    
    def hoverEnterEvent(self, event):
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.update()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши - начало перетаскивания провода"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_path = self.path()
            self.setSelected(True)
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка перемещения мыши - изменение формы провода"""
        if self.is_dragging and event.buttons() & Qt.LeftButton:
            # При перетаскивании не обновляем путь автоматически
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши - сохранение формы провода"""
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            # Сохраняем текущий путь как постоянный ТОЛЬКО если он изменился
            if self.drag_start_path and self.drag_start_path != self.path():
                self.save_current_path()
            event.accept()
        super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event):
        """Контекстное меню для провода"""
        if self.isSelected() and self.is_connected():
            menu = QMenu()
            
            delete_action = QAction("Удалить провод", self)
            delete_action.triggered.connect(self.remove)
            menu.addAction(delete_action)
            
            menu.exec_(event.screenPos())
        else:
            super().contextMenuEvent(event)
    
    def remove(self):
        """Удаление провода"""
        # Отключаем от компонентов
        if self.start_item:
            self.start_item.remove_wire(self)
        if self.end_item:
            self.end_item.remove_wire(self)
        
        if self.scene():
            self.scene().removeItem(self)
    
    def get_save_data(self):
        """Получение данных для сохранения в файл"""
        if not self.is_connected():
            return None
        
        data = {
            'start_element_id': id(self.start_item),
            'start_terminal': list(self.start_terminal) if self.start_terminal else None,
            'end_element_id': id(self.end_item),
            'end_terminal': list(self.end_terminal) if self.end_terminal else None,
        }
        
        # Сохраняем путь провода, если он нестандартный
        if self.saved_path and not self.saved_path.isEmpty():
            path_data = self._path_to_data()
            if path_data:
                data['path'] = path_data
        
        return data