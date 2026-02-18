import json
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QTransform, QPainterPath


class FileHandler:
    """Класс для работы с файлами схем (сохранение/загрузка)"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.current_file = None
        
    def new_file(self):
        """Создание новой схемы с поддержкой Undo"""
        if not self._check_save():
            return False
        
        from commands import ClearSceneCommand
        
        if hasattr(self.main_window, 'undo_stack'):
            self.main_window.undo_stack.clear()
            command = ClearSceneCommand(self.main_window.scene)
            self.main_window.undo_stack.push(command)
        else:
            grid_size = 10
            if hasattr(self.main_window.canvas, 'grid_background'):
                grid_size = self.main_window.canvas.grid_background.grid_size
            
            self.main_window.scene.clear()
            
            if hasattr(self.main_window.canvas, 'grid_background'):
                from canvas import InfiniteGridBackground
                self.main_window.canvas.grid_background = InfiniteGridBackground(grid_size)
                self.main_window.scene.addItem(self.main_window.canvas.grid_background)
        
        self.current_file = None
        self.main_window.setWindowTitle("Симулятор электрических цепей - Новый файл")
        return True
    
    def open_file(self):
        """Открытие схемы из файла с поддержкой Undo"""
        if not self._check_save():
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Открыть схему",
            "",
            "Файлы схем (*.circuit);;Все файлы (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if hasattr(self.main_window, 'undo_stack'):
                    self.main_window.undo_stack.clear()
                
                grid_size = 10
                if hasattr(self.main_window.canvas, 'grid_background'):
                    grid_size = self.main_window.canvas.grid_background.grid_size
                
                if hasattr(self.main_window.canvas, 'update_timer'):
                    self.main_window.canvas.update_timer.stop()
                
                self.main_window.scene.clear()
                
                from canvas import InfiniteGridBackground
                self.main_window.canvas.grid_background = InfiniteGridBackground(grid_size)
                self.main_window.scene.addItem(self.main_window.canvas.grid_background)
                
                self._load_from_data(data)
                self.current_file = file_path
                self.main_window.setWindowTitle(f"Симулятор электрических цепей - {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self.main_window, "Ошибка", f"Не удалось открыть файл: {str(e)}")
    
    def save_file(self):
        """Сохранение текущей схемы"""
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self.save_file_as()
    
    def save_file_as(self):
        """Сохранение схемы в новый файл"""
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Сохранить схему",
            "",
            "Файлы схем (*.circuit);;Все файлы (*)"
        )
        
        if file_path:
            if not file_path.endswith('.circuit'):
                file_path += '.circuit'
            
            if self._save_to_file(file_path):
                self.current_file = file_path
                self.main_window.setWindowTitle(f"Симулятор электрических цепей - {file_path}")
    
    def _save_to_file(self, file_path):
        """Сохранение данных в файл"""
        try:
            data = self._get_save_data()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
            return False
    
    def _get_save_data(self):
        """Получение данных для сохранения"""
        data = {
            "elements": [],
            "nodes": [],  # Пустой массив узлов для совместимости
            "wires": [],
            "version": "2.1"
        }
        
        # Сохранение компонентов
        for item in self.main_window.scene.items():
            if hasattr(item, 'element_type'):
                transform = item.transform()
                
                transform_matrix = [
                    transform.m11(), transform.m12(), transform.m13(),
                    transform.m21(), transform.m22(), transform.m23(),
                    transform.m31(), transform.m32(), transform.m33()
                ]
                
                element_data = {
                    "id": id(item),
                    "type": item.element_type,
                    "x": round(item.x(), 2),
                    "y": round(item.y(), 2),
                    "properties": item.properties.copy() if hasattr(item, 'properties') else {},
                    "rotation_angle": getattr(item, 'rotation_angle', 0),
                    "is_flipped": getattr(item, 'is_flipped', False),
                    "transform_matrix": transform_matrix
                }
                data["elements"].append(element_data)
        
        # Сохранение проводов
        from wire import Wire
        for item in self.main_window.scene.items():
            if isinstance(item, Wire):
                wire_data = self._save_wire_data(item)
                if wire_data:
                    data["wires"].append(wire_data)
        
        return data
    
    def _save_wire_data(self, wire):
        """Сохранение данных провода"""
        if not wire.is_connected():
            return None
        
        wire_data = {
            'start_element_id': id(wire.start_item),
            'start_terminal': list(wire.start_terminal) if wire.start_terminal else None,
            'end_element_id': id(wire.end_item),
            'end_terminal': list(wire.end_terminal) if wire.end_terminal else None,
        }
        
        # Сохраняем путь провода, если он был изменен
        if hasattr(wire, 'saved_path') and wire.saved_path and not wire.saved_path.isEmpty():
            path_data = self._save_path(wire.saved_path)
            if path_data:
                wire_data['path'] = path_data
        
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
    
    def _load_from_data(self, data):
        """Загрузка данных из сохраненного файла"""
        version = data.get("version", "1.0")
        
        # Словари для восстановления связей по ID
        element_map = {}
        
        # ========== 1. Восстановление компонентов ==========
        for element_data in data.get("elements", []):
            element = self._create_element_from_data(element_data)
            if element:
                self.main_window.scene.addItem(element)
                old_id = element_data.get("id")
                if old_id:
                    element_map[old_id] = element
        
        # ========== 2. Восстановление проводов ==========
        from wire import Wire
        
        for wire_data in data.get("wires", []):
            wire = Wire()
            
            # Восстанавливаем путь, если он есть
            if 'path' in wire_data:
                path = QPainterPath()
                for elem in wire_data['path']['elements']:
                    if elem['type'] == 'move':
                        path.moveTo(elem['x'], elem['y'])
                    elif elem['type'] == 'line':
                        path.lineTo(elem['x'], elem['y'])
                wire.setPath(path)
                wire.saved_path = path
            
            # Восстанавливаем подключения
            if "start_element_id" in wire_data and "end_element_id" in wire_data:
                start_element = element_map.get(wire_data["start_element_id"])
                end_element = element_map.get(wire_data["end_element_id"])
                
                if start_element and end_element:
                    start_terminal = tuple(wire_data["start_terminal"]) if "start_terminal" in wire_data else None
                    end_terminal = tuple(wire_data["end_terminal"]) if "end_terminal" in wire_data else None
                    
                    if start_terminal and end_terminal:
                        wire.connect_to_component(start_element, start_terminal, is_start=True)
                        wire.connect_to_component(end_element, end_terminal, is_start=False)
                        
                        if wire.is_connected():
                            self.main_window.scene.addItem(wire)
        
        # ========== 3. Обновление всех проводов ==========
        from wire import Wire
        for item in self.main_window.scene.items():
            if isinstance(item, Wire):
                item.update_path()
        
        # Перезапускаем таймер
        if hasattr(self.main_window.canvas, 'update_timer'):
            self.main_window.canvas.update_timer.start()
        
        # Обновляем представление
        self.main_window.canvas.viewport().update()
    
    def _create_element_from_data(self, element_data):
        """Создание элемента из данных с полным восстановлением трансформации"""
        from circuit_elements import GraphicsCircuitItem
        from PyQt5.QtGui import QTransform
        
        element = GraphicsCircuitItem(
            element_data["type"],
            element_data["x"],
            element_data["y"]
        )
        
        if "properties" in element_data:
            element.properties = element_data["properties"]
        
        if "rotation_angle" in element_data:
            element.rotation_angle = element_data["rotation_angle"]
        
        if "is_flipped" in element_data:
            element.is_flipped = element_data["is_flipped"]
        
        if "transform_matrix" in element_data and element_data["transform_matrix"]:
            matrix = element_data["transform_matrix"]
            # ИСПРАВЛЕНИЕ: Правильное восстановление матрицы
            transform = QTransform(
                matrix[0], matrix[1], matrix[2],
                matrix[3], matrix[4], matrix[5],
                matrix[6], matrix[7], matrix[8]
            )
            element.setTransform(transform)
        
        return element
    
    def _check_save(self):
        """Проверка необходимости сохранения текущей схемы"""
        has_elements = any(hasattr(item, 'element_type') for item in self.main_window.scene.items())
        
        if has_elements:
            reply = QMessageBox.question(
                self.main_window,
                "Сохранить изменения",
                "Сохранить изменения в текущей схеме?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.save_file()
                return True
            elif reply == QMessageBox.Discard:
                return True
            else:
                return False
        return True