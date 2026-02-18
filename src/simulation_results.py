import sympy as sp
import numpy as np
import matplotlib.pyplot as plt
import re
from PyQt5.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QFormLayout, QLabel,
    QHBoxLayout, QComboBox, QMessageBox, QSpinBox,
    QDoubleSpinBox, QPushButton, QSizePolicy, QScrollArea, QTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont, QMovie
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch


class PlotCanvas(QWidget):
    """Виджет для отображения графиков matplotlib"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.fig.tight_layout()

        # Цвета и стили линий для графиков
        self._colors = ['#2563eb', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4']
        self._linestyles = ['-', '--', '-.', ':', (0, (5, 1)), (0, (3, 1, 1, 1))]

    def plot(self, t, y, title=None, xlabel="t (s)", ylabel="", yunit=""):
        """Построение графика с заданными параметрами"""
        self.ax.clear()

        if y is None or len(t) == 0:
            self.ax.text(0.5, 0.5, 'Нет данных для построения графика',
                        horizontalalignment='center', verticalalignment='center',
                        transform=self.ax.transAxes, fontsize=12)
            self.canvas.draw()
            return

        # Обработка многомерных данных
        ys = None
        arr = np.array(y)
        if arr.ndim == 1:
            ys = arr.reshape((len(arr), 1))
        elif arr.ndim == 2:
            ys = arr
        else:
            ys = arr.reshape((len(t), -1))

        n_series = ys.shape[1]
        # Построение линий с разными цветами и стилями
        for i in range(n_series):
            color = self._colors[i % len(self._colors)]
            ls = self._linestyles[i % len(self._linestyles)]
            self.ax.plot(t, ys[:, i], lw=2, color=color, linestyle=ls, label=f"Серия {i+1}")

        # Настройка осей и заголовков
        if title:
            self.ax.set_title(title, fontsize=14, fontweight='bold')
        self.ax.set_xlabel(xlabel, fontsize=12)
        
        ylabel_full = ylabel
        if yunit:
            ylabel_full += f" ({yunit})"
        self.ax.set_ylabel(ylabel_full, fontsize=12)
        
        self.ax.grid(True, alpha=0.3)
        self.ax.tick_params(axis='both', which='major', labelsize=10)
        
        if n_series > 1:
            self.ax.legend(loc='best', fontsize=10)
        
        self.fig.tight_layout()
        self.canvas.draw()


class FormulaCanvas(QWidget):
    """Виджет для отображения математических формул через HTML"""
    
    def __init__(self, expr, desc="", parent=None):
        super().__init__(parent)
        self.expr = expr
        self.desc = desc
        
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                font-family: 'Times New Roman', serif;
                font-size: 14px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 15px;
                margin: 5px;
            }
        """)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.render_formula()
    
    def render_formula(self):
        """Рендеринг формулы в HTML формате - ИСПРАВЛЕННАЯ ВЕРСИЯ для U_1, U_2, U_3"""
        try:
            if self.desc:
                # Применяем форматирование с нижними индексами к заголовку
                desc_formatted = self._format_description_with_subscripts(self.desc)
                title_text = f"<b>{desc_formatted}</b><br><br>"
            else:
                title_text = ""
            
            formula_text = self._expr_to_html(self.expr)
            full_text = f"{title_text}{formula_text}"
            
            self.label.setText(full_text)
            
        except Exception as e:
            self.label.setText(f"Ошибка: {str(e)}<br>{str(self.expr)}")
    
    def _format_description_with_subscripts(self, text):
        """Форматирование описания с нижними индексами"""
        import re
        
        # Функция для замены подчеркивания с цифрой на нижний индекс
        def replace_underscore(match):
            letter = match.group(1)
            number = match.group(2)
            return f"{letter}<sub>{number}</sub>"
        
        # Сначала обрабатываем формат с подчеркиванием: U_1, U_2, I_E1, I_L1
        pattern = r'([A-Za-zА-Яа-яωφ]+)_(\d+)'
        text = re.sub(pattern, replace_underscore, text)
        
        # Затем обрабатываем буквы с цифрами без подчеркивания: U1, U2
        pattern2 = r'([A-Za-zА-Яа-яωφ])(\d+)'
        text = re.sub(pattern2, replace_underscore, text)
        
        # Дополнительная обработка для специальных символов
        text = text.replace('ω', 'ω')
        text = text.replace('φ', 'φ')
        
        return text
    
    def _expr_to_html(self, expr):
        """Преобразование выражения в HTML представление"""
        if hasattr(expr, '__iter__') and not isinstance(expr, str):
            if hasattr(expr, 'shape'):  # Matrix
                return self._matrix_to_html(expr)
            else:  # Вектор или кортеж
                return self._vector_to_html(expr)
        elif isinstance(expr, sp.Eq):  # Уравнение
            lhs = self._format_single_expr_html(expr.lhs)
            rhs = self._format_single_expr_html(expr.rhs)
            return f"{lhs} = {rhs}"
        else:  # Одиночное выражение
            return self._format_single_expr_html(expr)
    
    def _matrix_to_html(self, matrix):
        """Преобразование матрицы в HTML таблицу"""
        rows, cols = matrix.shape
        html = '<table style="border-collapse: collapse; margin: 0 auto; border: 2px solid #2563eb;">'
        
        for i in range(rows):
            html += '<tr>'
            for j in range(cols):
                elem = self._format_single_expr_html(matrix[i, j])
                border_style = "border: 1px solid #94a3b8; padding: 5px; text-align: center;"
                html += f'<td style="{border_style}">{elem}</td>'
            html += '</tr>'
        
        html += '</table>'
        return html
    
    def _vector_to_html(self, vector):
        """Преобразование вектора в HTML"""
        html = '<table style="border-collapse: collapse; margin: 0 auto; border: 2px solid #10b981;">'
        html += '<tr>'
        
        for elem in vector:
            elem_str = self._format_single_expr_html(elem)
            border_style = "border: 1px solid #86efac; padding: 5px; text-align: center;"
            html += f'<td style="{border_style}">{elem_str}</td>'
        
        html += '</tr></table>'
        return html
    
    def _format_single_expr_html(self, expr):
        """Форматирование одиночного выражения в HTML"""
        if isinstance(expr, sp.Symbol):
            return self._format_symbol_html(str(expr))
        elif isinstance(expr, (sp.Add, sp.Mul, sp.Pow)):
            return self._format_operation_html(expr)
        else:
            # Преобразуем в строку и форматируем
            expr_str = str(expr)
            return self._format_expr_string_html(expr_str)
    
    def _format_symbol_html(self, symbol_str):
        """Форматирование символа в HTML"""
        import re
        
        # Специальная обработка для греческих букв
        special_symbols = {
            'omega': 'ω',
            'phi': 'φ',
            'alpha': 'α',
            'beta': 'β',
            'gamma': 'γ',
            'delta': 'δ'
        }
        
        if symbol_str in special_symbols:
            return special_symbols[symbol_str]
        
        # Функция для замены на нижние индексы
        def replace_subscript(match):
            letter = match.group(1)
            numbers = match.group(2)
            return f"{letter}<sub>{numbers}</sub>"
        
        # Сначала обрабатываем формат с подчеркиванием: U_1
        if '_' in symbol_str:
            parts = symbol_str.split('_')
            if len(parts) == 2 and parts[1].isdigit():
                return f"{parts[0]}<sub>{parts[1]}</sub>"
        
        # Затем обрабатываем формат без подчеркивания: U1
        pattern = r'([A-Za-zА-Яа-яωφ])(\d+)'
        result = re.sub(pattern, replace_subscript, symbol_str)
        
        return result
    
    def _format_operation_html(self, expr):
        """Форматирование операции в HTML"""
        import re
        
        try:
            if hasattr(expr, 'expr'):
                expr_str = str(expr.expr)
            else:
                expr_str = str(expr)
            
            expr_str = expr_str.strip()
            
            # Специальная обработка для греческих букв
            greek_replacements = {
                'omega': 'ω',
                'phi': 'φ',
                'alpha': 'α',
                'beta': 'β',
                'gamma': 'γ',
                'delta': 'δ'
            }
            
            for greek, symbol in greek_replacements.items():
                expr_str = expr_str.replace(greek, symbol)
            
            # Функция для замены на нижние индексы в тексте
            def replace_subscript_in_text(text):
                # Обрабатываем формат с подчеркиванием: U_1
                def replace_underscore(match):
                    letter = match.group(1)
                    number = match.group(2)
                    return f"{letter}<sub>{number}</sub>"
                
                text = re.sub(r'([A-Za-zА-Яа-яωφ]+)_(\d+)', replace_underscore, text)
                
                # Обрабатываем формат без подчеркивания: U1
                def replace_numbers(match):
                    letter = match.group(1)
                    number = match.group(2)
                    return f"{letter}<sub>{number}</sub>"
                
                text = re.sub(r'([A-Za-zА-Яа-яωφ])(\d+)', replace_numbers, text)
                
                return text
            
            # Обрабатываем степени
            result_parts = []
            i = 0
            while i < len(expr_str):
                if i + 1 < len(expr_str) and expr_str[i:i+2] == '**':
                    result_parts.append('<sup>')
                    i += 2
                    
                    j = i
                    paren_count = 0
                    in_paren = False
                    
                    if j < len(expr_str) and expr_str[j] == '(':
                        in_paren = True
                        paren_count = 1
                        j += 1
                    
                    while j < len(expr_str):
                        if in_paren:
                            if expr_str[j] == '(':
                                paren_count += 1
                            elif expr_str[j] == ')':
                                paren_count -= 1
                                if paren_count == 0:
                                    j += 1
                                    break
                        else:
                            if expr_str[j] in ['+', '-', '*', '/', ')', '=']:
                                break
                        j += 1
                    
                    degree = expr_str[i:j]
                    # Применяем форматирование индексов к степени
                    degree_html = replace_subscript_in_text(degree)
                    result_parts.append(degree_html)
                    result_parts.append('</sup>')
                    i = j
                else:
                    result_parts.append(expr_str[i])
                    i += 1
            
            expr_str = ''.join(result_parts)
            
            # Применяем форматирование индексов ко всему выражению
            expr_str = replace_subscript_in_text(expr_str)
            
            # Заменяем * на ·
            expr_str = expr_str.replace('*', '·')
            
            # Обрабатываем дроби
            if '/' in expr_str:
                parts = expr_str.split('/')
                if len(parts) == 2:
                    numerator = parts[0].strip()
                    denominator = parts[1].strip()
                    
                    simple_numerator = len(numerator) < 30 and '(' not in numerator
                    simple_denominator = len(denominator) < 30 and '(' not in denominator
                    
                    if simple_numerator and simple_denominator:
                        expr_str = f'<span style="display: inline-block; vertical-align: middle; text-align: center;"><div style="border-bottom: 1px solid black; padding-bottom: 1px;">{numerator}</div><div>{denominator}</div></span>'
            
            # Заменяем отрицательные числа
            expr_str = expr_str.replace('-', '−')
            expr_str = expr_str.replace('−1·', '−')
            expr_str = expr_str.replace('1·', '')
            
            return expr_str
            
        except Exception as e:
            print(f"Ошибка форматирования HTML: {e}")
            return str(expr)
    
    def _format_simple_expr(self, expr_str):
        """Форматирование простого выражения без рекурсии"""
        import re
        
        result = expr_str.replace('p', '<i>p</i>')
        
        # Форматирование нижних индексов
        def replace_subscript(match):
            letter = match.group(1)
            number = match.group(2)
            return f'{letter}<sub>{number}</sub>'
        
        # Обрабатываем формат с подчеркиванием
        result = re.sub(r'([A-Za-zА-Яа-яωφ]+)_(\d+)', replace_subscript, result)
        
        # Обрабатываем формат без подчеркивания
        result = re.sub(r'([A-Za-zА-Яа-яωφ])(\d+)', replace_subscript, result)
        
        result = result.replace('*', '·')
        result = result.replace('-', '−')
        
        return result
    
    def _format_expr_string_html(self, expr_str):
        """Форматирование строки выражения в HTML"""
        import re
        
        # Специальная обработка для греческих букв
        greek_replacements = {
            'omega': 'ω',
            'phi': 'φ',
            'alpha': 'α',
            'beta': 'β',
            'gamma': 'γ',
            'delta': 'δ'
        }
        
        for greek, symbol in greek_replacements.items():
            expr_str = expr_str.replace(greek, symbol)
        
        expr_str = expr_str.replace('p', '<i>p</i>')
        
        # Функция для замены на нижние индексы
        def replace_subscript(match):
            letter = match.group(1)
            number = match.group(2)
            return f'{letter}<sub>{number}</sub>'
        
        # Обрабатываем степени
        result_parts = []
        i = 0
        while i < len(expr_str):
            if i + 1 < len(expr_str) and expr_str[i:i+2] == '**':
                result_parts.append('<sup>')
                i += 2
                
                j = i
                paren_count = 0
                in_paren = False
                
                if j < len(expr_str) and expr_str[j] == '(':
                    in_paren = True
                    paren_count = 1
                    j += 1
                
                while j < len(expr_str):
                    if in_paren:
                        if expr_str[j] == '(':
                            paren_count += 1
                        elif expr_str[j] == ')':
                            paren_count -= 1
                            if paren_count == 0:
                                j += 1
                                break
                    else:
                        if expr_str[j] in ['+', '-', '*', '/', ')', '=']:
                            break
                    j += 1
                
                degree = expr_str[i:j]
                # Применяем форматирование индексов к степени
                # Обрабатываем формат с подчеркиванием
                degree_html = re.sub(r'([A-Za-zА-Яа-яωφ]+)_(\d+)', replace_subscript, degree)
                # Обрабатываем формат без подчеркивания
                degree_html = re.sub(r'([A-Za-zА-Яа-яωφ])(\d+)', replace_subscript, degree_html)
                result_parts.append(degree_html)
                result_parts.append('</sup>')
                i = j
            else:
                result_parts.append(expr_str[i])
                i += 1
        
        expr_str = ''.join(result_parts)
        
        # Применяем форматирование индексов ко всему выражению
        # Сначала обрабатываем формат с подчеркиванием
        expr_str = re.sub(r'([A-Za-zА-Яа-яωφ]+)_(\d+)', replace_subscript, expr_str)
        # Затем обрабатываем формат без подчеркивания
        expr_str = re.sub(r'([A-Za-zА-Яа-яωφ])(\d+)', replace_subscript, expr_str)
        
        # Заменяем * на ·
        expr_str = expr_str.replace('*', '·')
        
        # Обрабатываем дроби
        expr_str = self._format_fractions_in_string(expr_str)
        
        return expr_str
    
    def _format_fractions_in_string(self, expr_str):
        """Форматирование дробей в строке"""
        import re
        
        def replace_simple_fraction(match):
            num = match.group(1)
            den = match.group(2)
            if '/' not in num and '/' not in den:
                return f'<span style="display: inline-block; vertical-align: middle; text-align: center;"><div style="border-bottom: 1px solid black;">{num}</div><div>{den}</div></span>'
            else:
                return f'{num}/{den}'
        
        pattern = r'([a-zA-Z0-9<sub>\d</sub>·<i>p</i><i>K</i>]+)/([a-zA-Z0-9<sub>\d</sub>·<i>p</i><i>K</i>]+)'
        result = re.sub(pattern, replace_simple_fraction, expr_str)
        
        return result


class SimulationResults(QWidget):
    """Главный виджет для отображения результатов моделирования"""
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.solver = None
        self.analysis = None
        self.param_widgets = {}
        self.last_param_values = {}
        self.initial_conditions = {"I0": 0.0, "V0": 0.0}
        self.var_list = []

        self.tabs = QTabWidget(self)

        # --- Вкладка символьного анализа ---
        self.sym_layout = QVBoxLayout()
        self.sym_widget = QWidget()
        self.sym_widget.setLayout(self.sym_layout)
        self.sym_scroll = QScrollArea()
        self.sym_scroll.setWidgetResizable(True)
        self.sym_scroll.setWidget(self.sym_widget)

        # --- Вкладка численного анализа ---
        self.num_widget = QWidget()
        self.num_layout = QVBoxLayout(self.num_widget)
        self.params_form = QFormLayout()
        self.num_layout.addLayout(self.params_form)

        # --- Виджеты для численного расчета ---
        calc_layout = QHBoxLayout()
        self.time_input = QDoubleSpinBox()
        self.time_input.setDecimals(6)
        self.time_input.setValue(0.1)
        self.time_input.setSuffix(" s")

        calc_button = QPushButton("Рассчитать в момент времени")
        calc_button.clicked.connect(self.on_calculate_numerical)

        calc_layout.addWidget(QLabel("Рассчитать при t ="))
        calc_layout.addWidget(self.time_input)
        calc_layout.addWidget(calc_button)
        calc_layout.addStretch()

        self.num_layout.addLayout(calc_layout)

        var_row = QHBoxLayout()
        var_row.addWidget(QLabel("Переменная:"))
        self.num_var_combo = QComboBox()
        var_row.addWidget(self.num_var_combo)
        var_row.addStretch()
        self.num_layout.addLayout(var_row)

        self.num_output_layout = QVBoxLayout()
        self.num_output_widget = QWidget()
        self.num_output_widget.setLayout(self.num_output_layout)
        self.num_scroll = QScrollArea()
        self.num_scroll.setWidgetResizable(True)
        self.num_scroll.setWidget(self.num_output_widget)
        self.num_layout.addWidget(self.num_scroll)

        # --- Вкладка графиков ---
        self.plot_widget = PlotCanvas()
        self.plot_controls_layout = QFormLayout()

        self.time_start = QDoubleSpinBox()
        self.time_start.setDecimals(3)
        self.time_start.setValue(0.0)
        self.time_start.setMaximum(1e6)
        self.plot_controls_layout.addRow("Начальное время (с):", self.time_start)

        self.time_end = QDoubleSpinBox()
        self.time_end.setDecimals(3)
        self.time_end.setValue(1.0)
        self.time_end.setMaximum(1e6)
        self.plot_controls_layout.addRow("Конечное время (с):", self.time_end)

        self.points_count = QSpinBox()
        self.points_count.setRange(10, 10000)
        self.points_count.setValue(500)
        self.plot_controls_layout.addRow("Количество точек:", self.points_count)

        self.plot_var_combo = QComboBox()
        self.plot_controls_layout.addRow("Переменная:", self.plot_var_combo)

        self.plot_button = QPushButton("Построить график")
        self.plot_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.plot_button.clicked.connect(self.on_build_plot)

        self.plot_layout = QVBoxLayout()
        self.plot_layout.addLayout(self.plot_controls_layout)
        self.plot_layout.addWidget(self.plot_button)
        self.plot_layout.addWidget(self.plot_widget)

        self.plot_container = QWidget()
        self.plot_container.setLayout(self.plot_layout)

        # --- Добавление вкладок ---
        self.tabs.addTab(self.sym_scroll, "Символьный анализ")
        self.tabs.addTab(self.num_widget, "Численный анализ")
        self.tabs.addTab(self.plot_container, "Графики")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def on_calculate_numerical(self):
        """Обработка численного расчета в заданный момент времени - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if not self.analysis:
            self._show_numerical_result("Нет данных анализа")
            return

        symbolic = self.analysis.get("symbolic", {})
        X_sym = symbolic.get("X")
        var_list = symbolic.get("vars", [])
        var_name = self.num_var_combo.currentText()

        if X_sym is None or not var_list or not var_name:
            self._show_numerical_result("Символьное решение недоступно")
            return

        try:
            # Находим индекс выбранной переменной
            var_index = [str(v) for v in var_list].index(var_name)
            expr_p = X_sym[var_index]
            
            # Подставляем параметры компонентов
            subs_dict = {}
            for name, widget in self.param_widgets.items():
                try:
                    subs_dict[sp.Symbol(name)] = float(widget.value())
                except:
                    pass
            
            # Добавляем начальные условия
            if hasattr(self, 'initial_current'):
                subs_dict[sp.Symbol('I0')] = float(self.initial_current.value())
            if hasattr(self, 'initial_voltage'):
                subs_dict[sp.Symbol('V0')] = float(self.initial_voltage.value())
            
            expr_p_numeric = expr_p.subs(subs_dict)
            
            # Получаем время для расчета
            t_val = self.time_input.value()
            
            # Правильно вычисляем значение во временной области
            result = self._calculate_time_domain_value(expr_p_numeric, t_val)
            
            # Определяем единицу измерения
            if var_name.upper().startswith('I'):
                unit = "А"
            elif var_name.upper().startswith('V') or var_name.upper().startswith('U'):
                unit = "В"
            else:
                unit = ""
            
            # Создаем красивое отображение результата
            self._show_numerical_result_formula(var_name, t_val, result, unit)

        except Exception as e:
            self._show_numerical_result(f"Ошибка расчета: {str(e)}")

    def _calculate_time_domain_value(self, expr_p, t_val):
        """
        Вычисление значения во временной области
        p_sym = sp.Symbol('p')
        t_sym = sp.Symbol('t', real=True, positive=True)

        """
        
        try:
            # Проверяем, является ли выражение AC сигналом
            expr_str = str(expr_p)
            if 'omega' in expr_str and ('p**2' in expr_str or 'p**2' in str(expr_p)):
                # Это AC сигнал - используем прямое вычисление
                try:
                    # Пробуем символьное обратное преобразование
                    expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
                    expr_t = sp.simplify(expr_t)
                    
                    # Убираем Heaviside, так как t>0
                    if expr_t.has(sp.Heaviside):
                        expr_t = expr_t.replace(sp.Heaviside(t_sym), 1)
                    
                    # Подставляем время
                    result = float(expr_t.subs(t_sym, t_val))
                    return result
                except Exception as e:
                    print(f"Символьное обратное преобразование для AC не удалось: {e}")
                    
                    # Если не получилось, используем прямое вычисление для AC сигнала
                    # Пытаемся извлечь параметры
                    try:
                        # Простой случай: A*omega/(p**2+omega**2) -> A*sin(omega*t)
                        if expr_p.is_Mul:
                            # Ищем множители
                            for arg in expr_p.args:
                                if arg.is_Pow and arg.base == p_sym and arg.exp == 2:
                                    # Это p^2
                                    pass
                            
                            # Пытаемся определить форму
                            if 'omega' in expr_str:
                                # Получаем значения параметров
                                subs_vals = {}
                                if hasattr(self, 'solver') and self.solver:
                                    if hasattr(self.solver, 'A'):
                                        subs_vals[self.solver.A] = float(self.solver.source_params.get('amplitude', 1.0))
                                    if hasattr(self.solver, 'omega'):
                                        subs_vals[self.solver.omega] = float(self.solver.source_params.get('frequency', 100.0))
                                    if hasattr(self.solver, 'phi'):
                                        subs_vals[self.solver.phi] = float(self.solver.source_params.get('phase', 0.0))
                                
                                expr_p_num = expr_p.subs(subs_vals)
                                
                                # Пробуем вычислить обратное преобразование для числовых значений
                                expr_t_num = sp.inverse_laplace_transform(expr_p_num, p_sym, t_sym, noconds=True)
                                result = float(expr_t_num.subs(t_sym, t_val))
                                return result
                    except:
                        pass
                    
                    # Если всё не получилось, используем численный метод
                    if hasattr(self, 'solver') and self.solver:
                        t_vals = np.array([t_val])
                        y_vals = self.solver.numeric_inverse_laplace(expr_p, t_vals)
                        return float(y_vals[0]) if len(y_vals) > 0 else 0.0
                    return 0.0
            
            # Пробуем символьное обратное преобразование
            expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
            expr_t = sp.simplify(expr_t)
            
            # Убираем Heaviside, так как t>0
            if expr_t.has(sp.Heaviside):
                expr_t = expr_t.replace(sp.Heaviside(t_sym), 1)
            
            # Подставляем время
            result = float(expr_t.subs(t_sym, t_val))
            return result
            
        except Exception as e:
            print(f"Символьное обратное преобразование не удалось: {e}")
            
            # Если не получилось, пробуем численный метод
            if hasattr(self, 'solver') and self.solver:
                t_vals = np.array([t_val])
                y_vals = self.solver.numeric_inverse_laplace(expr_p, t_vals)
                return float(y_vals[0]) if len(y_vals) > 0 else 0.0
            
            # Резервный вариант для простых случаев
            try:
                # Проверяем, не является ли выражение типа E/p
                if expr_p.is_Mul and len(expr_p.args) == 2:
                    # Ищем символ и деление на p
                    for arg in expr_p.args:
                        if arg == 1/p_sym:
                            # Это E/p
                            const_part = expr_p / (1/p_sym)
                            const_val = float(const_part)
                            # E/p -> E * step(t)
                            return const_val if t_val > 0 else 0.0
            except:
                pass
            
            return 0.0
    
    def _calculate_at_time(self, expr_p, t_val):
        """Вычисление значения во временной области"""
        try:
            # Пробуем символьное обратное преобразование Лапласа
            p_sym = sp.Symbol('p')
            t_sym = sp.Symbol('t', real=True, positive=True)
            
            expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
            expr_t = sp.simplify(expr_t)
            
            # Подставляем время
            result = float(expr_t.subs(t_sym, t_val))
            return result
        except:
            # Если не получается, используем численный метод
            if hasattr(self, 'solver') and self.solver:
                t_vals = np.array([t_val])
                y_vals = self.solver.numeric_inverse_laplace(expr_p, t_vals)
                return float(y_vals[0]) if len(y_vals) > 0 else 0.0
            return 0.0
    
    def _show_numerical_result(self, text):
        """Показ текстового результата с ошибкой"""
        if hasattr(self, 'numerical_result_widget') and self.numerical_result_widget:
            self.num_output_layout.removeWidget(self.numerical_result_widget)
            self.numerical_result_widget.deleteLater()
        
        error_label = QLabel(f"Ошибка: {text}")
        error_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
        self.num_output_layout.addWidget(error_label)
        self.numerical_result_widget = error_label
    
    def _show_numerical_result_formula(self, var_name, t_val, result, unit):
        """Показ результата в виде красивой формулы - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if hasattr(self, 'numerical_result_widget') and self.numerical_result_widget:
            self.num_output_layout.removeWidget(self.numerical_result_widget)
            self.numerical_result_widget.deleteLater()
        
        # Создаем виджет для отображения результата
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        
        # Отображение численного результата
        result_text = QLabel()
        result_text.setStyleSheet("font-size: 14px; font-weight: bold; color: #0066cc;")
        result_value = f"{result:.6g}"
        
        # Форматируем переменную с нижним индексом если есть цифры
        formatted_var = self._format_variable_name(var_name)
        
        if unit:
            result_text.setText(f"{formatted_var}({t_val:.3f} с) = {result_value} {unit}")
        else:
            result_text.setText(f"{formatted_var}({t_val:.3f} с) = {result_value}")
        
        result_text.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(result_text)
        
        self.num_output_layout.addWidget(result_widget)
        self.numerical_result_widget = result_widget
    
    def _format_variable_name(self, var_name):
        """Форматирование имени переменной с нижними индексами"""
        import re
        
        # Функция для замены чисел после букв на нижние индексы
        def replace_numbers(match):
            letter = match.group(1)
            numbers = match.group(2)
            return f"{letter}<sub>{numbers}</sub>"
        
        # Ищем буквы с последующими цифрами - добавляем все возможные буквы
        # Включаем латинские, кириллические и греческие символы
        pattern = r'([A-Za-zА-Яа-яωφ])(\d+)'
        formatted = re.sub(pattern, replace_numbers, var_name)
        
        # Если нет совпадений, проверяем формат с подчеркиванием
        if formatted == var_name and '_' in var_name:
            parts = var_name.split('_')
            if len(parts) == 2 and parts[1].isdigit():
                return f"{parts[0]}<sub>{parts[1]}</sub>"
        
        return formatted

    def clear_all(self):
        """Очистка всех отображаемых результатов и внутреннего состояния"""
        while self.sym_layout.count():
            item = self.sym_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        while self.num_output_layout.count():
            item = self.num_output_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if hasattr(self, 'numerical_result_widget') and self.numerical_result_widget:
            self.numerical_result_widget.deleteLater()
            self.numerical_result_widget = None
        
        while self.params_form.count():
            self.params_form.removeRow(0)
        
        self.plot_widget.ax.clear()
        self.plot_widget.canvas.draw()
        
        self.num_var_combo.clear()
        self.plot_var_combo.clear()
        
        self.analysis = None
        self.solver = None
        self.param_widgets.clear()
        self.var_list = []

    def display_results(self, analysis_result, solver=None):
        """Отображение результатов анализа цепи"""
        self.clear_all()

        self.solver = solver
        self.analysis = analysis_result

        if not analysis_result:
            error_label = QLabel("Результаты анализа недоступны.")
            self.sym_layout.addWidget(error_label)
            return

        if "error" in analysis_result:
            error_label = QLabel(f"Ошибка: {analysis_result['error']}")
            error_label.setStyleSheet("color: red;")
            self.sym_layout.addWidget(error_label)
            return

        symbolic = analysis_result.get("symbolic", {}) or {}
        X_sym = symbolic.get("X")
        var_symbols = symbolic.get("vars", [])
        net_elems = symbolic.get("net_elems", [])

        # Отображаем только решения X(p)
        if X_sym is not None and var_symbols:
            # Определяем описания для переменных
            var_descriptions = self._get_variable_descriptions(var_symbols, net_elems)
            
            for i, var_symbol in enumerate(var_symbols):
                equation = sp.Eq(var_symbol, X_sym[i])
                var_name = str(var_symbol)
                desc = var_descriptions.get(var_name, f"Решение {i+1}")
                
                self.sym_layout.addWidget(FormulaCanvas(equation, desc))
        else:
            error_label = QLabel("Символьное решение не может быть вычислено.")
            self.sym_layout.addWidget(error_label)

        # --- Настройка вкладки численного анализа ---
        params = analysis_result.get("params", [])
        self.param_widgets = {}

        if params:
            for p in params:
                pname = p.get("name")
                default = p.get("default", 0.0)
                desc = p.get("desc", "")
                spin = QDoubleSpinBox()
                spin.setDecimals(6)
                spin.setRange(-1e12, 1e12)
                spin.setValue(float(default))
                spin.setMaximumWidth(160)
                spin.valueChanged.connect(self._on_param_changed)
                self.params_form.addRow(f"{pname} ({desc})", spin)
                self.param_widgets[pname] = spin
                self.last_param_values[pname] = float(default)

        # Начальные условия
        self.initial_current = QDoubleSpinBox()
        self.initial_current.setDecimals(6)
        self.initial_current.setRange(-1e6, 1e6)
        self.initial_current.setValue(0.0)
        self.initial_current.valueChanged.connect(self._on_param_changed)

        self.initial_voltage = QDoubleSpinBox()
        self.initial_voltage.setDecimals(6)
        self.initial_voltage.setRange(-1e6, 1e6)
        self.initial_voltage.setValue(0.0)
        self.initial_voltage.valueChanged.connect(self._on_param_changed)

        self.params_form.addRow("Начальный ток I₀ (А):", self.initial_current)
        self.params_form.addRow("Начальное напряжение V₀ (В):", self.initial_voltage)

        # Выбор переменной
        self.var_list = [str(v) for v in var_symbols]
        self.num_var_combo.clear()
        self.plot_var_combo.clear()
        
        if self.var_list:
            for v in self.var_list:
                self.num_var_combo.addItem(v)
                self.plot_var_combo.addItem(v)
        else:
            self.num_var_combo.addItem("Нет переменных")
            self.plot_var_combo.addItem("Нет переменных")

        self._on_param_changed()

    def _get_variable_descriptions(self, var_symbols, net_elems):
        """Получение описаний для переменных"""
        descriptions = {}
        
        for var in var_symbols:
            var_str = str(var)
            
            # Напряжения узлов
            if var_str.startswith('U_'):
                node_num = var_str[2:] if len(var_str) > 2 else "?"
                descriptions[var_str] = f"Напряжение узла U<sub>{node_num}</sub>:"
            # Ток через источник напряжения
            elif var_str.startswith('I_E'):
                source_num = var_str[3:] if len(var_str) > 3 else "1"
                descriptions[var_str] = f"Ток через источник напряжения I<sub>E{source_num}</sub>:"
            # Ток через катушку индуктивности
            elif var_str.startswith('I_L'):
                l_num = var_str[3:] if len(var_str) > 3 else "1"
                descriptions[var_str] = f"Ток через катушку индуктивности I<sub>L{l_num}</sub>:"
            # Общий случай - ищем буквы с цифрами
            else:
                import re
                # Ищем латинские буквы, кириллицу и греческие символы с цифрами
                match = re.match(r'([A-Za-zА-Яа-яωφ]+)(\d+)', var_str)
                if match:
                    letter = match.group(1)
                    number = match.group(2)
                    
                    if letter == 'I':
                        descriptions[var_str] = f"Ток I<sub>{number}</sub>:"
                    elif letter == 'U':
                        descriptions[var_str] = f"Напряжение U<sub>{number}</sub>:"
                    elif letter == 'E':
                        descriptions[var_str] = f"ЭДС E<sub>{number}</sub>:"
                    elif letter == 'L':
                        descriptions[var_str] = f"Ток через катушку L<sub>{number}</sub>:"
                    elif letter == 'C':
                        descriptions[var_str] = f"Напряжение на конденсаторе C<sub>{number}</sub>:"
                    elif letter == 'R':
                        descriptions[var_str] = f"Ток через резистор R<sub>{number}</sub>:"
                    else:
                        descriptions[var_str] = f"Переменная {letter}<sub>{number}</sub>:"
                else:
                    descriptions[var_str] = f"Переменная {var_str}:"
        
        return descriptions

    def _on_param_changed(self):
        """Обработка изменения параметров"""
        if hasattr(self, 'operator_solution_widget') and self.operator_solution_widget:
            self.num_output_layout.removeWidget(self.operator_solution_widget)
            self.operator_solution_widget.deleteLater()
            self.operator_solution_widget = None

        # Сохраняем текущие значения
        self.initial_conditions = {
            "I0": float(self.initial_current.value()) if hasattr(self, 'initial_current') else 0.0,
            "V0": float(self.initial_voltage.value()) if hasattr(self, 'initial_voltage') else 0.0
        }

    def on_build_plot(self):
        """Построение графика временной зависимости"""
        if not self.analysis:
            QMessageBox.warning(self, "Ошибка", "Нет результатов анализа для построения графика.")
            return

        symbolic = self.analysis.get("symbolic", {})
        X_sym = symbolic.get("X")
        var_list = symbolic.get("vars", [])

        if X_sym is None or not var_list:
            QMessageBox.warning(self, "Ошибка", "Символьное решение недоступно для построения графика.")
            return

        var_name = self.plot_var_combo.currentText()
        if not var_name or var_name == "Нет переменных":
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите переменную для построения графика.")
            return

        try:
            var_index = [str(v) for v in var_list].index(var_name)
            expr_p = X_sym[var_index]
        except (ValueError, IndexError):
            QMessageBox.warning(self, "Ошибка", f"Переменная '{var_name}' не найдена в решении.")
            return

        # Подстановка численных значений
        subs_dict = {}
        for name, widget in self.param_widgets.items():
            try:
                subs_dict[sp.Symbol(name)] = float(widget.value())
            except:
                pass
        
        # Добавляем начальные условия
        if hasattr(self, 'initial_current'):
            subs_dict[sp.Symbol('I0')] = float(self.initial_current.value())
        if hasattr(self, 'initial_voltage'):
            subs_dict[sp.Symbol('V0')] = float(self.initial_voltage.value())
        
        expr_p_numeric = expr_p.subs(subs_dict)

        # Параметры времени
        t_start = max(1e-6, self.time_start.value())
        t_end = self.time_end.value()
        n_points = self.points_count.value()
        
        t_vals = np.linspace(t_start, t_end, n_points)
        
        try:
            # Вычисляем значения для каждого момента времени
            y_vals = np.zeros_like(t_vals)
            
            # Проверяем, является ли выражение AC сигналом
            expr_str = str(expr_p_numeric)
            is_ac = 'omega' in expr_str and ('p**2' in expr_str or 'p**2' in str(expr_p_numeric))
            
            if is_ac:
                # Для AC сигнала используем специализированную обработку
                print("Обнаружен AC сигнал, используем улучшенную обработку")
                
                # Пытаемся получить символьное выражение во временной области
                p_sym = sp.Symbol('p')
                t_sym = sp.Symbol('t', real=True, positive=True)
                
                try:
                    # Пробуем символьное обратное преобразование
                    expr_t = sp.inverse_laplace_transform(expr_p_numeric, p_sym, t_sym, noconds=True)
                    expr_t = sp.simplify(expr_t)
                    
                    # Убираем Heaviside, так как t>0
                    if expr_t.has(sp.Heaviside):
                        expr_t = expr_t.replace(sp.Heaviside(t_sym), 1)
                    
                    # Создаем функцию
                    func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                    y_vals = func_t(t_vals)
                    
                except Exception as e:
                    print(f"Символьное преобразование AC не удалось: {e}")
                    # Используем численный метод для каждой точки
                    for i, t in enumerate(t_vals):
                        y_vals[i] = self._calculate_time_domain_value(expr_p_numeric, t)
            else:
                # Для DC сигнала используем стандартную обработку
                for i, t in enumerate(t_vals):
                    y_vals[i] = self._calculate_time_domain_value(expr_p_numeric, t)
            
            # Обработка численных проблем
            y_vals = np.nan_to_num(y_vals, nan=0.0, posinf=1e10, neginf=-1e10)
            
            # Определение единицы измерения для оси Y
            if var_name.upper().startswith('I'):
                yunit = "А"
            elif var_name.upper().startswith('V') or var_name.upper().startswith('U'):
                yunit = "В"
            else:
                yunit = ""
            
            # Построение графика
            self.plot_widget.plot(t_vals, y_vals,
                                title=f"Временная зависимость {var_name}(t)",
                                xlabel="Время (с)",
                                ylabel=var_name,
                                yunit=yunit)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка построения графика",
                            f"Не удалось построить график.\nОшибка: {str(e)}")