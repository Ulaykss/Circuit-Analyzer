# ⚡ Circuit Analyzer

> **An interactive desktop simulator for linear electric circuits based on the Laplace transform.**

---

## 📖 Description

**Circuit Analyzer** is a Python desktop application that bridges the gap between circuit theory and hands-on analysis. It lets you draw an electrical schematic using a drag-and-drop interface, then automatically derives symbolic equations in the operator (Laplace) domain, computes numerical values, and plots transient responses — all without manual algebraic manipulation.

**Why does it exist?**
Analyzing RLC circuits with inductors, capacitors, and resistors by hand requires solving systems of integro-differential equations, which is tedious and error-prone. Circuit Analyzer automates exactly that pipeline:

1. Build a schematic visually.
2. Get symbolic equations in the Laplace domain instantly.
3. Evaluate any variable numerically at a chosen moment in time.
4. Plot the full transient waveform.

**How it works under the hood:**
The solver uses **Modified Nodal Analysis (MNA)** in operator form — the same method used by industrial SPICE simulators. Passive elements are replaced by their operator impedances (`R`, `Lp`, `1/Cp`), and the resulting matrix equation `A(p)·X(p) = Z(p)` is solved symbolically via **SymPy**. The inverse Laplace transform is then applied analytically (where possible) or numerically via FFT-based methods to recover the time-domain signal.

---

## 🎯 Usage Examples

### 🔋 Scenario 1 — Simple RLC Series Circuit
Place a **Voltage Source**, **Resistor**, **Inductor**, and **Capacitor** in series. Hit **Analyse** to get the symbolic expression for current `I(p)` and plot the transient response showing whether the circuit is over-, under-, or critically damped.

### 🔀 Scenario 2 — Parallel RC Branch
Connect a capacitor and resistor in parallel, driven by a constant EMF through an inductor. The tool computes node voltages and branch currents symbolically, verifies Kirchhoff's laws automatically, and outputs expressions ready for further analysis.

### 〰️ Scenario 3 — Sinusoidal Source & Switch
Use an AC voltage source with configurable amplitude `A`, angular frequency `ω`, and phase `φ`. Toggle a switch (modelled as a near-zero / near-infinite resistance) to simulate circuit make/break events and observe the resulting transient current waveform.

### 📐 Scenario 4 — Two-Loop Mutual Circuit
Build a two-loop circuit with shared reactive elements (as in classical textbook problems). The MNA engine handles the coupled equations automatically and returns individual loop currents as rational functions of `p`.

---

## 🚀 Installation & Usage

### Prerequisites
- **Python 3.9+**
- pip

### 1. Clone the repository
```bash
git clone https://github.com/Ulaykss/Circuit-Analyzer.git
cd Circuit-Analyzer
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```
Key packages: `PyQt5`, `sympy`, `numpy`, `matplotlib`.

### 3. Run the application
```bash
cd src
python main.py
```
Or, on Windows, run the pre-built executable:
```
dist/main.exe
```

### 4. Build a circuit & analyse
1. **Drag** components from the left panel onto the canvas.
2. **Right-click** a component to rotate, flip, or edit its properties.
3. **Draw wires** by dragging from one terminal (green dot) to another.
4. Open **Settings → Voltage Source Type** to choose DC or AC.
5. Click **Analyse** in the toolbar.
6. Switch between the **Symbolic Analysis**, **Numerical Analysis**, and **Graphs** tabs on the right panel.

### 🎬 Demo Video

> Place your demo video file (`demo.mp4`) in the repository root and embed it below, or link to a YouTube/Vimeo upload:

```
[![Circuit Analyzer Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/68AbTDCaIe0)
```

*To attach a local video on GitHub, upload it directly in a Pull Request comment or Release asset, then paste the generated URL here.*

---

## 🛠️ Technologies Used

| Technology | Role |
|---|---|
| **Python 3.9+** | Core language |
| **PyQt5** | GUI framework (canvas, dialogs, event loop) |
| **SymPy** | Symbolic algebra, LU solve, inverse Laplace transform |
| **NumPy** | Numerical arrays, FFT-based inverse Laplace |
| **Matplotlib** | Transient waveform plots embedded in Qt |
| **JSON** | `.circuit` file format for saving/loading schematics |
| **Union-Find (DSU)** | Netlist topology construction |
| **MNA (Modified Nodal Analysis)** | Core circuit equation assembly |

---

## ✅ Validation

The symbolic results produced by Circuit Analyzer have been verified against analytical solutions from classical electrical engineering problems:

- **Example 1 (RLC series, DC source):** The operator expression for source current `I_E1` matches the hand-derived result exactly (up to a common factor of `C₁` before simplification).
- **Task №70 (RL circuit, sinusoidal source with switch):** The program outputs a generalized expression valid for arbitrary switch resistance `K₁`. Taking the limit `K₁ → ∞` (open switch) reproduces the textbook formula identically:

$$i(p) = \frac{u_0(\omega\cos\psi + p\sin\psi)}{(p^2 + \omega^2)(Lp + R_1 + R_2)}$$

Both cases confirm that the MNA engine, symbolic solver, and operator-form source models work correctly.

---

## ⚠️ Known Limitations & Contribution Ideas

The project is functional but has room for improvement. Here are concrete areas where **your contribution would be welcome**:

### 🐢 Performance
- Python's interpreted nature makes analysis of complex multi-loop circuits noticeably slow.
- **Idea:** Implement the MNA matrix assembly and LU solver as a native shared library (`dll` / `.so`) in **C or C++**, called from Python via `ctypes` or `cffi`. This could yield a **10–100× speedup** for large netlists.

### 🔢 Numerical inverse Laplace
- The current FFT-based method (Tallon–Stieltjes) can be inaccurate for stiff systems or very long time windows.
- **Idea:** Integrate the **Weeks method** or **de Hoog algorithm** for more robust numerical inversion.

### 📦 Component library
- Currently supports R, L, C, voltage source, and switch only.
- **Idea:** Add current sources, dependent sources (VCVS, CCCS), transformers, and transmission lines.

### 💾 Export
- Simulation results cannot be saved.
- **Idea:** Add export to CSV / PDF report, and SPICE netlist export for cross-validation with LTspice.

### 🧪 Unit tests
- The codebase lacks automated tests.
- **Idea:** Add a `tests/` directory with `pytest` cases covering netlist construction, MNA stamping, and known analytical solutions.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Authors & Contacts

**Yaroslav Obukhov** — developer, author of the bachelor's thesis underlying this project.

[![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:yaroslav.obuxov@gmail.com)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/ulaykss)
[![VK](https://img.shields.io/badge/VK-0077FF?style=for-the-badge&logo=vk&logoColor=white)](https://vk.com/ulaykss)

> Replace the placeholder links above with your actual contact details.

---

<p align="center">
  Made with ❤️ and lots of Laplace transforms &nbsp;·&nbsp; Irkutsk State University, 2026
</p>
