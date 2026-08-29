import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from scheduling import load_dag, AVAILABLE_HEURISTICS, calculate_metrics
from visualization import compute_node_levels, create_dag_fig, create_gantt_fig, create_loads_fig


st.set_page_config(
    page_title="Static Task Scheduling & Analysis",
    layout="wide"
)

st.title("Visual Analysis and Comparison of Static Task Schedules")

st.write("Load a directed acyclic graph (DAG) to generate task schedules for an edge" \
" computing cluster. Compare different heuristics through Gantt charts and key performance metrics."
)

theme_type = st.context.theme.type or "light"

if 'scheduling_results' not in st.session_state:
    st.session_state.scheduling_results = None
if 'loaded_dag' not in st.session_state:
    st.session_state.loaded_dag = None
if 'levels' not in st.session_state:
    st.session_state.levels = None
if 'current_dag' not in st.session_state:
    st.session_state.current_dag = None   


st.sidebar.header("Load DAG")
file = st.sidebar.file_uploader('Load a DAG in .json format:', type=["json"])
if file and file != st.session_state.current_dag:
    try:
        dag = load_dag(file)
        st.session_state.current_dag = file
        st.session_state.loaded_dag = dag
        st.session_state.levels = compute_node_levels(dag)
        st.session_state.scheduling_results = None  
    except ValueError as e:
        st.error(f"An error has occured: {e}")
        st.session_state.current_dag = None
        st.session_state.loaded_dag = None
        st.session_state.levels = None


if st.session_state.loaded_dag is not None:
    dag = st.session_state.loaded_dag
    levels = st.session_state.levels

    header_col, toggle_col = st.columns([4, 1])
    with header_col:
        st.subheader("Interactive DAG display")
    with toggle_col:
        show_critical_path = st.toggle("Show critical path", value=False)
    critical_path_nodes = []
    if show_critical_path:
        critical_path_nodes = nx.dag_longest_path(dag, weight="duration")

    dag_fig = create_dag_fig(dag, levels, theme_type, critical_path_nodes)
    st.plotly_chart(
        dag_fig,
        use_container_width=True
    )     


    st.sidebar.markdown("---") 
    st.sidebar.header("Schedule Configuration")

    heuristic_options = list(AVAILABLE_HEURISTICS.keys())
    default_id2 = 1 if len(heuristic_options) > 1 else 0

    selected_heuristic_name1 = st.sidebar.selectbox(
        "Select first scheduling heuristic", 
        options=heuristic_options,
        index=0,
        key="heuristic1"
    )
    selected_heuristic_name2 = st.sidebar.selectbox(
        "Select second scheduling heuristic", 
        options=heuristic_options,
        index=default_id2,
        key="heuristic2"
    )
    pu_num = st.sidebar.number_input(
        "Number of processing units (PU)", 
        min_value=1,
        value=2, 
        step=1)

    selected_heuristics = [selected_heuristic_name1, selected_heuristic_name2]
    st.sidebar.markdown("---") 

    generate_toggle = st.sidebar.button("Generate schedules") 

    if generate_toggle:
        if selected_heuristic_name1 == selected_heuristic_name2:
            st.sidebar.warning("Select different heuristics for comparison!")
            st.stop()

        with st.spinner("Generating schedules..."):
            results = []
            for selected in selected_heuristics:
                StrategyClass = AVAILABLE_HEURISTICS[selected]
                heuristic = StrategyClass(pu_num)
                schedule = heuristic.generate_schedule(dag)
                metrics = calculate_metrics(dag, schedule, pu_num)

                results.append({
                   "name": selected,
                    "schedule": schedule,
                    "metrics": metrics,
                    "pu_num": pu_num
                })
            st.session_state.scheduling_results = results

else:
    st.info("Load a file in the sidebar to begin.")


if st.session_state.scheduling_results is not None:
    st.divider()

    res_header_col, res_toggle_col = st.columns([4, 1])
    with res_header_col:
        st.subheader("Generated Schedules")
    with res_toggle_col:
        show_gantt_cp = st.toggle("Show critical path on Gantt diagrams", value=False, key="gantt_cp_toggle")

    dag = st.session_state.loaded_dag

    for res in st.session_state.scheduling_results:
            selected = res["name"]
            schedule = res["schedule"]
            metrics = res["metrics"]
            res_pu_num = res["pu_num"]
    
            st.markdown(f"#### {selected}")

            cp_nodes_for_gantt = metrics["critical_path_nodes"] if show_gantt_cp else None

            fig = create_gantt_fig(dag, schedule, res_pu_num, cp_nodes_for_gantt)
            st.plotly_chart(fig,
                             use_container_width=True,
                             key=f"gantt_{selected}"
                             )    

            st.markdown("""
                <style>
                [data-testid="stMetric"] {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }
                [data-testid="stMetricLabel"] {
                    width: 100%;
                    display: flex;
                    justify-content: center;
                }
                [data-testid="stMetricValue"] {
                    width: 100%;
                    display: flex;
                    justify-content: center;
                }
                </style>
            """, unsafe_allow_html=True)

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Makespan", f"{metrics["makespan"]} units")
            with col_m2:
                st.metric("Critical path", f"{metrics["critical_path_length"]} units")
            with col_m3:
                st.metric("Total comm. cost", f"{metrics["total_communication_cost"]} units")
            with col_m4:          
                st.metric("Load imbalance", f"{metrics["load_imbalance"]} units")

            st.markdown("<div style='margin-top: 1.75rem;'></div>", unsafe_allow_html=True)

            loads_col, cp_col = st.columns([1, 2])
            cp_string = " → ".join(metrics["critical_path_nodes"])
            with loads_col:
                loads_fig = create_loads_fig(metrics, res_pu_num, theme_type)
                st.caption("PU loads")
                st.plotly_chart(loads_fig,
                                 use_container_width=True,
                                 key=f"loads_{selected}"
                                 )                
            with cp_col:
                st.markdown(
                    f"<div style='text-align: right;'>"
                    f"<p style='color: gray; font-size: 0.875rem; margin-bottom: 0.25rem;'>Critical path nodes</p>"
                    f"<p style='font-weight: 600; font-size: 1.4rem;'>{cp_string}</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )                

            st.divider()


    res1 = st.session_state.scheduling_results[0]
    res2 = st.session_state.scheduling_results[1]
    name1 = res1["name"]
    name2 = res2["name"]
    metrics1 = res1["metrics"]
    metrics2 = res2["metrics"]

    st.subheader(f"Comparison Summary")

    comparisons = [
        ("Makespan", metrics1["makespan"], metrics2["makespan"]),
        ("Critical Path", metrics1["critical_path_length"], metrics2["critical_path_length"]),
        ("Total Comm. Cost", metrics1["total_communication_cost"], metrics2["total_communication_cost"]),
        ("Load Imbalance", metrics1["load_imbalance"], metrics2["load_imbalance"]),
    ]

    diffs = []
    better_count = 0
    worse_count = 0

    for label, v1, v2 in comparisons:
        diff = v2-v1
        diffs.append(diff)

        if v1>v2:
            better_count += 1
        elif v2>v1:
            worse_count += 1

    st.caption(f"Values shown are for **{name2}**, with change relative to **{name1}**.")

    if better_count > worse_count:
        st.success(f"**{name2}** performs better than **{name1}** on {better_count} of {len(comparisons)} metrics.")
    elif worse_count > better_count:
        st.success(f"**{name1}** performs better than **{name2}** on {worse_count} of {len(comparisons)} metrics.")
    else:
        st.info(f"**{name1}** and **{name2}** are evenly matched ({better_count} better metrics each).")

    

    comp_cols = st.columns(len(comparisons))
    for i in range(len(comparisons)):
        label, v1, v2 = comparisons[i]
        diff = diffs[i]
        value_str = "0 units" if diff == 0 else f"{diff:+d} units"
        with comp_cols[i]:
            st.metric(
                label=label,
                value=value_str
            )            

