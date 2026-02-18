"""
Модуль с классами команд для системы отмены действий (Undo/Redo).
Реализует паттерн Command для операций над схемой.
"""

from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QUndoCommand
from PyQt5.QtGui import QTransform, QPainterPath
import weakref


class BaseCommand(QUndoCommand):
    """Базовый класс для всех команд системы отмены"""
    
    def __init__(self, description, scene):
        super().__init__(description)
        self.scene = scene
        self.first_redo = True
    
    def mergeWith(self, other):
        return False
    
    def is_item_valid(self, item):
        """Проверка, существует ли еще объект и находится ли он в сцене"""
        try:
            return item is not None and item.scene() is not None
        except RuntimeError:
            return False


class ClearSceneCommand(BaseCommand):
    """Команда очистки всей схемы"""
    
    def __init__(self, scene):
        super().__init__("Очистка схемы", scene)
        
        # Сохраняем все элементы схемы перед очисткой
        self.saved_data = self._save_complete_scene_data()
        self.grid_size = 10
        
        # Сохраняем размер сетки
        views = scene.views()
        if views:
            view = views[0]
            if hasattr(view, 'grid_background'):
                self.grid_size = view.grid_background.grid_size
    
    def _save_complete_scene_data(self):
        """Сохранение полного состояния схемы"""
        data = {
            "elements": [],
            "wires": []
        }
        
        # Сохраняем компоненты
        for item in self.scene.items():
            if hasattr(item, 'element_type'):
                element_data = {
                    'element_type': item.element_type,
                    'pos': item.pos(),
                    'properties': item.properties.copy() if hasattr(item, 'properties') else {},
                    'rotation_angle': getattr(item, 'rotation_angle', 0),
                    'is_flipped': getattr(item, 'is_flipped', False),
                    'transform': item.transform()
                }
                data["elements"].append(element_data)
        
        # Сохраняем провода
        from wire import Wire
        for item in self.scene.items():
            if isinstance(item, Wire):
                wire_data = self._save_complete_wire_data(item)
                if wire_data:
                    data["wires"].append(wire_data)
        
        return data
    
    def _save_complete_wire_data(self, wire):
        """Сохранение полных данных о проводе"""
        if not wire.is_connected():
            return None
        
        wire_data = {
            'start_component_id': id(wire.start_item),
            'start_component_pos': wire.start_item.pos() if wire.start_item else None,
            'start_terminal': wire.start_terminal,
            'end_component_id': id(wire.end_item),
            'end_component_pos': wire.end_item.pos() if wire.end_item else None,
            'end_terminal': wire.end_terminal,
            'path': self._save_path(wire.path()) if hasattr(wire, 'saved_path') and wire.saved_path else None
        }
        
        return wire_data
    
    def _save_path(self, path):
        """Сохранение пути провода"""
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
    
    def redo(self):
        """Выполнение очистки схемы"""
        views = self.scene.views()
        view = views[0] if views else None
        if view and hasattr(view, 'update_timer'):
            view.update_timer.stop()
        
        self.scene.clear()
        
        if view and hasattr(view, 'grid_background'):
            from canvas import InfiniteGridBackground
            view.grid_background = InfiniteGridBackground(self.grid_size)
            self.scene.addItem(view.grid_background)
        
        if view and hasattr(view, 'update_timer'):
            view.update_timer.start()
    
    def undo(self):
        """Отмена очистки - восстановление схемы"""
        from circuit_elements import GraphicsCircuitItem
        from wire import Wire
        
        views = self.scene.views()
        view = views[0] if views else None
        if view and hasattr(view, 'update_timer'):
            view.update_timer.stop()
        
        self.scene.clear()
        
        if view and hasattr(view, 'grid_background'):
            from canvas import InfiniteGridBackground
            view.grid_background = InfiniteGridBackground(self.grid_size)
            self.scene.addItem(view.grid_background)
        
        # Восстанавливаем компоненты
        component_map = {}
        for element_data in self.saved_data["elements"]:
            component = GraphicsCircuitItem(
                element_data['element_type'],
                element_data['pos'].x(),
                element_data['pos'].y()
            )
            
            if hasattr(component, 'properties'):
                component.properties = element_data['properties'].copy()
            
            if hasattr(component, 'rotation_angle'):
                component.rotation_angle = element_data['rotation_angle']
            
            if hasattr(component, 'is_flipped'):
                component.is_flipped = element_data['is_flipped']
            
            if 'transform' in element_data:
                component.setTransform(element_data['transform'])
            
            self.scene.addItem(component)
            component_map[id(component)] = component
        
        # Восстанавливаем провода
        for wire_data in self.saved_data["wires"]:
            # Создаем провод с восстановлением пути
            wire = Wire()
            
            # Восстанавливаем путь, если он был сохранен
            if wire_data.get('path'):
                path = QPainterPath()
                for elem in wire_data['path']['elements']:
                    if elem['type'] == 'move':
                        path.moveTo(elem['x'], elem['y'])
                    elif elem['type'] == 'line':
                        path.lineTo(elem['x'], elem['y'])
                wire.setPath(path)
                wire.saved_path = path
            
            # Восстанавливаем начало
            start_component = None
            for comp in component_map.values():
                if comp.pos() == wire_data['start_component_pos']:
                    start_component = comp
                    break
            
            if start_component:
                wire.connect_to_component(
                    start_component,
                    wire_data['start_terminal'],
                    is_start=True
                )
            
            # Восстанавливаем конец
            end_component = None
            for comp in component_map.values():
                if comp.pos() == wire_data['end_component_pos']:
                    end_component = comp
                    break
            
            if end_component:
                wire.connect_to_component(
                    end_component,
                    wire_data['end_terminal'],
                    is_start=False
                )
            
            if wire.is_connected():
                self.scene.addItem(wire)
        
        # Перезапускаем таймер
        if view and hasattr(view, 'update_timer'):
            view.update_timer.start()
        
        if view:
            view.viewport().update()


class MoveItemsCommand(BaseCommand):
    """Команда перемещения группы элементов"""
    
    def __init__(self, scene, items, old_positions, new_positions):
        super().__init__("Перемещение элементов", scene)
        # Сохраняем ссылки через weakref и копируем позиции
        self.item_refs = {}
        self.old_positions = {}
        self.new_positions = {}
        
        # Сохраняем для каждого элемента его старую и новую позицию
        for item, pos in old_positions.items():
            if item and self.is_item_valid(item):
                item_id = id(item)
                self.item_refs[item_id] = weakref.ref(item)
                self.old_positions[item_id] = QPointF(pos)  # Копируем позицию
        
        for item, pos in new_positions.items():
            if item and self.is_item_valid(item):
                item_id = id(item)
                self.new_positions[item_id] = QPointF(pos)  # Копируем позицию
    
    def _apply_positions(self, positions_dict):
        """Применить позиции из словаря"""
        for item_id, pos in positions_dict.items():
            item_ref = self.item_refs.get(item_id)
            if item_ref:
                item = item_ref()
                # ИСПРАВЛЕНИЕ: Улучшенная проверка валидности элемента
                if item and self.is_item_valid(item):
                    try:
                        # Устанавливаем позицию
                        item.setPos(pos)
                        if hasattr(item, 'update_connected_wires'):
                            item.update_connected_wires()
                        elif hasattr(item, 'wires'):
                            for wire in item.wires[:]:
                                if wire and wire.scene():
                                    wire.update_path()
                    except RuntimeError:
                        pass
    
    def redo(self):
        """Применить перемещение"""
        self._apply_positions(self.new_positions)
    
    def undo(self):
        """Отменить перемещение"""
        self._apply_positions(self.old_positions)


class ModifyWireCommand(BaseCommand):
    """Команда изменения формы провода"""
    
    def __init__(self, scene, wire, old_path, new_path):
        super().__init__("Изменение формы провода", scene)
        self.wire_ref = weakref.ref(wire)
        self.old_path_data = self._save_path(old_path)
        self.new_path_data = self._save_path(new_path)
        
        # Сохраняем информацию о подключениях для проверки
        if wire and self.is_item_valid(wire):
            self.start_item_ref = weakref.ref(wire.start_item) if wire.start_item else None
            self.start_terminal = wire.start_terminal
            self.end_item_ref = weakref.ref(wire.end_item) if wire.end_item else None
            self.end_terminal = wire.end_terminal
    
    def _save_path(self, path):
        """Сохранение пути в данные"""
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
    
    def _restore_path(self, path_data):
        """Восстановление пути из данных"""
        if not path_data:
            return QPainterPath()
        
        path = QPainterPath()
        for elem in path_data['elements']:
            if elem['type'] == 'move':
                path.moveTo(elem['x'], elem['y'])
            elif elem['type'] == 'line':
                path.lineTo(elem['x'], elem['y'])
        
        return path
    
    def _ensure_connections(self, wire):
        """Проверка и восстановление подключений провода"""
        if not wire or not self.is_item_valid(wire):
            return False
        
        # Проверяем начало провода
        if self.start_item_ref:
            start_item = self.start_item_ref()
            if start_item and self.is_item_valid(start_item):
                if wire.start_item != start_item or wire.start_terminal != self.start_terminal:
                    wire.connect_to_component(start_item, self.start_terminal, is_start=True)
            else:
                return False
        
        # Проверяем конец провода
        if self.end_item_ref:
            end_item = self.end_item_ref()
            if end_item and self.is_item_valid(end_item):
                if wire.end_item != end_item or wire.end_terminal != self.end_terminal:
                    wire.connect_to_component(end_item, self.end_terminal, is_start=False)
            else:
                return False
        
        return wire.is_connected()
    
    def redo(self):
        """Применить изменение формы"""
        wire = self.wire_ref()
        if wire and self.is_item_valid(wire):
            # Проверяем и восстанавливаем подключения
            if not self._ensure_connections(wire):
                return
            
            new_path = self._restore_path(self.new_path_data)
            
            # Преобразуем путь в локальные координаты провода
            if not new_path.isEmpty():
                # Получаем начальную и конечную точки в координатах сцены
                start_scene = wire.get_start_pos()
                end_scene = wire.get_end_pos()
                
                if start_scene and end_scene:
                    # Создаем новый путь с учетом текущих позиций компонентов
                    updated_path = QPainterPath()
                    updated_path.moveTo(start_scene)
                    
                    # Копируем промежуточные точки из сохраненного пути
                    for i in range(1, new_path.elementCount()):
                        elem = new_path.elementAt(i)
                        if elem.isLineTo():
                            updated_path.lineTo(QPointF(elem.x, elem.y))
                    
                    # Убеждаемся, что путь заканчивается в правильной точке
                    if updated_path.elementCount() > 0:
                        last_elem = updated_path.elementAt(updated_path.elementCount() - 1)
                        last_point = QPointF(last_elem.x, last_elem.y)
                        if (last_point - end_scene).manhattanLength() > 1:
                            updated_path.lineTo(end_scene)
                    
                    # Преобразуем в локальные координаты
                    local_path = wire.mapFromScene(updated_path)
                    wire.setPath(local_path)
                    wire.saved_path = local_path
                else:
                    wire.setPath(new_path)
                    wire.saved_path = new_path
            
            wire.update()
    
    def undo(self):
        """Отменить изменение формы"""
        wire = self.wire_ref()
        if wire and self.is_item_valid(wire):
            # Проверяем и восстанавливаем подключения
            if not self._ensure_connections(wire):
                return
            
            old_path = self._restore_path(self.old_path_data)
            
            # Преобразуем путь в локальные координаты провода
            if not old_path.isEmpty():
                # Получаем начальную и конечную точки в координатах сцены
                start_scene = wire.get_start_pos()
                end_scene = wire.get_end_pos()
                
                if start_scene and end_scene:
                    # Создаем старый путь с учетом текущих позиций компонентов
                    updated_path = QPainterPath()
                    updated_path.moveTo(start_scene)
                    
                    # Копируем промежуточные точки из сохраненного пути
                    for i in range(1, old_path.elementCount()):
                        elem = old_path.elementAt(i)
                        if elem.isLineTo():
                            updated_path.lineTo(QPointF(elem.x, elem.y))
                    
                    # Убеждаемся, что путь заканчивается в правильной точке
                    if updated_path.elementCount() > 0:
                        last_elem = updated_path.elementAt(updated_path.elementCount() - 1)
                        last_point = QPointF(last_elem.x, last_elem.y)
                        if (last_point - end_scene).manhattanLength() > 1:
                            updated_path.lineTo(end_scene)
                    
                    # Преобразуем в локальные координаты
                    local_path = wire.mapFromScene(updated_path)
                    wire.setPath(local_path)
                    wire.saved_path = local_path
                else:
                    wire.setPath(old_path)
                    wire.saved_path = old_path
            
            wire.update()


class AddComponentCommand(BaseCommand):
    """Команда добавления компонента на схему"""
    
    def __init__(self, scene, component, pos):
        super().__init__(f"Добавление {component.element_type}", scene)
        self.component_ref = weakref.ref(component)
        self.pos = QPointF(pos)  # Копируем позицию
        self.element_type = component.element_type
        self.properties = component.properties.copy() if hasattr(component, 'properties') else {}
        self.rotation_angle = getattr(component, 'rotation_angle', 0)
        self.is_flipped = getattr(component, 'is_flipped', False)
        self.transform = component.transform()
    
    def redo(self):
        if self.first_redo:
            self.first_redo = False
        else:
            from circuit_elements import GraphicsCircuitItem
            component = GraphicsCircuitItem(
                self.element_type,
                self.pos.x(),
                self.pos.y()
            )
            self.component_ref = weakref.ref(component)
            
            if hasattr(component, 'properties'):
                component.properties = self.properties.copy()
            
            if hasattr(component, 'rotation_angle'):
                component.rotation_angle = self.rotation_angle
            
            if hasattr(component, 'is_flipped'):
                component.is_flipped = self.is_flipped
            
            component.setTransform(self.transform)
            
            self.scene.addItem(component)
    
    def undo(self):
        component = self.component_ref()
        if component and self.is_item_valid(component):
            component.remove()


class RemoveComponentCommand(BaseCommand):
    """Команда удаления компонента со схемы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, scene, component):
        super().__init__(f"Удаление {component.element_type}", scene)
        
        self.component_ref = weakref.ref(component)
        
        # Сохраняем ВСЕ данные компонента
        self.component_id = id(component)
        self.element_type = component.element_type
        self.pos = QPointF(component.pos())  # Копируем позицию
        self.properties = component.properties.copy() if hasattr(component, 'properties') else {}
        self.rotation_angle = getattr(component, 'rotation_angle', 0)
        self.is_flipped = getattr(component, 'is_flipped', False)
        self.transform = component.transform()
        
        # Сохраняем подключенные провода с полной информацией о терминалах
        self.connected_wires_data = []
        if hasattr(component, 'wires'):
            wires_copy = component.wires[:]
            for wire in wires_copy:
                if wire and wire.scene():
                    wire_data = self._save_complete_wire_data(wire, component)
                    self.connected_wires_data.append(wire_data)
    
    def _save_complete_wire_data(self, wire, this_component):
        """Сохранение полных данных о проводе с информацией о терминалах"""
        wire_data = {
            'is_start_this_component': False,
            'is_end_this_component': False,
            'this_terminal': None,  # Терминал на удаляемом компоненте
            'other_component_id': None,
            'other_component_pos': None,
            'other_terminal': None,  # Терминал на другом компоненте
            'path': self._save_path(wire.path()) if hasattr(wire, 'saved_path') and wire.saved_path else None
        }
        
        if wire.start_item == this_component:
            wire_data['is_start_this_component'] = True
            wire_data['this_terminal'] = wire.start_terminal  # Сохраняем терминал удаляемого компонента
            wire_data['other_component_id'] = id(wire.end_item) if wire.end_item else None
            wire_data['other_component_pos'] = wire.end_item.pos() if wire.end_item else None
            wire_data['other_terminal'] = wire.end_terminal  # Сохраняем терминал другого компонента
        elif wire.end_item == this_component:
            wire_data['is_end_this_component'] = True
            wire_data['this_terminal'] = wire.end_terminal  # Сохраняем терминал удаляемого компонента
            wire_data['other_component_id'] = id(wire.start_item) if wire.start_item else None
            wire_data['other_component_pos'] = wire.start_item.pos() if wire.start_item else None
            wire_data['other_terminal'] = wire.start_terminal  # Сохраняем терминал другого компонента
        
        return wire_data
    
    def _save_path(self, path):
        """Сохранение пути провода"""
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
    
    def redo(self):
        """Выполнение удаления"""
        component = self.component_ref()
        if component and self.is_item_valid(component):
            component.remove()
    
    def undo(self):
        """Отмена удаления - восстанавливаем компонент и провода"""
        from circuit_elements import GraphicsCircuitItem
        from wire import Wire
        
        # Восстанавливаем компонент
        component = GraphicsCircuitItem(self.element_type, self.pos.x(), self.pos.y())
        self.component_ref = weakref.ref(component)
        component.properties = self.properties.copy()
        
        if hasattr(component, 'rotation_angle'):
            component.rotation_angle = self.rotation_angle
        
        if hasattr(component, 'is_flipped'):
            component.is_flipped = self.is_flipped
        
        component.setTransform(self.transform)
        
        self.scene.addItem(component)
        
        # Восстанавливаем провода
        for wire_data in self.connected_wires_data:
            wire = Wire()
            
            # Восстанавливаем путь
            if wire_data.get('path'):
                path = QPainterPath()
                for elem in wire_data['path']['elements']:
                    if elem['type'] == 'move':
                        path.moveTo(elem['x'], elem['y'])
                    elif elem['type'] == 'line':
                        path.lineTo(elem['x'], elem['y'])
                wire.setPath(path)
                wire.saved_path = path
            
            # Ищем другой компонент по позиции
            other_component = None
            for item in self.scene.items():
                if hasattr(item, 'element_type') and item.pos() == wire_data.get('other_component_pos'):
                    other_component = item
                    break
            
            if other_component:
                # Восстанавливаем подключения с правильными терминалами
                if wire_data['is_start_this_component']:
                    # Провод начинался на удаленном компоненте
                    wire.connect_to_component(component, wire_data['this_terminal'], is_start=True)
                    wire.connect_to_component(other_component, wire_data['other_terminal'], is_start=False)
                else:
                    # Провод заканчивался на удаленном компоненте
                    wire.connect_to_component(other_component, wire_data['other_terminal'], is_start=True)
                    wire.connect_to_component(component, wire_data['this_terminal'], is_start=False)
                
                if wire.is_connected():
                    self.scene.addItem(wire)
                    wire.update_path()


class AddWireCommand(BaseCommand):
    """Команда добавления провода"""
    
    def __init__(self, scene, wire):
        super().__init__("Добавление провода", scene)
        self.wire_data = self._save_complete_wire_data(wire)
        self.wire_ref = weakref.ref(wire)
    
    def _save_complete_wire_data(self, wire):
        """Сохранение полных данных о проводе"""
        if not wire.is_connected():
            return None
        
        wire_data = {
            'start_component_id': id(wire.start_item) if wire.start_item else None,
            'start_component_pos': wire.start_item.pos() if wire.start_item else None,
            'start_terminal': wire.start_terminal,
            'end_component_id': id(wire.end_item) if wire.end_item else None,
            'end_component_pos': wire.end_item.pos() if wire.end_item else None,
            'end_terminal': wire.end_terminal,
            'path': self._save_path(wire.path()) if hasattr(wire, 'saved_path') and wire.saved_path else None
        }
        
        return wire_data
    
    def _save_path(self, path):
        """Сохранение пути провода"""
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
    
    def redo(self):
        if self.first_redo:
            self.first_redo = False
        else:
            from wire import Wire
            
            wire = Wire()
            self.wire_ref = weakref.ref(wire)
            wire_restored = False
            
            # Восстанавливаем путь
            if self.wire_data and self.wire_data.get('path'):
                path = QPainterPath()
                for elem in self.wire_data['path']['elements']:
                    if elem['type'] == 'move':
                        path.moveTo(elem['x'], elem['y'])
                    elif elem['type'] == 'line':
                        path.lineTo(elem['x'], elem['y'])
                wire.setPath(path)
                wire.saved_path = path
            
            # Восстанавливаем начало
            start_component = None
            for item in self.scene.items():
                if hasattr(item, 'element_type') and item.pos() == self.wire_data['start_component_pos']:
                    start_component = item
                    break
            
            if start_component:
                wire.connect_to_component(
                    start_component,
                    self.wire_data['start_terminal'],
                    is_start=True
                )
                wire_restored = True
            
            # Восстанавливаем конец
            end_component = None
            for item in self.scene.items():
                if hasattr(item, 'element_type') and item.pos() == self.wire_data['end_component_pos']:
                    end_component = item
                    break
            
            if end_component:
                wire.connect_to_component(
                    end_component,
                    self.wire_data['end_terminal'],
                    is_start=False
                )
                wire_restored = True
            
            if wire_restored and wire.is_connected():
                self.scene.addItem(wire)
                wire.update_path()
            else:
                wire.remove()
    
    def undo(self):
        wire = self.wire_ref()
        if wire and self.is_item_valid(wire):
            wire.remove()


class RemoveWireCommand(BaseCommand):
    """Команда удаления провода"""
    
    def __init__(self, scene, wire):
        super().__init__("Удаление провода", scene)
        
        self.wire_ref = weakref.ref(wire)
        self.wire_data = self._save_complete_wire_data(wire)
    
    def _save_complete_wire_data(self, wire):
        """Сохранение полных данных о проводе"""
        if not wire.is_connected():
            return None
        
        wire_data = {
            'start_component_id': id(wire.start_item) if wire.start_item else None,
            'start_component_pos': wire.start_item.pos() if wire.start_item else None,
            'start_terminal': wire.start_terminal,
            'end_component_id': id(wire.end_item) if wire.end_item else None,
            'end_component_pos': wire.end_item.pos() if wire.end_item else None,
            'end_terminal': wire.end_terminal,
            'path': self._save_path(wire.path()) if hasattr(wire, 'saved_path') and wire.saved_path else None
        }
        
        return wire_data
    
    def _save_path(self, path):
        """Сохранение пути провода"""
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
    
    def redo(self):
        """Удаление провода"""
        wire = self.wire_ref()
        if wire and self.is_item_valid(wire):
            wire.remove()
    
    def undo(self):
        """Восстановление провода"""
        from wire import Wire
        
        wire = Wire()
        self.wire_ref = weakref.ref(wire)
        
        # Восстанавливаем путь
        if self.wire_data and self.wire_data.get('path'):
            path = QPainterPath()
            for elem in self.wire_data['path']['elements']:
                if elem['type'] == 'move':
                    path.moveTo(elem['x'], elem['y'])
                elif elem['type'] == 'line':
                    path.lineTo(elem['x'], elem['y'])
            wire.setPath(path)
            wire.saved_path = path
        
        # Восстанавливаем начало
        start_component = None
        for item in self.scene.items():
            if hasattr(item, 'element_type') and item.pos() == self.wire_data['start_component_pos']:
                start_component = item
                break
        
        if start_component:
            wire.connect_to_component(
                start_component,
                self.wire_data['start_terminal'],
                is_start=True
            )
        
        # Восстанавливаем конец
        end_component = None
        for item in self.scene.items():
            if hasattr(item, 'element_type') and item.pos() == self.wire_data['end_component_pos']:
                end_component = item
                break
        
        if end_component:
            wire.connect_to_component(
                end_component,
                self.wire_data['end_terminal'],
                is_start=False
            )
        
        if wire.is_connected():
            self.scene.addItem(wire)
            wire.update_path()


class RotateComponentCommand(BaseCommand):
    """Команда поворота компонента"""
    
    def __init__(self, scene, component, old_angle, new_angle):
        super().__init__(f"Поворот {component.element_type}", scene)
        self.component_ref = weakref.ref(component)
        self.old_angle = old_angle
        self.new_angle = new_angle
        self.old_flipped = getattr(component, 'is_flipped', False)
        self.new_flipped = getattr(component, 'is_flipped', False)
    
    def _create_transform(self, angle, flipped):
        """Создание трансформации на основе угла и состояния отражения"""
        transform = QTransform()
        transform.rotate(angle)
        if flipped:
            transform.scale(-1, 1)
        return transform
    
    def _apply_transform(self, component, angle, flipped):
        """Применение трансформации к компоненту"""
        if not component or not self.is_item_valid(component):
            return
            
        component.prepareGeometryChange()
        component.rotation_angle = angle
        component.is_flipped = flipped
        component.setTransform(self._create_transform(angle, flipped))
        component.update_connected_wires()
        component.update()
    
    def redo(self):
        component = self.component_ref()
        self._apply_transform(component, self.new_angle, self.new_flipped)
    
    def undo(self):
        component = self.component_ref()
        self._apply_transform(component, self.old_angle, self.old_flipped)


class FlipComponentCommand(BaseCommand):
    """Команда отражения компонента"""
    
    def __init__(self, scene, component, old_flipped, new_flipped):
        super().__init__(f"Отражение {component.element_type}", scene)
        self.component_ref = weakref.ref(component)
        self.old_flipped = old_flipped
        self.new_flipped = new_flipped
        self.old_angle = getattr(component, 'rotation_angle', 0)
        self.new_angle = getattr(component, 'rotation_angle', 0)
    
    def _create_transform(self, angle, flipped):
        """Создание трансформации на основе угла и состояния отражения"""
        transform = QTransform()
        transform.rotate(angle)
        if flipped:
            transform.scale(-1, 1)
        return transform
    
    def _apply_transform(self, component, angle, flipped):
        """Применение трансформации к компоненту"""
        if not component or not self.is_item_valid(component):
            return
            
        component.prepareGeometryChange()
        component.rotation_angle = angle
        component.is_flipped = flipped
        component.setTransform(self._create_transform(angle, flipped))
        component.update_connected_wires()
        component.update()
    
    def redo(self):
        component = self.component_ref()
        self._apply_transform(component, self.new_angle, self.new_flipped)
    
    def undo(self):
        component = self.component_ref()
        self._apply_transform(component, self.old_angle, self.old_flipped)


class ChangePropertiesCommand(BaseCommand):
    """Команда изменения свойств компонента"""
    
    def __init__(self, scene, component, old_properties, new_properties):
        super().__init__(f"Изменение свойств {component.element_type}", scene)
        self.component_ref = weakref.ref(component)
        self.old_properties = old_properties.copy()
        self.new_properties = new_properties.copy()
    
    def redo(self):
        component = self.component_ref()
        if component and self.is_item_valid(component):
            component.properties = self.new_properties.copy()
            component.update()
            component.update_connected_wires()
    
    def undo(self):
        component = self.component_ref()
        if component and self.is_item_valid(component):
            component.properties = self.old_properties.copy()
            component.update()
            component.update_connected_wires()