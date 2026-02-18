"""
Модуль для диалога настроек программы.
Позволяет выбирать тип источника напряжения и его параметры.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QDialogButtonBox, QComboBox, QDoubleSpinBox,
                             QLabel, QGroupBox, QTabWidget, QWidget, QCheckBox)
from PyQt5.QtCore import Qt
import sympy as sp


class SettingsDialog(QDialog):
    """Диалог настроек программы"""
    
    def __init__(self, solver, parent=None):
        super().__init__(parent)
        self.solver = solver
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(500, 400)
        
        # Основной layout
        main_layout = QVBoxLayout()
        
        # Создаем вкладки
        tab_widget = QTabWidget()
        
        # Вкладка источников
        source_tab = self._create_source_tab()
        tab_widget.addTab(source_tab, "Источники")
        
        main_layout.addWidget(tab_widget)
        
        # Кнопки OK/Отмена
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)
        
        self.setLayout(main_layout)
    
    def _create_source_tab(self):
        """Создание вкладки настроек источников"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Группа для источника напряжения
        voltage_group = QGroupBox("Источник напряжения")
        voltage_layout = QFormLayout()
        
        # Выбор типа источника
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItem("Постоянный (DC) - символ U", "DC")
        self.source_type_combo.addItem("Синусоидальный (AC) - символы A, ω, φ", "AC")
        
        # Устанавливаем текущее значение из solver
        current_type = getattr(self.solver, 'source_type', 'DC')
        index = self.source_type_combo.findData(current_type)
        if index >= 0:
            self.source_type_combo.setCurrentIndex(index)
        
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)
        voltage_layout.addRow("Тип источника:", self.source_type_combo)
        
        # Галочка для использования символьных обозначений
        self.symbolic_checkbox = QCheckBox("Использовать символьные обозначения (A, ω, φ) в формулах")
        self.symbolic_checkbox.setChecked(True)
        self.symbolic_checkbox.setToolTip(
            "При включении в формулах будут отображаться A, ω, φ вместо численных значений.\n"
            "Для численных расчётов будут использоваться значения по умолчанию."
        )
        voltage_layout.addRow(self.symbolic_checkbox)
        
        # Информационная метка о численных расчётах
        info_label_numeric = QLabel(
            "Примечание: При включённой галочке для численных расчётов\n"
            "будут использоваться значения параметров по умолчанию,\n"
            "указанные ниже в полях ввода."
        )
        info_label_numeric.setStyleSheet("color: #666; font-size: 9px; padding: 2px;")
        info_label_numeric.setWordWrap(True)
        voltage_layout.addRow(info_label_numeric)
        
        # Параметры для AC источника
        self.ac_params_group = QGroupBox("Параметры синусоидального источника (по умолчанию)")
        ac_layout = QFormLayout()
        
        self.amplitude_spin = QDoubleSpinBox()
        self.amplitude_spin.setDecimals(3)
        self.amplitude_spin.setRange(0.001, 1000.0)
        self.amplitude_spin.setValue(5.0)
        self.amplitude_spin.setSuffix(" В")
        ac_layout.addRow("Амплитуда A:", self.amplitude_spin)
        
        self.frequency_spin = QDoubleSpinBox()
        self.frequency_spin.setDecimals(3)
        self.frequency_spin.setRange(0.1, 100000.0)
        self.frequency_spin.setValue(100.0)
        self.frequency_spin.setSuffix(" рад/с")
        ac_layout.addRow("Угловая частота ω:", self.frequency_spin)
        
        self.phase_spin = QDoubleSpinBox()
        self.phase_spin.setDecimals(3)
        self.phase_spin.setRange(0.0, 360.0)
        self.phase_spin.setValue(0.0)
        self.phase_spin.setSuffix(" °")
        ac_layout.addRow("Начальная фаза φ:", self.phase_spin)
        
        self.ac_params_group.setLayout(ac_layout)
        
        # Информационная метка
        info_label = QLabel(
            "Для синусоидального источника используется форма:\n"
            "v(t) = A·sin(ωt + φ), где φ - начальная фаза в градусах\n\n"
            "В операторной форме: E(p) = A·(ω·cosφ + p·sinφ) / (p² + ω²)\n\n"
            "Режим символьных обозначений:\n"
            "• ВКЛ - в формулах отображаются A, ω, φ (для аналитических выкладок)\n"
            "• ВЫКЛ - в формулах подставляются численные значения (для численных расчётов)"
        )
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        
        voltage_layout.addRow(self.ac_params_group)
        voltage_layout.addRow(info_label)
        
        voltage_group.setLayout(voltage_layout)
        layout.addWidget(voltage_group)
        
        # Загружаем сохраненные параметры
        self._load_saved_params()
        
        # Обновляем видимость AC параметров
        self._on_source_type_changed()
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _load_saved_params(self):
        """Загрузка сохраненных параметров из solver"""
        if hasattr(self.solver, 'source_params'):
            params = self.solver.source_params
            self.amplitude_spin.setValue(params.get('amplitude', 5.0))
            self.frequency_spin.setValue(params.get('frequency', 100.0))
            
            # Конвертируем фазу из радиан в градусы для отображения
            phase_rad = params.get('phase', 0.0)
            phase_deg = phase_rad * 180 / 3.14159
            self.phase_spin.setValue(phase_deg)
            
            # Устанавливаем состояние чекбокса
            use_symbolic = params.get('use_symbolic', True)
            self.symbolic_checkbox.setChecked(use_symbolic)
    
    def _on_source_type_changed(self):
        """Обработка изменения типа источника"""
        is_ac = self.source_type_combo.currentData() == "AC"
        self.ac_params_group.setEnabled(is_ac)
        self.symbolic_checkbox.setEnabled(is_ac)
    
    def get_settings(self):
        """Получение настроек из диалога"""
        source_type = self.source_type_combo.currentData()
        use_symbolic = self.symbolic_checkbox.isChecked()
        
        # Конвертируем фазу из градусов в радианы
        phase_deg = self.phase_spin.value()
        phase_rad = phase_deg * 3.14159 / 180
        
        source_params = {
            'amplitude': self.amplitude_spin.value(),
            'frequency': self.frequency_spin.value(),
            'phase': phase_rad,
            'use_symbolic': use_symbolic
        }
        
        return {
            'source_type': source_type,
            'source_params': source_params
        }