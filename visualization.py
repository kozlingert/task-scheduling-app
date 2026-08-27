import networkx as nx
import plotly.graph_objects as go
import plotly.colors as pc

HORIZONTAL_SPACING = 3.5
VERTICAL_SPACING = 2.5



def compute_node_levels(dag):
    levels = {}

    for node in nx.topological_sort(dag):
        predecessors = list(dag.predecessors(node))

        if not predecessors:
            levels[node] = 0
        else:
            levels[node] = max(levels[p] for p in predecessors) + 1

    return levels

def create_dag_coords(levels):
    grouped_nodes = {}

    for node, level in levels.items():
        grouped_nodes.setdefault(level, []).append(node) 

    coords = {}

    for level, nodes in grouped_nodes.items():
        nodes_num = len(nodes)
        upper_y = ((nodes_num - 1) * VERTICAL_SPACING / 2)

        for i, node in enumerate(nodes):
            x = level * HORIZONTAL_SPACING
            y = upper_y - i * VERTICAL_SPACING
            coords[node] = (x, y)

    return coords, grouped_nodes



def quadratic_bezier_curve(p0, control, p2, points_num=40):
    coords = []

    for i in range(points_num + 1):
        t = i / points_num
        x = ( (1-t)**2*p0[0] + 2*(1-t)*t*control[0] + t**2*p2[0]  )
        y = ( (1-t)**2*p0[1] + 2*(1-t)*t*control[1] + t**2*p2[1]  )

        coords.append((x,y))

    return coords

def compute_edges(u, v, node_coords, levels, grouped_nodes):
    x0, y0 = node_coords[u]
    x2, y2 = node_coords[v]

    mid_x = (x0 + x2) / 2
    mid_y = (y0 + y2) / 2

    level_diff = levels[v] - levels[u]

    if level_diff > 1:
        beetween_levels = range(levels[u] +1, levels[v])
        beetween_ys = [
            node_coords[n][1]
            for lvl in beetween_levels
            for n in grouped_nodes.get(lvl, [])
        ]

        if beetween_ys:
            avg_beetween_y = sum(beetween_ys) / len(beetween_ys)
            direction = 1 if mid_y >= avg_beetween_y else -1
            max_extent = max(abs(y-mid_y) for y in beetween_ys)
        else:
            direction = 1
            max_extent = VERTICAL_SPACING
        control_y = mid_y + (max_extent + VERTICAL_SPACING * 0.6) * direction
    else:
        control_y = mid_y
    edge_coords = quadratic_bezier_curve( (x0, y0), (mid_x, control_y), (x2, y2))

    return edge_coords

def trim_edge(edge_coords, trim_distance=0.4):
    cumulative = [0.0]
    for i in range(1, len(edge_coords)):
        dx = edge_coords[i][0] - edge_coords[i-1][0]
        dy = edge_coords[i][1] - edge_coords[i-1][1]
        cumulative.append(cumulative[-1] + (dx**2 + dy**2)**0.5)

    total_length = cumulative[-1]

    safe_trim = min(trim_distance, total_length*0.4)

    start_index = 0
    while cumulative[start_index] < safe_trim:
        start_index += 1

    end_index = len(edge_coords)-1
    while cumulative[-1] - cumulative[end_index] < safe_trim:
        end_index -= 1

    return edge_coords[start_index:end_index+1]


THEME_COLORS = {
    "light": {
        "node_fill": "#F0D9FF",
        "node_border": "#9D4EDD",
        "edge_line": "#B185DB",
        "edge_label_text": "#D6249F",
        "edge_label_bg": "#FFFFFF",
        "cp_node_fill": "#FFCCD5",     
        "cp_node_border": "#FF4D6D",   
        "cp_edge_line": "#FF4D6D",
    },
    "dark": {
        "node_fill": "#7B2CBF",      
        "node_border": "#E0AAFF",
        "edge_line": "#C77DFF",
        "edge_label_text": "#FF8FE3",
        "edge_label_bg": "#262730",  
        "cp_node_fill": "#590D22",     
        "cp_node_border": "#FF4D6D",    
        "cp_edge_line": "#FF4D6D",
    },
}

def create_dag_fig(dag, levels, theme_type="light", critical_path_nodes=None):
    coords, grouped_nodes = create_dag_coords(levels)

    fig = go.Figure()
    colors = THEME_COLORS.get(theme_type, THEME_COLORS["light"])

    if critical_path_nodes is None:
        critical_path_nodes = []


    for u, v, data in dag.edges(data=True):
        edge_coords = compute_edges(u, v, coords, levels, grouped_nodes)
        trimmed_coords = trim_edge(edge_coords)

        x_coords = [p[0] for p in trimmed_coords]
        y_coords = [p[1] for p in trimmed_coords]

        is_cp_edge = (u in critical_path_nodes) and (v in critical_path_nodes)
        edge_color = colors["cp_edge_line"] if is_cp_edge else colors["edge_line"]
        edge_width = 3 if is_cp_edge else 2 


        fig.add_trace(go.Scatter(
            x = x_coords,
            y = y_coords,
            mode="lines",
            line=dict(
                width=edge_width,
                color=edge_color,
                shape="spline"
            ),
            hoverinfo="none",
            showlegend=False
        ))

        arrow_end = trimmed_coords[-1]
        arrow_start = trimmed_coords[-3] if len(trimmed_coords) >= 3 else trimmed_coords[0]

        fig.add_annotation(
            x=arrow_end[0],
            y=arrow_end[1],
            ax=arrow_start[0],
            ay=arrow_start[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.2,
            arrowwidth=2,
            arrowcolor=edge_color
        )

        communication = data["communication"]
        label_point = trimmed_coords[len(trimmed_coords) // 2]
    
        fig.add_annotation(
            x=label_point[0],
            y=label_point[1],
            text=f"c={communication}",
            showarrow=False,
            font=dict(
                size=12,
                color=edge_color
            ),
            bgcolor=colors["edge_label_bg"]
        )


    node_x = []
    node_y = []
    node_text = []
    node_hover = []
    node_fills = []
    node_borders = []

    for node in dag.nodes():

        x, y = coords[node]

        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_hover.append(
            f"Duration: {dag.nodes[node]['duration']}"
        )

        if node in critical_path_nodes:
            node_fills.append(colors["cp_node_fill"])
            node_borders.append(colors["cp_node_border"])
        else:
            node_fills.append(colors["node_fill"])
            node_borders.append(colors["node_border"])


    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition="middle center",
            hovertext=node_hover,
            hoverinfo="text",
            marker=dict(
                size=55,
                color=node_fills,
                line=dict(
                    width=3 if node in critical_path_nodes else 2,
                    color=node_borders
                )
            ),
            showlegend=False
        )
    )


    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False
        )
    )

    return fig




def create_gantt_fig(dag, schedule, pu_num, critical_path_nodes = None):
    fig = go.Figure()
    if critical_path_nodes is None:
        critical_path_nodes = []

    colorscale = [
        [0.0, "#FF8FE3"],
        [0.5, "#C77DFF"],
        [1.0, "#5A189A"],
    ]
    tasks = list(schedule.items())
    if len(tasks) == 1:
        colors = pc.sample_colorscale(colorscale, [0.5])
    else:
        sample_points = [i/(len(tasks)-1) for i in range(len(tasks))]
        colors = pc.sample_colorscale(colorscale, sample_points)

    for (task, data), task_color in zip(tasks, colors):
        start_time = data["start_time"]
        end_time = data["end_time"]
        duration = end_time - start_time

        pu = data["pu"]
        pu_label = f"Processing unit {pu}"

        is_critical = task in critical_path_nodes
        final_color = "#FF4D6D" if is_critical else task_color
        border_color = "#590D22" if is_critical else "#3C096C"
        border_width = 2.5 if is_critical else 1.5

        fig.add_trace(go.Bar(
            x = [duration],
            y = [pu_label],
            base = [start_time],
            orientation='h',
            width=0.3,
            text=f"{duration}",
            textposition="inside",
            marker=dict(
                color=final_color,                       
                line=dict(color=border_color, width=border_width)  
            ),            
            hoverinfo="text",
            hovertext=(
                f"<b>{task}</b><br>"
                f"Start: {start_time}<br>"
                f"End: {end_time}<br>"
                f"Duration: {duration}"
            ),
            showlegend=False         
        ))

    fig.update_layout(
        title="Gantt Chart",
        barmode="overlay",
        xaxis=dict(title=None),
        yaxis=dict(title="Processing Units (PU)",
                   categoryorder="array",
                   categoryarray=[f"PU {i}" for i in range(pu_num)]
                   ),
        margin=dict(b=80)         
    )

    fig.add_annotation(
        text="Time",
        xref="paper",
        yref="paper",
        x=0.45,
        y=-0.18,
        xanchor="center",
        yanchor="top",
        showarrow=False,
        font=dict(size=13)
    )

    return fig

def create_loads_fig(metrics, pu_num, theme_type="light"):
    colors = THEME_COLORS.get(theme_type, THEME_COLORS["light"])
 
    pu_labels = [f"PU {i}" for i in range(pu_num)]
    load_values = [metrics[f"pu_{i}_load"] for i in range(pu_num)]
    max_load = max(load_values) if load_values else 0

    fig = go.Figure(go.Bar(
        x=load_values,
        y=pu_labels,
        orientation="h",
        marker=dict(
            color=colors["node_fill"],
            line=dict(color=colors["node_border"], width=1.5)
        ),
        text=load_values,
        textposition="outside",
        cliponaxis=False
    ))

    fig.update_layout(
        height= 70 + 32 * pu_num,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(pu_labels))
        ),
        xaxis=dict(title=None,
                   range=[0, max_load * 1.2 if max_load > 0 else 1])        
    )    

    return fig