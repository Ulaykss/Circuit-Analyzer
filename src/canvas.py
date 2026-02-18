from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QMenu,
                             QAction, QGraphicsItem, QGraphicsRectItem,
                             QUndoStack, QUndoCommand)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer, QMimeData, QLineF
from PyQt5.QtGui import (QPainterPath, QPen, QPainter,
                        QColor, QBrush, QDrag, QTransform)
from circuit_elements import GraphicsCircuitItem
from wire import Wire
from commands import *
import weakref


class ComponentPreview(GraphicsCircuitItem):
    """Предварительный просмотр компонента при перетаскивании"""
    
    def __init__(self, element_type):
        super().__init__(element_type, 0, 0)
        self.setOpacity(0.7)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setCursor(Qt.DragCopyCursor)


class InfiniteGridBackground(QGraphicsRectItem):
    """Фон с бесконечной сеткой"""
    
    def __init__(self, grid_size=10):
        super().__init__()
        self.grid_size = grid_size
        self.setZValue(-1000)
        self.setRect(-1000000, -1000000, 2000000, 2000000)
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.NoPen))
    
    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        
        painter.save()
        
        view = widget.parent() if widget else None
        if view:
            view_rect = view.mapToScene(view.viewport().rect()).boundingRect()
            
            left = view_rect.left() - self.grid_size
            right = view_rect.right() + self.grid_size
            top = view_rect.top() - self.grid_size
            bottom = view_rect.bottom() + self.grid_size
            
            grid_left = left - (left % self.grid_size)
            grid_right = right
            grid_top = top - (top % self.grid_size)
            grid_bottom = bottom
            
            # Мелкая сетка
            painter.setPen(QPen(QColor(240, 240, 240), 1))
            
            x = grid_left
            while x <= grid_right:
                painter.drawLine(QLineF(x, grid_top, x, grid_bottom))
                x += self.grid_size
            
            y = grid_top
            while y <= grid_bottom:
                painter.drawLine(QLineF(grid_left, y, grid_right, y))
                y += self.grid_size
            
            # Крупная сетка
            major_grid_size = self.grid_size * 10
            major_grid_left = grid_left - (grid_left % major_grid_size)
            major_grid_top = grid_top - (grid_top % major_grid_size)
            
            painter.setPen(QPen(QColor(220, 220, 220), 1))
            
            x = major_grid_left
            while x <= grid_right:
                painter.drawLine(QLineF(x, grid_top, x, grid_bottom))
                x += major_grid_size
            
            y = major_grid_top
            while y <= grid_bottom:
                painter.drawLine(QLineF(grid_left, y, grid_right, y))
                y += major_grid_size
            
            # Центральные оси
            painter.setPen(QPen(QColor(100, 100, 255, 100), 1.5))
            painter.drawLine(QLineF(0, grid_top, 0, grid_bottom))
            painter.drawLine(QLineF(grid_left, 0, grid_right, 0))
        
        painter.restore()


class Canvas(QGraphicsView):
    """Основное рабочее поле для размещения компонентов и проводов"""
    
    def __init__(self, scene):
        super().__init__(scene)
        self.scene = scene
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self.setAcceptDrops(True)
        
        # Стек отмены действий
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(100)
        
        # Переменные для создания проводов
        self.dragging_wire = False
        self.current_wire = None
        self.wire_start_pos = None
        self.wire_start_item = None
        self.wire_start_terminal = None
        
        # Переменные для перетаскивания существующего провода (изменение формы)
        self.dragging_wire_point = False
        self.dragged_wire = None
        self.drag_start_pos = None
        self.drag_offset = None
        self.temp_wire_path = None
        
        # Переменные для перемещения с помощью зажатого колёсика
        self.panning = False
        self.pan_start_pos = None
        self.pan_start_h_scroll = None
        self.pan_start_v_scroll = None
        
        self.highlight_items = []
        self.snap_threshold = 20
        
        self.zoom_factor = 1.15
        self.min_zoom = 0.01
        self.max_zoom = 50.0
        
        self.selection_rect = None
        self.selection_start_pos = None
        self.selection_in_progress = False
        
        self.group_drag_start_pos = None
        self.original_positions = {}
        self.dragging_group = False
        
        # Фон с сеткой
        self.grid_background = InfiniteGridBackground(10)  # Передаем размер сетки
        self.scene.addItem(self.grid_background)
        
        self.scene.setSceneRect(-1000000, -1000000, 2000000, 2000000)
        self.centerOn(0, 0)
        
        # Таймер для обновления сетки
        self.update_timer = QTimer()
        self.update_timer.setInterval(16)
        self.update_timer.timeout.connect(self.forceGridUpdate)
        self.update_timer.start()
        
        self.drawGrid = self.draw_grid

    def draw_grid(self):
        self.viewport().update()

    def forceGridUpdate(self):
        try:
            if hasattr(self, 'grid_background') and self.grid_background:
                self.grid_background.update()
        except RuntimeError:
            pass

    def wheelEvent(self, event):
        """Обработка колесика мыши - масштабирование"""
        current_scale = self.transform().m11()
        
        if event.angleDelta().y() > 0:
            factor = self.zoom_factor
        else:
            factor = 1 / self.zoom_factor
            
        new_scale = current_scale * factor
        
        if self.min_zoom <= new_scale <= self.max_zoom:
            self.scale(factor, factor)
            
            # Адаптивное изменение размера сетки в зависимости от масштаба
            if new_scale < 0.1:
                self.grid_background.grid_size = 100
            elif new_scale < 0.5:
                self.grid_background.grid_size = 50
            elif new_scale < 1.0:
                self.grid_background.grid_size = 20
            else:
                self.grid_background.grid_size = 10
            
            self.forceGridUpdate()
        
        event.accept()

    def get_selected_items(self):
        """Возвращает список выделенных элементов (компоненты, провода)"""
        selected_items = []
        for item in self.scene.selectedItems():
            if isinstance(item, (GraphicsCircuitItem, Wire)):
                try:
                    selected_items.append(item)
                except:
                    pass
        return selected_items

    def is_in_selection_area(self, pos):
        selected_items = self.get_selected_items()
        if not selected_items:
            return False
        
        selection_rect = QRectF()
        for item in selected_items:
            try:
                item_rect = item.sceneBoundingRect()
                selection_rect = selection_rect.united(item_rect)
            except:
                continue
        
        padding = 5
        selection_rect.adjust(-padding, -padding, padding, padding)
        
        return selection_rect.contains(pos)
    
    def mouseDoubleClickEvent(self, event):
        """Двойной клик - больше не создает узлы, только стандартное поведение"""
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """Обработка нажатия мыши"""
        scene_pos = self.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, self.transform())

        # Начало перемещения по сцене с помощью зажатого колесика
        if event.button() == Qt.MidButton:
            self.panning = True
            self.pan_start_pos = event.pos()
            self.pan_start_h_scroll = self.horizontalScrollBar().value()
            self.pan_start_v_scroll = self.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # Клик на проводе - начало перетаскивания для изменения формы
        if event.button() == Qt.LeftButton and isinstance(item, Wire):
            wire = item
            if wire.is_connected():
                self.dragging_wire_point = True
                self.dragged_wire = wire
                self.drag_start_pos = scene_pos
                self.temp_wire_path = wire.path()
                self.clear_highlights()
                event.accept()
                return

        if event.button() == Qt.LeftButton:
            add_to_selection = event.modifiers() & Qt.ControlModifier
            
            # Групповое перетаскивание
            selected_items = self.get_selected_items()
            if selected_items and self.is_in_selection_area(scene_pos):
                self.dragging_group = True
                self.group_drag_start_pos = scene_pos
                self.original_positions = {}
                
                for item in selected_items:
                    try:
                        if isinstance(item, GraphicsCircuitItem):
                            self.original_positions[item] = item.pos()
                    except:
                        pass
                
                self.clear_highlights()
                event.accept()
                return
            
            # Поиск цели для начала создания провода
            target_item, target_terminal = self.get_connection_target_near(scene_pos)
            
            if target_item and not self.dragging_wire:
                # Начинаем создание нового провода
                self.current_wire = Wire()
                self.scene.addItem(self.current_wire)
                
                self.current_wire.connect_to_component(target_item, target_terminal, is_start=True)
                self.wire_start_item = target_item
                self.wire_start_terminal = target_terminal
                self.wire_start_pos = target_item.get_terminal_scene_pos(target_terminal)
                
                self.dragging_wire = True
                self.clear_highlights()
                event.accept()
                return
            
            # Прямоугольное выделение
            if not item or not isinstance(item, (GraphicsCircuitItem, Wire)):
                self.selection_start_pos = scene_pos
                self.selection_rect = QGraphicsRectItem()
                self.selection_rect.setPen(QPen(QColor(100, 100, 255, 200), 1, Qt.DashLine))
                self.selection_rect.setBrush(QBrush(QColor(100, 100, 255, 50)))
                self.selection_rect.setZValue(100)
                self.selection_rect.setRect(QRectF(scene_pos, scene_pos))
                self.scene.addItem(self.selection_rect)
                self.selection_in_progress = True
                
                if not add_to_selection:
                    self.clear_selection()
                
                event.accept()
                return
            
            # Клик на элементе
            if isinstance(item, (GraphicsCircuitItem, Wire)) and not add_to_selection:
                self.clear_selection()
                item.setSelected(True)
            
            self.clear_highlights()
        
        elif event.button() == Qt.RightButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene.itemAt(scene_pos, self.transform())
            self.show_context_menu_at_position(scene_pos, item, event.globalPos())
            event.accept()
            return
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        scene_pos = self.mapToScene(event.pos())

        # Перемещение по сцене с помощью зажатого колесика
        if self.panning:
            delta = event.pos() - self.pan_start_pos
            self.horizontalScrollBar().setValue(self.pan_start_h_scroll - delta.x())
            self.verticalScrollBar().setValue(self.pan_start_v_scroll - delta.y())
            event.accept()
            return

        # Перемещение компонента
        if isinstance(self.scene.mouseGrabberItem(), GraphicsCircuitItem):
            self.clear_highlights()
            super().mouseMoveEvent(event)
            return
        
        # Перетаскивание провода для изменения формы
        if self.dragging_wire_point and self.dragged_wire and event.buttons() & Qt.LeftButton:
            if self.dragged_wire.is_connected():
                start_pos = self.dragged_wire.get_start_pos()
                end_pos = self.dragged_wire.get_end_pos()
                
                if start_pos and end_pos:
                    path = QPainterPath()
                    path.moveTo(start_pos)
                    
                    # Создаем новый путь с учетом позиции мыши
                    dx = scene_pos.x() - start_pos.x()
                    dy = scene_pos.y() - start_pos.y()
                    
                    # Ортогональная трассировка через точку перетаскивания
                    if abs(dx) > abs(dy):
                        path.lineTo(QPointF(scene_pos.x(), start_pos.y()))
                        path.lineTo(scene_pos)
                        path.lineTo(QPointF(end_pos.x(), scene_pos.y()))
                        path.lineTo(end_pos)
                    else:
                        path.lineTo(QPointF(start_pos.x(), scene_pos.y()))
                        path.lineTo(scene_pos)
                        path.lineTo(QPointF(scene_pos.x(), end_pos.y()))
                        path.lineTo(end_pos)
                    
                    local_path = self.dragged_wire.mapFromScene(path)
                    self.dragged_wire.setPath(local_path)
                    
                    event.accept()
                    return
        
        # Групповое перетаскивание
        if self.dragging_group and event.buttons() & Qt.LeftButton and self.group_drag_start_pos:
            dx = scene_pos.x() - self.group_drag_start_pos.x()
            dy = scene_pos.y() - self.group_drag_start_pos.y()
            
            grid_size = 10
            dx_grid = round(dx / grid_size) * grid_size
            dy_grid = round(dy / grid_size) * grid_size
            
            selected_items = self.get_selected_items()
            for item in selected_items:
                try:
                    if isinstance(item, GraphicsCircuitItem):
                        original_pos = self.original_positions.get(item)
                        if original_pos:
                            item.setPos(original_pos.x() + dx_grid, original_pos.y() + dy_grid)
                except:
                    pass
            return
        
        # Прямоугольное выделение
        if self.selection_in_progress and self.selection_start_pos and self.selection_rect:
            rect = QRectF(self.selection_start_pos, scene_pos).normalized()
            self.selection_rect.setRect(rect)
            
            add_to_selection = event.modifiers() & Qt.ControlModifier
            self.update_selection_in_rect(rect, add_to_selection)
            return

        # Динамическое обновление пути провода при создании
        if self.dragging_wire and self.current_wire:
            target_item, target_terminal = self.get_connection_target_near(scene_pos)
            
            if target_item:
                target_pos = target_item.get_terminal_scene_pos(target_terminal)
                self.show_target_highlight(target_item, target_terminal)
            else:
                target_pos = scene_pos
                self.clear_highlights()
            
            path = QPainterPath()
            path.moveTo(self.wire_start_pos)
            
            dx = target_pos.x() - self.wire_start_pos.x()
            dy = target_pos.y() - self.wire_start_pos.y()
            
            if abs(dx) > abs(dy):
                mid_x = target_pos.x()
                path.lineTo(QPointF(mid_x, self.wire_start_pos.y()))
                path.lineTo(target_pos)
            else:
                mid_y = target_pos.y()
                path.lineTo(QPointF(self.wire_start_pos.x(), mid_y))
                path.lineTo(target_pos)
            
            local_path = self.current_wire.mapFromScene(path)
            self.current_wire.setPath(local_path)
            
            return

        # Подсветка терминалов (только если ничего не перетаскивается)
        if (not self.dragging_wire and not self.selection_in_progress and 
            not self.dragging_group and not isinstance(self.scene.mouseGrabberItem(), GraphicsCircuitItem) and
            not self.panning):
            target_item, target_terminal = self.get_connection_target_near(scene_pos)
            if target_item:
                self.show_target_highlight(target_item, target_terminal)
            else:
                self.clear_highlights()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши"""
        scene_pos = self.mapToScene(event.pos())

        # Завершение перемещения с помощью колесика
        if event.button() == Qt.MidButton:
            self.panning = False
            self.pan_start_pos = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            # Завершение перетаскивания провода - СОХРАНЯЕМ новую форму
            if self.dragging_wire_point and self.dragged_wire:
                if self.dragged_wire.is_connected():
                    if self.drag_start_pos and (scene_pos - self.drag_start_pos).manhattanLength() > 5:
                        # Провод уже имеет новую форму - сохраняем в команду
                        # Создаем команду для изменения формы провода
                        from commands import ModifyWireCommand
                        command = ModifyWireCommand(
                            self.scene, 
                            self.dragged_wire, 
                            self.temp_wire_path, 
                            self.dragged_wire.path()
                        )
                        self.undo_stack.push(command)
                    else:
                        if self.temp_wire_path:
                            self.dragged_wire.setPath(self.temp_wire_path)
                
                self.dragging_wire_point = False
                self.dragged_wire = None
                self.drag_start_pos = None
                self.drag_offset = None
                self.temp_wire_path = None
                self.clear_highlights()
                event.accept()
                return
            
            # Завершение создания провода
            if self.dragging_wire and self.current_wire:
                target_item, target_terminal = self.get_connection_target_near(scene_pos)
                
                if target_item:
                    is_self_connection = False
                    
                    if (self.wire_start_item == target_item and 
                        self.wire_start_terminal == target_terminal):
                        is_self_connection = True
                    
                    if not is_self_connection:
                        # Подключаем конец провода
                        self.current_wire.connect_to_component(target_item, target_terminal, is_start=False)
                        
                        self.current_wire.update_path()
                        
                        # Добавляем команду в стек отмены
                        from commands import AddWireCommand
                        command = AddWireCommand(self.scene, self.current_wire)
                        self.undo_stack.push(command)
                    else:
                        self.current_wire.remove()
                else:
                    self.current_wire.remove()
                
                self.dragging_wire = False
                self.current_wire = None
                self.wire_start_pos = None
                self.wire_start_item = None
                self.wire_start_terminal = None
                self.clear_highlights()
                event.accept()
                return
            
            # Завершение группового перетаскивания
            if self.dragging_group:
                # Создаем команду для перемещения группы
                selected_items = self.get_selected_items()
                old_positions = {}
                new_positions = {}
                
                for item in selected_items:
                    if isinstance(item, GraphicsCircuitItem):
                        old_pos = self.original_positions.get(item)
                        if old_pos:
                            old_positions[item] = old_pos
                            new_positions[item] = item.pos()
                
                if old_positions and new_positions:
                    from commands import MoveItemsCommand
                    command = MoveItemsCommand(self.scene, selected_items, old_positions, new_positions)
                    self.undo_stack.push(command)
                
                self.dragging_group = False
                self.group_drag_start_pos = None
                self.original_positions.clear()
                event.accept()
                return
            
            # Завершение прямоугольного выделения
            if self.selection_in_progress:
                self.selection_in_progress = False
                if self.selection_rect:
                    self.scene.removeItem(self.selection_rect)
                    self.selection_rect = None
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def update_selection_in_rect(self, rect, add_to_selection=False):
        if not add_to_selection:
            self.clear_selection()
        
        for item in self.scene.items(rect):
            if isinstance(item, (GraphicsCircuitItem, Wire)):
                item.setSelected(True)

    def clear_selection(self):
        for item in self.scene.selectedItems():
            try:
                item.setSelected(False)
            except:
                pass

    def get_connection_target_near(self, scene_pos):
        """
        Поиск ближайшей цели для подключения провода.
        Возвращает (компонент, позиция_терминала)
        """
        # Ищем терминалы компонентов
        for item in self.scene.items():
            if isinstance(item, GraphicsCircuitItem):
                terminals = item.get_terminals()
                item_pos = item.mapFromScene(scene_pos)
                
                for (x, y), label in terminals.items():
                    terminal_point = QPointF(x, y)
                    distance = (item_pos - terminal_point).manhattanLength()
                    
                    if distance < self.snap_threshold:
                        return item, (x, y)
        
        return None, None

    def show_target_highlight(self, target_item, terminal):
        """Подсветка цели для подключения"""
        self.clear_highlights()
        
        if isinstance(target_item, GraphicsCircuitItem):
            scene_pos = target_item.get_terminal_scene_pos(terminal)
            highlight = self.scene.addEllipse(
                scene_pos.x() - 10, scene_pos.y() - 10, 20, 20,
                QPen(QColor(0, 255, 0, 200), 2),
                QBrush(QColor(0, 255, 0, 80))
            )
            highlight.setZValue(10)
            self.highlight_items.append(highlight)

    def clear_highlights(self):
        """Очистка всех подсветок"""
        for item in self.highlight_items[:]:
            if item and item.scene():
                try:
                    item.scene().removeItem(item)
                except:
                    pass
        self.highlight_items.clear()

    def show_context_menu_at_position(self, scene_pos, item, global_pos):
        """Показать контекстное меню"""
        
        if isinstance(item, GraphicsCircuitItem):
            menu = QMenu()
            properties_action = menu.addAction("Свойства")
            rotate_cw_action = menu.addAction("Повернуть на 90° по часовой")
            rotate_ccw_action = menu.addAction("Повернуть на 90° против часовой")
            flip_action = menu.addAction("Отразить горизонтально")
            delete_action = menu.addAction("Удалить")
            
            action = menu.exec_(global_pos)

            if action == properties_action:
                old_props = item.properties.copy()
                item.show_properties_dialog()
                new_props = item.properties.copy()
                
                if old_props != new_props:
                    from commands import ChangePropertiesCommand
                    command = ChangePropertiesCommand(self.scene, item, old_props, new_props)
                    self.undo_stack.push(command)
                    
            elif action == rotate_cw_action:
                old_angle = item.rotation_angle
                item.rotate_clockwise()
                new_angle = item.rotation_angle
                
                from commands import RotateComponentCommand
                command = RotateComponentCommand(self.scene, item, old_angle, new_angle)
                self.undo_stack.push(command)
                
            elif action == rotate_ccw_action:
                old_angle = item.rotation_angle
                item.rotate_counterclockwise()
                new_angle = item.rotation_angle
                
                from commands import RotateComponentCommand
                command = RotateComponentCommand(self.scene, item, old_angle, new_angle)
                self.undo_stack.push(command)
                
            elif action == flip_action:
                old_flipped = item.is_flipped
                item.flip_horizontal()
                new_flipped = item.is_flipped
                
                from commands import FlipComponentCommand
                command = FlipComponentCommand(self.scene, item, old_flipped, new_flipped)
                self.undo_stack.push(command)
                
            elif action == delete_action:
                from commands import RemoveComponentCommand
                command = RemoveComponentCommand(self.scene, item)
                self.undo_stack.push(command)
            return
                
        elif isinstance(item, Wire):
            menu = QMenu()
            delete_action = QAction("Удалить провод", self)
            delete_action.triggered.connect(
                lambda: self._remove_wire(item)
            )
            menu.addAction(delete_action)
            menu.exec_(global_pos)
            return
        
        # Меню для группы выделенных элементов
        selected_items = self.get_selected_items()
        if selected_items:
            menu = QMenu()
            duplicate_action = QAction("Дублировать", self)
            duplicate_action.triggered.connect(self.duplicate_selected_items)
            delete_action = QAction("Удалить", self)
            delete_action.triggered.connect(self.delete_selected_items)
            clear_action = QAction("Снять выделение", self)
            clear_action.triggered.connect(self.clear_selection)
            
            menu.addAction(duplicate_action)
            menu.addAction(delete_action)
            menu.addSeparator()
            menu.addAction(clear_action)
            
            menu.exec_(global_pos)
            return
        
        # Меню добавления компонентов
        menu = QMenu("Добавить компонент")
        components = [
            ("Resistor", "Резистор"), 
            ("Capacitor", "Конденсатор"), 
            ("Inductor", "Катушка индуктивности"),
            ("Voltage Source", "Источник напряжения"),
            ("Switch", "Рубильник"),
            ("Ground", "Земля")
        ]

        for component_type, component_name in components:
            action = QAction(component_name)
            action.component_type = component_type
            action.position = scene_pos
            action.triggered.connect(
                lambda checked, act=action: self.add_component_at_position(act.component_type, act.position)
            )
            menu.addAction(action)

        menu.exec_(global_pos)

    def _remove_wire(self, wire):
        """Удаление провода с командой отмены"""
        from commands import RemoveWireCommand
        command = RemoveWireCommand(self.scene, wire)
        self.undo_stack.push(command)

    def add_component_at_position(self, component_type, pos):
        """Добавление компонента в указанную позицию"""
        grid_size = self.grid_background.grid_size
        x = round(pos.x() / grid_size) * grid_size
        y = round(pos.y() / grid_size) * grid_size

        element = GraphicsCircuitItem(component_type, x, y)
        self.scene.addItem(element)
        
        # Добавляем команду в стек отмены
        from commands import AddComponentCommand
        command = AddComponentCommand(self.scene, element, QPointF(x, y))
        self.undo_stack.push(command)

    def contextMenuEvent(self, event):
        pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
            element_type = event.mimeData().text()
            self.preview_element = ComponentPreview(element_type)
            self.scene.addItem(self.preview_element)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if hasattr(self, 'preview_element') and self.preview_element:
            pos = self.mapToScene(event.pos())
            grid_size = self.grid_background.grid_size
            x = round(pos.x() / grid_size) * grid_size
            y = round(pos.y() / grid_size) * grid_size
            self.preview_element.setPos(x, y)
            event.accept()

    def dragLeaveEvent(self, event):
        if hasattr(self, 'preview_element') and self.preview_element:
            self.scene.removeItem(self.preview_element)
            self.preview_element = None
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            pos = self.mapToScene(event.pos())
            grid_size = self.grid_background.grid_size
            x = round(pos.x() / grid_size) * grid_size
            y = round(pos.y() / grid_size) * grid_size

            element_type = event.mimeData().text()
            element = GraphicsCircuitItem(element_type, x, y)
            self.scene.addItem(element)
            
            # Добавляем команду в стек отмены
            from commands import AddComponentCommand
            command = AddComponentCommand(self.scene, element, QPointF(x, y))
            self.undo_stack.push(command)

            if hasattr(self, 'preview_element') and self.preview_element:
                self.scene.removeItem(self.preview_element)
                self.preview_element = None

            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_0 and event.modifiers() & Qt.ControlModifier:
            self.resetTransform()
            self.grid_background.grid_size = 10
            self.forceGridUpdate()
        elif event.key() == Qt.Key_G:
            if self.grid_background.isVisible():
                self.grid_background.hide()
            else:
                self.grid_background.show()
        elif event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.delete_selected_items()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            # Отмена создания провода или перетаскивания
            self.dragging_wire = False
            if self.current_wire:
                self.current_wire.remove()
                self.current_wire = None
            self.dragging_wire_point = False
            if self.dragged_wire:
                if self.temp_wire_path:
                    self.dragged_wire.setPath(self.temp_wire_path)
                self.dragged_wire = None
            self.wire_start_pos = None
            self.wire_start_item = None
            self.wire_start_terminal = None
            self.drag_start_pos = None
            self.drag_offset = None
            self.temp_wire_path = None
            self.clear_highlights()
            if self.panning:
                self.panning = False
                self.pan_start_pos = None
                self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().keyPressEvent(event)

    def delete_selected_items(self):
        """Удаление выделенных элементов с командой отмены"""
        selected_items = self.get_selected_items()
        
        if not selected_items:
            return
        
        # Создаем макрокоманду для удаления группы
        class DeleteItemsCommand(QUndoCommand):
            def __init__(self, scene, items):
                super().__init__(f"Удаление {len(items)} элементов")
                self.scene = scene
                self.item_commands = []
                
                # Создаем команды удаления для каждого элемента
                for item in items:
                    try:
                        if hasattr(item, 'element_type'):
                            from commands import RemoveComponentCommand
                            cmd = RemoveComponentCommand(scene, item)
                        elif isinstance(item, Wire):
                            from commands import RemoveWireCommand
                            cmd = RemoveWireCommand(scene, item)
                        else:
                            continue
                        self.item_commands.append(cmd)
                    except:
                        continue
            
            def redo(self):
                for cmd in self.item_commands:
                    try:
                        cmd.redo()
                    except:
                        pass
            
            def undo(self):
                for cmd in reversed(self.item_commands):
                    try:
                        cmd.undo()
                    except:
                        pass
        
        command = DeleteItemsCommand(self.scene, selected_items)
        self.undo_stack.push(command)
        
        self.clear_selection()

    def duplicate_selected_items(self):
        """Дублирование выделенных элементов"""
        selected_items = self.get_selected_items()
        
        if not selected_items:
            return
        
        # Находим границы выделения
        min_x = float('inf')
        min_y = float('inf')
        for item in selected_items:
            try:
                rect = item.sceneBoundingRect()
                min_x = min(min_x, rect.x())
                min_y = min(min_y, rect.y())
            except:
                continue
        
        offset_x = 50
        offset_y = 50
        
        # Создаем макрокоманду для дублирования
        class DuplicateItemsCommand(QUndoCommand):
            def __init__(self, scene, items, offset):
                super().__init__(f"Дублирование {len(items)} элементов")
                self.scene = scene
                self.items = items
                self.offset = offset
                self.element_copies = {}
                self.wire_commands = []
                self.first_redo = True
            
            def redo(self):
                if self.first_redo:
                    # Копируем компоненты
                    for item in self.items:
                        if isinstance(item, GraphicsCircuitItem):
                            try:
                                new_item = GraphicsCircuitItem(
                                    item.element_type,
                                    item.x() + self.offset.x(),
                                    item.y() + self.offset.y()
                                )
                                new_item.properties = item.properties.copy()
                                
                                # Правильное восстановление трансформаций
                                new_item.rotation_angle = item.rotation_angle
                                new_item.is_flipped = item.is_flipped
                                
                                # Применяем трансформации в правильном порядке
                                transform = QTransform()
                                transform.rotate(new_item.rotation_angle)
                                if new_item.is_flipped:
                                    transform.scale(-1, 1)
                                new_item.setTransform(transform)
                                
                                self.scene.addItem(new_item)
                                self.element_copies[item] = new_item
                            except:
                                continue
                    
                    # Копируем провода
                    for item in self.items:
                        if isinstance(item, Wire):
                            try:
                                new_wire = Wire()
                                
                                if item.start_item and item.start_item in self.element_copies:
                                    new_wire.connect_to_component(
                                        self.element_copies[item.start_item],
                                        item.start_terminal,
                                        is_start=True
                                    )
                                
                                if item.end_item and item.end_item in self.element_copies:
                                    new_wire.connect_to_component(
                                        self.element_copies[item.end_item],
                                        item.end_terminal,
                                        is_start=False
                                    )
                                
                                self.scene.addItem(new_wire)
                                new_wire.update_path()
                                self.wire_commands.append(new_wire)
                            except:
                                continue
                    
                    self.first_redo = False
                else:
                    # Восстанавливаем все элементы
                    for cmd in self.element_copies.values():
                        self.scene.addItem(cmd)
                    for wire in self.wire_commands:
                        self.scene.addItem(wire)
                        wire.update_path()
            
            def undo(self):
                # Удаляем все созданные элементы
                for wire in self.wire_commands:
                    if wire and wire.scene():
                        try:
                            wire.remove()
                        except:
                            pass
                for elem in self.element_copies.values():
                    if elem and elem.scene():
                        try:
                            elem.remove()
                        except:
                            pass
        
        offset = QPointF(offset_x, offset_y)
        command = DuplicateItemsCommand(self.scene, selected_items, offset)
        self.undo_stack.push(command)
        
        # Снимаем выделение со старых элементов и выделяем новые
        self.clear_selection()
        if hasattr(command, 'element_copies'):
            for new_item in command.element_copies.values():
                new_item.setSelected(True)