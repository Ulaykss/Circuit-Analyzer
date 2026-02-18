import sympy as sp
import numpy as np
from collections import defaultdict

class CircuitSolver:
    """Класс для анализа электрических цепей методом узловых напряжений"""
    
    def __init__(self, scene):
        self.scene = scene
        self.t = sp.symbols('t')  # Временная переменная
        self.p = sp.symbols('p')   # Переменная Лапласа
        self.source_type = "DC"  # Тип источника напряжения по умолчанию (DC - постоянный)
        self.source_params = {}   # Параметры для разных типов источников
        
        # Символьные переменные для синусоидального источника
        self.A = sp.Symbol('A', real=True, positive=True)  # Амплитуда
        self.omega = sp.Symbol('omega', real=True, positive=True)  # Угловая частота
        self.phi = sp.Symbol('phi', real=True)  # Начальная фаза
        
    def set_source_type(self, source_type, params=None):
        """Установка типа источника напряжения
        
        Args:
            source_type (str): "DC" - постоянный, "AC" - синусоидальный
            params (dict): Параметры для AC источника:
                          - amplitude: амплитуда (число или символ)
                          - frequency: частота (рад/с) (число или символ)
                          - phase: начальная фаза (рад) (число или символ)
        """
        self.source_type = source_type
        if params:
            self.source_params = params
        else:
            self.source_params = {}

    def analyze_circuit(self):
        """Основной метод анализа цепи: MNA в операторной форме"""
        elements = self._get_circuit_elements()
        wires = self._get_wires()
        if not elements:
            return {"error": "Нет элементов в схеме"}

        # Построение списка соединений
        node_of_terminal, node_count, ground, net_elems = self._build_netlist(elements, wires)
        if node_count <= 0:
            return {"error": "В схеме нет узлов"}

        # Сборка символьных MNA матриц
        A_sym, Z_sym, var_list, net_elems_sym = self._assemble_mna_operator_form(node_count, ground, net_elems)

        if A_sym is None:
            return {"error": "Не удалось собрать матрицы MNA"}

        # Символьное решение: X(p) = A(p)^{-1} * Z(p)
        try:
            if A_sym.det() != 0:
                # Решаем систему
                X_sym = A_sym.LUsolve(Z_sym)
                
                # Упрощаем и факторизуем
                X_simplified = []
                for i, expr in enumerate(X_sym):
                    # Упрощаем выражение
                    expr_simple = sp.simplify(expr)
                    
                    # Пытаемся факторизовать для более красивого вида
                    try:
                        # Для дробей: приводим к общему знаменателю
                        expr_together = sp.together(expr_simple)
                        X_simplified.append(expr_together)
                    except:
                        X_simplified.append(expr_simple)
                
                X_sym_final = sp.Matrix(X_simplified)
                X_sym_final = -X_sym_final
                    
            else:
                X_sym_final = None
                return {"error": "Матрица системы сингулярна, решение не существует"}
                
        except Exception as e:
            X_sym_final = None
            return {"error": f"Ошибка решения системы: {e}"}

        # Формирование вывода
        pretty = "Символьный анализ цепи:\n"
        pretty += "Переменные: " + ", ".join(str(v) for v in var_list) + "\n\n"
        
        if X_sym_final is not None:
            # Создаем уравнения для каждой переменной
            equations = []
            for i, var in enumerate(var_list):
                eq = sp.Eq(var, X_sym_final[i])
                equations.append(eq)
                pretty += f"{sp.pretty(eq)}\n\n"
        else:
            pretty += "Символьное решение недоступно\n\n"
            equations = None

        # Построение списка параметров для численного анализа
        params = []
        symbols = {}
        
        for el in net_elems_sym:
            param_name = el.get('param_name', '')
            if not param_name:
                continue
                
            sym = el['value_sym']
            default = el.get('raw', 0.0)
            
            # Определяем описание элемента
            desc_map = {
                'R': "Сопротивление (Ом)",
                'R1': "Сопротивление (Ом)",
                'C': "Емкость (Ф)",
                'C1': "Емкость (Ф)",
                'L': "Индуктивность (Гн)",
                'L1': "Индуктивность (Гн)",
                'E': "ЭДС источника (В)",
                'E1': "ЭДС источника (В)",
                'K': "Рубильник",
                'K1': "Рубильник"
            }
            desc = desc_map.get(param_name, param_name)
            
            params.append({"name": param_name, "symbol": str(sym), "default": default, "desc": desc})
            symbols[param_name] = sym

        # Добавляем параметры источника в зависимости от типа
        if self.source_type == "AC":
            params.append({
                "name": "A", 
                "symbol": "A", 
                "default": self.source_params.get('amplitude', 1.0), 
                "desc": "Амплитуда ЭДС (В)"
            })
            params.append({
                "name": "ω", 
                "symbol": "omega", 
                "default": self.source_params.get('frequency', 100.0), 
                "desc": "Угловая частота (рад/с)"
            })
            params.append({
                "name": "φ", 
                "symbol": "phi", 
                "default": self.source_params.get('phase', 0.0), 
                "desc": "Начальная фаза (рад)"
            })
            symbols['A'] = self.A
            symbols['omega'] = self.omega
            symbols['phi'] = self.phi

        symbolic_section = {
            "X": X_sym_final,
            "vars": var_list,
            "net_elems": net_elems_sym,
            "equations": equations,
            "matrix_A": A_sym,
            "vector_Z": Z_sym,
            "pretty": pretty,
            "source_type": self.source_type
        }

        return {
            "type": "MNA_operator",
            "symbolic": symbolic_section,
            "params": params,
            "symbols": symbols
        }

    def simulate(self, analysis_result, param_values, t_end=1.0, n_points=200, variable="I"):
        """Численное моделирование на основе символьного решения"""
        if not analysis_result or "symbolic" not in analysis_result:
            return {"error": "Нет данных анализа"}

        sym = analysis_result["symbolic"]
        X_sym = sym.get("X")
        var_list = sym.get("vars")
        source_type = sym.get("source_type", "DC")

        if X_sym is None:
            return {"error": "Отсутствует символьное решение для моделирования."}

        # Построение карты подстановки параметров
        subs = {}
        
        for el in sym.get("net_elems", []):
            param_name = el.get('param_name')
            sym_el = el['value_sym']
            if param_name and param_name in param_values:
                subs[sym_el] = float(param_values[param_name])
            else:
                raw = el.get('raw', None)
                if raw is not None:
                    subs[sym_el] = float(raw)
        
        if source_type == "AC":
            if 'A' in param_values:
                subs[self.A] = float(param_values['A'])
            if 'ω' in param_values:
                subs[self.omega] = float(param_values['ω'])
            if 'φ' in param_values:
                subs[self.phi] = float(param_values['φ'])

        # Выбор переменной для вывода
        sel_index = 0
        var_name = str(variable)
        for idx, v in enumerate(var_list):
            if str(v) == var_name:
                sel_index = idx
                break

        try:
            expr_p = X_sym[sel_index].subs(subs)
            
            t_sym = sp.Symbol('t')
            p_sym = self.p
            
            expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
            expr_t = sp.simplify(expr_t)
            
            t = np.linspace(1e-6, float(t_end), int(n_points))
            
            if expr_t.is_number:
                y = np.full_like(t, float(expr_t))
            elif expr_t.has(sp.Heaviside):
                func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                y = func_t(t)
            else:
                func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                y = func_t(t)
            
            y = np.nan_to_num(y, nan=0.0, posinf=1e10, neginf=-1e10)
            
            return {
                "t": t, 
                "y": y, 
                "expr_t": expr_t,
                "expr_p": expr_p,
                "variable": var_name
            }
            
        except Exception as e:
            return {"error": f"Ошибка моделирования: {e}"}

    def _get_circuit_elements(self):
        return [item for item in self.scene.items() if hasattr(item, 'element_type')]

    def _get_wires(self):
        return [item for item in self.scene.items() if hasattr(item, 'start_item') and hasattr(item, 'end_item')]

    def _build_netlist(self, elements, wires):
        terminal_keys = []
        for elem in elements:
            try:
                terms = list(elem.get_terminals().keys())
            except Exception:
                terms = []
            for coord in terms:
                terminal_keys.append((elem, tuple(coord)))

        parent = {tk: tk for tk in terminal_keys}
        
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for w in wires:
            if getattr(w, 'start_item', None) is None or getattr(w, 'end_item', None) is None:
                continue
            a = (w.start_item, tuple(w.start_terminal))
            b = (w.end_item, tuple(w.end_terminal))
            if a in parent and b in parent:
                union(a, b)

        roots = {}
        node_of_terminal = {}
        node_id = 0
        
        for tk in terminal_keys:
            r = find(tk)
            if r not in roots:
                roots[r] = node_id
                node_id += 1
            node_of_terminal[tk] = roots[r]

        ground_node = None
        for (elem, coord), idx in node_of_terminal.items():
            if getattr(elem, 'element_type', '') == 'Ground':
                ground_node = idx
                break
        
        if ground_node is None:
            ground_node = 0

        net_elems = []
        el_counts = defaultdict(int)
        
        for elem in elements:
            typ = elem.element_type
            if typ not in ['Resistor', 'Capacitor', 'Inductor', 'Voltage Source', 'Current Source', 'Switch']:
                continue
                
            el_counts[typ] += 1
            
            try:
                terms = list(elem.get_terminals().keys())
            except Exception:
                terms = []
            
            nodes = []
            for term in terms[:2]:
                tk = (elem, tuple(term))
                nodes.append(node_of_terminal.get(tk))
            
            n1 = nodes[0] if len(nodes) > 0 else None
            n2 = nodes[1] if len(nodes) > 1 else None
            
            if typ == "Resistor":
                sym = sp.Symbol(f"R{el_counts[typ]}")
                raw = elem.properties.get("Resistance", 1000.0)
                net_elems.append({
                    "type": "R", "n1": n1, "n2": n2, 
                    "value_sym": sym, "raw": raw, "owner": elem,
                    "param_name": f"R{el_counts[typ]}"
                })
            elif typ == "Capacitor":
                sym = sp.Symbol(f"C{el_counts[typ]}")
                raw = elem.properties.get("Capacitance", 1e-6)
                net_elems.append({
                    "type": "C", "n1": n1, "n2": n2,
                    "value_sym": sym, "raw": raw, "owner": elem,
                    "param_name": f"C{el_counts[typ]}"
                })
            elif typ == "Inductor":
                sym = sp.Symbol(f"L{el_counts[typ]}")
                raw = elem.properties.get("Inductance", 1e-3)
                net_elems.append({
                    "type": "L", "n1": n1, "n2": n2,
                    "value_sym": sym, "raw": raw, "owner": elem,
                    "param_name": f"L{el_counts[typ]}"
                })
            elif typ == "Voltage Source":
                sym = sp.Symbol(f"E{el_counts[typ]}")
                raw = elem.properties.get("Voltage", 5.0)
                net_elems.append({
                    "type": "V", "n1": n1, "n2": n2,
                    "value_sym": sym, "raw": raw, "owner": elem,
                    "param_name": f"E{el_counts[typ]}"
                })
            elif typ == "Current Source":
                sym = sp.Symbol(f"I{el_counts[typ]}")
                raw = elem.properties.get("Current", 0.0)
                net_elems.append({
                    "type": "I", "n1": n1, "n2": n2,
                    "value_sym": sym, "raw": raw, "owner": elem,
                    "param_name": f"I{el_counts[typ]}"
                })
            elif typ == "Switch":
                state = elem.properties.get("State", "closed")
                r_closed = elem.properties.get("Resistance_closed", 1e-6)
                r_open = elem.properties.get("Resistance_open", 1e12)
                
                sym = sp.Symbol(f"K{el_counts[typ]}")
                raw = r_closed if state == "closed" else r_open
                
                net_elems.append({
                    "type": "K",
                    "n1": n1, "n2": n2,
                    "value_sym": sym,
                    "raw": raw,
                    "state": state,
                    "r_closed": r_closed,
                    "r_open": r_open,
                    "owner": elem,
                    "param_name": f"K{el_counts[typ]}"
                })

        return node_of_terminal, node_id, ground_node, net_elems

    def _assemble_mna_operator_form(self, node_count, ground, net_elems):
        # ==========================================================
        # 1. Определение уникальных узлов (кроме земли)
        # ==========================================================
        all_nodes = set()
        for elem in net_elems:
            for node in (elem['n1'], elem['n2']):
                if node is not None and node != ground:
                    all_nodes.add(node)

        sorted_nodes = sorted(all_nodes)
        node_map = {node: idx for idx, node in enumerate(sorted_nodes)}
        n_nodes = len(sorted_nodes)

        # ==========================================================
        # 2. Дополнительные переменные
        # ==========================================================
        voltage_sources = [e for e in net_elems if e['type'] == 'V']
        inductors = [e for e in net_elems if e['type'] == 'L']
        
        n_vs = len(voltage_sources)
        n_L = len(inductors)
        N = n_nodes + n_vs + n_L

        if N == 0:
            return None, None, [], net_elems

        A = sp.zeros(N, N)
        Z = sp.zeros(N, 1)

        # ==========================================================
        # 3. Формирование списка переменных
        # ==========================================================
        var_list = []

        # Напряжения узлов - используем U с подчеркиванием
        for node in sorted_nodes:
            var_list.append(sp.Symbol(f"U_{node}"))

        # Токи через источники напряжения - используем I_E
        for i, vs in enumerate(voltage_sources):
            var_list.append(sp.Symbol(f"I_E{i+1}"))

        # Токи через индуктивности - I_L
        for i, ind in enumerate(inductors):
            var_list.append(sp.Symbol(f"I_L{i+1}"))

        # Индексы доп. переменных
        vs_index_map = {id(vs): n_nodes + i for i, vs in enumerate(voltage_sources)}
        L_index_map = {id(ind): n_nodes + n_vs + i for i, ind in enumerate(inductors)}

        # ==========================================================
        # 4. Штамповка элементов
        # ==========================================================
        for elem in net_elems:
            typ = elem['type']
            n1 = elem['n1']
            n2 = elem['n2']
            val = elem['value_sym']

            idx1 = node_map.get(n1) if n1 is not None and n1 != ground else None
            idx2 = node_map.get(n2) if n2 is not None and n2 != ground else None

            if typ == 'R':
                g = 1 / val
                
                if idx1 is not None:
                    A[idx1, idx1] += g
                if idx2 is not None:
                    A[idx2, idx2] += g
                if idx1 is not None and idx2 is not None:
                    A[idx1, idx2] -= g
                    A[idx2, idx1] -= g

            elif typ == 'C':
                Y = val * self.p
                
                if idx1 is not None:
                    A[idx1, idx1] += Y
                if idx2 is not None:
                    A[idx2, idx2] += Y
                if idx1 is not None and idx2 is not None:
                    A[idx1, idx2] -= Y
                    A[idx2, idx1] -= Y

            elif typ == 'L':
                L_idx = L_index_map[id(elem)]
                
                if idx1 is not None:
                    A[idx1, L_idx] += 1
                if idx2 is not None:
                    A[idx2, L_idx] -= 1
                
                if idx1 is not None:
                    A[L_idx, idx1] += 1
                if idx2 is not None:
                    A[L_idx, idx2] -= 1
                
                A[L_idx, L_idx] -= val * self.p

            elif typ == 'V':
                vs_idx = vs_index_map[id(elem)]
                
                # Полярность: положительный вывод - n1, отрицательный - n2
                pos_node = n1
                neg_node = n2
                
                pos_idx = node_map.get(pos_node) if pos_node is not None and pos_node != ground else None
                neg_idx = node_map.get(neg_node) if neg_node is not None and neg_node != ground else None
                
                # Вклад тока источника в узловые уравнения
                if pos_idx is not None:
                    A[pos_idx, vs_idx] += 1  # ток вытекает из положительного узла
                if neg_idx is not None:
                    A[neg_idx, vs_idx] -= 1  # ток втекает в отрицательный узел
                
                # Дополнительное уравнение: U_pos - U_neg = E(p)
                if pos_idx is not None:
                    A[vs_idx, pos_idx] += 1
                if neg_idx is not None:
                    A[vs_idx, neg_idx] -= 1
                
                # Правильная форма для AC источника
                if self.source_type == "DC":
                    # Постоянный источник: U(p) = E / p
                    Z[vs_idx] = val / self.p
                elif self.source_type == "AC":
                    # Синусоидальный источник: A·sin(ωt + φ)
                    # Преобразование Лапласа: A·(ω·cos(φ) + p·sin(φ)) / (p² + ω²)
                    # ИСПРАВЛЕНИЕ: Используем численные значения, если они заданы, иначе символьные
                    use_symbolic = self.source_params.get('use_symbolic', True)
                    
                    if use_symbolic:
                        # Символьная форма
                        Z[vs_idx] = self.A * (self.omega * sp.cos(self.phi) + self.p * sp.sin(self.phi)) / (self.p**2 + self.omega**2)
                    else:
                        # Численная форма - подставляем значения
                        A_val = self.source_params.get('amplitude', 1.0)
                        omega_val = self.source_params.get('frequency', 100.0)
                        phi_val = self.source_params.get('phase', 0.0)
                        Z[vs_idx] = A_val * (omega_val * sp.cos(phi_val) + self.p * sp.sin(phi_val)) / (self.p**2 + omega_val**2)
                else:
                    Z[vs_idx] = val / self.p

            elif typ == 'I':
                I_val = val / self.p
                
                if idx1 is not None:
                    Z[idx1] -= I_val
                if idx2 is not None:
                    Z[idx2] += I_val

            elif typ == 'K':
                g = 1 / val
                
                if idx1 is not None:
                    A[idx1, idx1] += g
                if idx2 is not None:
                    A[idx2, idx2] += g
                if idx1 is not None and idx2 is not None:
                    A[idx1, idx2] -= g
                    A[idx2, idx1] -= g

        return A, Z, var_list, net_elems

    def inverse_laplace_numeric(self, expr_p, t_vals):
        p_sym = self.p
        t_sym = sp.Symbol('t')
        
        try:
            expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
            expr_t = sp.simplify(expr_t)
            
            if expr_t.is_number:
                return np.full_like(t_vals, float(expr_t))
            else:
                func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                result = func_t(t_vals)
                return np.nan_to_num(result, nan=0.0, posinf=1e10, neginf=-1e10)
                
        except Exception:
            return np.zeros_like(t_vals)

    def numeric_inverse_laplace(self, expr_p, t_vals, sigma=1.0, N=200):
        """
        Численное обратное преобразование Лапласа
        
        ИСПРАВЛЕННАЯ ВЕРСИЯ: Улучшенная обработка AC сигналов
        """
        p_sym = self.p
        t_sym = sp.Symbol('t', real=True, positive=True)
        result = np.zeros_like(t_vals, dtype=float)
        
        # Проверяем, не является ли выражение простым: const/p
        try:
            if expr_p.is_Mul:
                for arg in expr_p.args:
                    if arg == 1/p_sym:
                        # Это выражение вида const/p
                        const_part = expr_p / (1/p_sym)
                        const_val = float(const_part)
                        # const/p -> const * step(t)
                        for i, t in enumerate(t_vals):
                            result[i] = const_val if t > 0 else 0.0
                        return result
        except:
            pass
        
        # Специальная обработка для выражений вида A*omega/(p^2+omega^2) (синус)
        try:
            # Проверяем на форму A*omega/(p^2+omega^2)
            if expr_p.is_Mul:
                # Ищем множители
                for arg in expr_p.args:
                    if arg.is_Pow and arg.base == p_sym and arg.exp == 2:
                        # Это p^2
                        pass
                
                # Пытаемся разложить на части
                expr_str = str(expr_p)
                if 'omega' in expr_str and 'p**2' in expr_str:
                    # Это AC выражение - используем прямое вычисление
                    p_sym = sp.Symbol('p')
                    t_sym = sp.Symbol('t')
                    
                    # Пробуем символьное обратное преобразование с упрощением
                    try:
                        expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
                        expr_t = sp.simplify(expr_t)
                        
                        if expr_t.has(sp.Heaviside):
                            # Убираем Heaviside, так как t>0
                            expr_t = expr_t.replace(sp.Heaviside(t_sym), 1)
                        
                        # Создаем функцию
                        func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                        result = func_t(t_vals)
                        result = np.nan_to_num(result, nan=0.0, posinf=1e10, neginf=-1e10)
                        return result
                    except:
                        pass
        except:
            pass
        
        # Пробуем символьное преобразование
        try:
            expr_t = sp.inverse_laplace_transform(expr_p, p_sym, t_sym, noconds=True)
            expr_t = sp.simplify(expr_t)
            
            if expr_t.has(sp.Heaviside):
                # Убираем Heaviside, так как t>0
                expr_t = expr_t.replace(sp.Heaviside(t_sym), 1)
            
            if expr_t.is_number:
                const_val = float(expr_t)
                return np.full_like(t_vals, const_val)
            else:
                func_t = sp.lambdify(t_sym, expr_t, 'numpy')
                result = func_t(t_vals)
                return np.nan_to_num(result, nan=0.0, posinf=1e10, neginf=-1e10)
        except Exception:
            pass
        
        # Если не получилось, используем численный метод
        for i, t in enumerate(t_vals):
            if t <= 0:
                result[i] = 0.0
                continue
            
            try:
                sum_real = 0.0
                delta_theta = 2 * np.pi / N
                
                for k in range(N):
                    theta = -np.pi + (k + 0.5) * delta_theta
                    z = sigma + 1j * theta / t
                    
                    weight = np.exp(1j * theta) * (sigma + 1j * theta * np.cos(theta) / t + 1j * sigma * np.sin(theta) / t)
                    
                    try:
                        F_z = complex(expr_p.subs(p_sym, z))
                        sum_real += np.real(weight * F_z)
                    except:
                        continue
                
                result[i] = np.exp(sigma * t) / t * sum_real / N
                
            except Exception:
                result[i] = 0.0
        
        return result