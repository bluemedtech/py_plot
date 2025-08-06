import ast
import tkinter as tk
from tkinter import filedialog, ttk
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
class FunctionAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}
        self.source = ""

    def visit_FunctionDef(self, node):
        func_name = node.name
        args = [arg.arg for arg in node.args.args]

        # Get full source of the function
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.body[-1].lineno if node.body else start_line)
        line_range = self.source.splitlines()[start_line - 1:end_line]

        meaningful_lines = []
        inside_docstring = False

        for line in line_range:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(('"""', "'''")):
                if not inside_docstring:
                    inside_docstring = True
                elif inside_docstring:
                    inside_docstring = False
                continue
            if inside_docstring or stripped.startswith("#"):
                continue
            meaningful_lines.append(line)

        # 🔁 Moved this up here
        call_names = {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

        self.functions[func_name] = {
            'calls': call_names,
            'lines': len(meaningful_lines),
            'args': args
        }

        self.generic_visit(node)

def analyze_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
        tree = ast.parse(source, filename=file_path)
        analyzer = FunctionAnalyzer()
        analyzer.source = source
        analyzer.visit(tree)
        return analyzer.functions



def draw_graph(G, functions):
    fig, ax = plt.subplots(figsize=(9, 7))
    
    # Increase spacing between nodes with a larger 'k'
    pos = nx.spring_layout(G, seed=42, k=2.6 / (len(G.nodes) ** 0.5))
    
    max_lines = max((data['lines'] for data in functions.values()), default=1)
    sizes = [800 + 1200 * (functions[n]['lines'] / max_lines) for n in G.nodes]

    # Draw nodes and edges
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color='skyblue', edgecolors='black', ax=ax)
    nx.draw_networkx_edges(G, pos, arrowstyle='-|>', arrowsize=20, ax=ax)

    # Move labels slightly above the nodes
    label_pos = {k: (v[0], v[1] + 0.1) for k, v in pos.items()}
    nx.draw_networkx_labels(G, label_pos, font_size=6, ax=ax)

    ax.set_title("Function Call Graph", fontsize=12)
    ax.axis('off')
    return fig


def draw_graph_tkinter(canvas, functions, G):
    canvas.delete("all")  # Clear previous drawings

    # Dynamic node sizes based on function line counts
    min_radius = 20
    max_radius = min_radius * 2.5
    min_lines = min((data['lines'] for data in functions.values()), default=1)
    max_lines = max((data['lines'] for data in functions.values()), default=1)

    # Avoid division by zero
    def get_radius(lines):
        if max_lines == min_lines:
            return min_radius
        scale = (lines - min_lines) / (max_lines - min_lines)
        return min_radius + scale * (max_radius - min_radius)



    spacing_x, spacing_y = 160, 120

    # Compute grid layout
    positions = {}
    for idx, node in enumerate(G.nodes):
        row = idx // 4
        col = idx % 4
        x = 100 + col * spacing_x
        y = 100 + row * spacing_y
        positions[node] = [x, y]

    # Store canvas items
    node_items = {}
    text_items = {}
    edge_items = []

    # Draw edges (arrows)
    for src, dst in G.edges:
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        line = canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, width=2)
        edge_items.append((line, src, dst))

    # Draw nodes and labels
    for node, (x, y) in positions.items():
        radius = get_radius(functions[node]['lines'])
        circle = canvas.create_oval(x - radius, y - radius,
                                    x + radius, y + radius,
                                    fill="skyblue", outline="black", width=2, tags=("node", node))
        label = canvas.create_text(x, y - radius - 10, text=node, tags=("label", node), font=("Arial", 9))

        node_items[node] = circle
        text_items[node] = label

    # Drag handlers
    def on_drag_start(event):
        canvas.scan_mark(event.x, event.y)
        canvas._drag_data = canvas.find_withtag("current")[0]

    def on_drag_motion(event):
        item = canvas._drag_data
        tags = canvas.gettags(item)
        if not tags:
            return
        node = tags[1]
        dx = event.x - positions[node][0]
        dy = event.y - positions[node][1]
        positions[node][0] = event.x
        positions[node][1] = event.y

        # Move circle and label
        radius = get_radius(functions[node]['lines'])
        canvas.coords(node_items[node],
                      event.x - radius, event.y - radius,
                      event.x + radius, event.y + radius)
        canvas.coords(text_items[node], event.x, event.y - radius - 10)


        # Redraw arrows
        for line_id, src, dst in edge_items:
            x1, y1 = positions[src]
            x2, y2 = positions[dst]
            canvas.coords(line_id, x1, y1, x2, y2)

    # Bind drag events
    for node in G.nodes:
        canvas.tag_bind(node_items[node], "<ButtonPress-1>", on_drag_start)
        canvas.tag_bind(node_items[node], "<B1-Motion>", on_drag_motion)




def build_graph(functions):
    G = nx.DiGraph()
    for func, data in functions.items():
        G.add_node(func)
        for callee in data['calls']:
            if callee in functions:
                G.add_edge(func, callee)
    return G

def update_ui(file_path, root, frame, listbox, canvas_frame):

    functions = analyze_file(file_path)

    # Update window title with filename and total lines
    filename = os.path.basename(file_path)
    
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
        lines = source.splitlines()
        total_lines = 0
        inside_docstring = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(('"""', "'''")):
                if not inside_docstring:
                    inside_docstring = True
                elif inside_docstring:
                    inside_docstring = False
                continue
            if inside_docstring or stripped.startswith("#"):
                continue
            total_lines += 1



    
    root.title(f"{filename} - Total Lines: {total_lines}")

    # Sort functions by number of lines (descending)
    sorted_funcs = sorted(functions.items(), key=lambda x: x[1]['lines'], reverse=True)

    listbox.delete(0, tk.END)
    for name, data in sorted_funcs:
        args = ", ".join(data['args'])
        listbox.insert(tk.END, f"[{data['lines']}] {name}({args})")

    for widget in canvas_frame.winfo_children():
        widget.destroy()

    canvas = tk.Canvas(canvas_frame, bg="white")
    canvas.pack(fill=tk.BOTH, expand=True)
    G = build_graph(functions)
    draw_graph_tkinter(canvas, functions, G)


def choose_file(root, listbox, canvas_frame):
    file_path = filedialog.askopenfilename(title="Select a Python file", filetypes=[("Python files", "*.py")])
    if file_path:
        update_ui(file_path, root, root, listbox, canvas_frame)

def main():
    root = tk.Tk()
    root.title("Python Function Analyzer")
    root.geometry("1000x700")

    left_frame = tk.Frame(root, width=300)
    left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

    tk.Label(left_frame, text="Functions & Args").pack()
    listbox = tk.Listbox(left_frame, width=40, height=30)
    listbox.pack(fill=tk.Y, expand=True)

    btn_frame = tk.Frame(left_frame)
    btn_frame.pack(pady=10)

    browse_btn = tk.Button(btn_frame, text="Browse", command=lambda: choose_file(root, listbox, right_frame))

    browse_btn.grid(row=0, column=0, padx=5)

    exit_btn = tk.Button(btn_frame, text="Exit", command=root.quit)
    exit_btn.grid(row=0, column=1, padx=5)

    right_frame = tk.Frame(root)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
