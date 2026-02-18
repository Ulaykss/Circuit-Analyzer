from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, 
                            QDoubleSpinBox, QLabel, QVBoxLayout, QLineEdit,
                            QComboBox, QGroupBox, QHBoxLayout)
from PyQt5.QtCore import Qt

class PropertiesDialog(QDialog):
    """Диалог для редактирования свойств компонентов"""
    
    def __init__(self, properties, element_type, parent=None):
        super().__init__(parent)
        self.properties = properties.copy()
        self.element_type = element_type
        self.setWindowTitle(f"Свойства {self._get_display_name(element_type)}")
        self.setModal(True)
        self.resize(350, 300 if element_type == "Switch" else 200)
        
        main_layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        
        # Добавляем виджеты для каждого свойства
        self.inputs = {}
        
        # Специальная обработка для рубильника
        if element_type == "Switch":
            self._setup_switch_properties()
        else:
            self._setup_standard_properties()
        
        # Кнопки OK и Отмена
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        main_layout.addLayout(self.form_layout)
        main_layout.addWidget(self.button_box)
        
        self.setLayout(main_layout)
    
    def _get_display_name(self, element_type):
        """Получение отображаемого имени компонента"""
        names = {
            "Resistor": "Резистор",
            "Capacitor": "Конденсатор",
            "Inductor": "Катушка индуктивности",
            "Voltage Source": "Источник напряжения",
            "Current Source": "Источник тока",
            "Switch": "Рубильник",
            "Ground": "Земля"
        }
        return names.get(element_type, element_type)
    
    def _setup_standard_properties(self):
        """Настройка свойств для стандартных компонентов"""
        for name, value in self.properties.items():
            if name == "Name":
                # Имя компонента
                line_edit = QLineEdit(str(value))
                self.form_layout.addRow("Имя:", line_edit)
                self.inputs[name] = line_edit
            elif isinstance(value, (int, float)) and name not in ["State", "Resistance_closed", "Resistance_open"]:
                # Числовые свойства
                spinbox = QDoubleSpinBox()
                spinbox.setDecimals(6)
                spinbox.setRange(-999999, 999999)
                spinbox.setValue(float(value))
                
                # Добавляем единицы измерения
                if "Resistance" in name:
                    spinbox.setSuffix(" Ом")
                elif "Capacitance" in name:
                    spinbox.setSuffix(" Ф")
                elif "Inductance" in name:
                    spinbox.setSuffix(" Гн")
                elif "Voltage" in name:
                    spinbox.setSuffix(" В")
                elif "Current" in name:
                    spinbox.setSuffix(" А")
                
                display_name = self._get_property_display_name(name)
                self.form_layout.addRow(f"{display_name}:", spinbox)
                self.inputs[name] = spinbox
    
    def _setup_switch_properties(self):
        """Настройка свойств для рубильника"""
        # Группа основных свойств
        basic_group = QGroupBox("Основные параметры")
        basic_layout = QFormLayout()
        
        # Имя компонента
        name_edit = QLineEdit(str(self.properties.get("Name", "K1")))
        basic_layout.addRow("Имя:", name_edit)
        self.inputs["Name"] = name_edit
        
        # Состояние рубильника
        state_combo = QComboBox()
        state_combo.addItem("Замкнут", "closed")
        state_combo.addItem("Разомкнут", "open")
        
        current_state = self.properties.get("State", "closed")
        state_combo.setCurrentIndex(0 if current_state == "closed" else 1)
        state_combo.currentIndexChanged.connect(self._on_state_changed)
        
        basic_layout.addRow("Состояние:", state_combo)
        self.inputs["State"] = state_combo
        
        basic_group.setLayout(basic_layout)
        self.form_layout.addRow(basic_group)
        
        # Группа электрических параметров
        params_group = QGroupBox("Электрические параметры")
        params_layout = QFormLayout()
        
        # Сопротивление в замкнутом состоянии
        r_closed = QDoubleSpinBox()
        r_closed.setDecimals(6)
        r_closed.setRange(1e-12, 1e6)
        r_closed.setValue(float(self.properties.get("Resistance_closed", 1e-6)))
        r_closed.setSuffix(" Ом")
        r_closed.setToolTip("Сопротивление в замкнутом состоянии (очень мало)")
        params_layout.addRow("Сопротивление (замкнут):", r_closed)
        self.inputs["Resistance_closed"] = r_closed
        
        # Сопротивление в разомкнутом состоянии
        r_open = QDoubleSpinBox()
        r_open.setDecimals(6)
        r_open.setRange(1e3, 1e15)
        r_open.setValue(float(self.properties.get("Resistance_open", 1e12)))
        r_open.setSuffix(" Ом")
        r_open.setToolTip("Сопротивление в разомкнутом состоянии (очень большое)")
        params_layout.addRow("Сопротивление (разомкнут):", r_open)
        self.inputs["Resistance_open"] = r_open
        
        params_group.setLayout(params_layout)
        self.form_layout.addRow(params_group)
        
        # Пояснение
        info_label = QLabel(
            "Рубильник моделируется как сопротивление:\n"
            "• Замкнут: R → 0 (≈1e-6 Ом)\n"
            "• Разомкнут: R → ∞ (≈1e12 Ом)"
        )
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        self.form_layout.addRow(info_label)
    
    def _get_property_display_name(self, prop_name):
        """Получение отображаемого имени свойства"""
        names = {
            "Resistance": "Сопротивление",
            "Capacitance": "Емкость",
            "Inductance": "Индуктивность",
            "Voltage": "Напряжение",
            "Current": "Ток"
        }
        return names.get(prop_name, prop_name)
    
    def _on_state_changed(self, index):
        """Обработка изменения состояния рубильника"""
        # Ничего не делаем, просто сохраняем в свойствах
        pass

    def get_properties(self):
        """Получение обновленных свойств из диалога"""
        new_properties = {}
        
        for name, widget in self.inputs.items():
            if isinstance(widget, QDoubleSpinBox):
                new_properties[name] = widget.value()
            elif isinstance(widget, QComboBox):
                new_properties[name] = widget.currentData()
            else:
                try:
                    text = widget.text()
                    if '.' in text:
                        new_properties[name] = float(text)
                    else:
                        new_properties[name] = int(text)
                except ValueError:
                    new_properties[name] = widget.text()
        
        return new_properties