import networkx as nx
import json
from abc import ABC, abstractmethod


def load_dag(file):
    try:
        data = json.load(file)
    except json.JSONDecodeError:
        raise ValueError("The file is not a valid JSON format.")

    if not isinstance(data, dict):
        raise ValueError("The main element in JSON needs to be a dictionary.")


    dag = nx.DiGraph()

    all_nodes = data.get("nodes")
    if not isinstance(all_nodes, dict):
         raise ValueError("The 'nodes' field is missing or isn't a dictionary.")

    for node_id, attributes in all_nodes.items():
        if not isinstance(attributes, dict) or "duration" not in attributes:
             raise ValueError(f"Node {node_id} has no defined duration.")

        duration = attributes["duration"]

        if not isinstance(duration, int) or isinstance(duration, bool):
             raise ValueError(f"Node {node_id} has invalid duration: {duration!r}. (must be an integer)")
             
        dag.add_node(node_id, duration=duration)

    if len(dag.nodes) == 0:
            raise ValueError("The DAG needs to have at least one node.")


    all_edges = data.get("edges")
    if not isinstance(all_edges, list):
         raise ValueError("The 'edges' field is missing or isn't a list.")

    for edge in all_edges:
        if not isinstance(edge, dict) or "to" not in edge or "from" not in edge:
             raise ValueError("Invalid edge format (must have 'to' and 'from').")

        u = edge.get("from")
        v = edge.get("to")
        communication = edge.get("communication", 0)

        if u not in dag or v not in dag:
             raise ValueError(f"The edge is connecting non-existent nodes: {u} -> {v}.")

        if not isinstance(communication, int) or isinstance(communication, bool):
             raise ValueError(f"Edge {u} -> {v} has invalid communication cost: {communication!r}. (must be an integer)")

        dag.add_edge(u, v, communication = communication)

    if not nx.is_directed_acyclic_graph(dag):
        raise ValueError("The loaded graph is not a valid DAG, contains a cycle.")

    return dag

class SchedulingHeuristicStrategy(ABC):
     def __init__(self, pu_num):
          if not isinstance(pu_num, int) or pu_num < 1:
               raise ValueError("The number of processing units must be a positive integer.")
          
          self.pu_num = pu_num

     @abstractmethod
     def generate_schedule(self, dag):
          raise NotImplementedError


class FirstComeFirstServeStrategy(SchedulingHeuristicStrategy):
     def generate_schedule(self, dag):
          pu_num = self.pu_num

          remaining_predecessors = { task: dag.in_degree(task) for task in dag.nodes() }
          ready_tasks = [ task for task, count in remaining_predecessors.items() if count == 0]
          schedule = {}
          pu_free_times = [0] * pu_num

          while ready_tasks:
               current_task = ready_tasks.pop(0)
               best_pu = None
               best_start_time = None

               for pu in range(pu_num):
                    predecessors_ready_time = 0

                    for predecessor in dag.predecessors(current_task):
                         predecessor_end_time = schedule[predecessor]["end_time"]
                         predecessor_pu = schedule[predecessor]["pu"]

                         if predecessor_pu == pu:
                              arrival_time = predecessor_end_time
                         else:
                              communication_cost = dag.edges[predecessor, current_task]["communication"]
                              arrival_time = predecessor_end_time + communication_cost

                         predecessors_ready_time = max(predecessors_ready_time, arrival_time)

                    start_time = max(predecessors_ready_time, pu_free_times[pu])
                    if best_start_time is None or start_time < best_start_time:
                         best_start_time = start_time
                         best_pu = pu

               duration = dag.nodes[current_task]["duration"]
               end_time = best_start_time + duration

               schedule[current_task] = {
                    "start_time": best_start_time,
                    "end_time": end_time,
                    "pu": best_pu
               }

               pu_free_times[best_pu] = end_time

               for successor in dag.successors(current_task):
                    remaining_predecessors[successor] -= 1
                    if remaining_predecessors[successor] == 0:
                         ready_tasks.append(successor)

          return schedule 



class LongestTaskFirstStrategy(SchedulingHeuristicStrategy):     
     def generate_schedule(self, dag):
          pu_num = self.pu_num

          remaining_predecessors = { task: dag.in_degree(task) for task in dag.nodes() }
          ready_tasks = [ task for task, count in remaining_predecessors.items() if count == 0]
          schedule = {}
          pu_free_times = [0] * pu_num
 
          while ready_tasks:

               current_task = max(ready_tasks, key = lambda task: dag.nodes[task]["duration"])
               ready_tasks.remove(current_task)

               best_pu = None
               best_start_time = None

               for pu in range(pu_num):
                    predecessors_ready_time = 0

                    for predecessor in dag.predecessors(current_task):
                         predecessor_end_time = schedule[predecessor]["end_time"]
                         predecessor_pu = schedule[predecessor]["pu"]

                         if predecessor_pu == pu:
                              arrival_time = predecessor_end_time
                         else:
                              communication_cost = dag.edges[predecessor, current_task]["communication"]
                              arrival_time = predecessor_end_time + communication_cost

                         predecessors_ready_time = max(predecessors_ready_time, arrival_time)

                    start_time = max(predecessors_ready_time, pu_free_times[pu])
                    if best_start_time is None or start_time < best_start_time:
                         best_start_time = start_time
                         best_pu = pu

               duration = dag.nodes[current_task]["duration"]
               end_time = best_start_time + duration

               schedule[current_task] = {
                    "start_time": best_start_time,
                    "end_time": end_time,
                    "pu": best_pu
               }

               pu_free_times[best_pu] = end_time

               for successor in dag.successors(current_task):
                    remaining_predecessors[successor] -= 1
                    if remaining_predecessors[successor] == 0:
                         ready_tasks.append(successor)

          return schedule


def calculate_cp_ranks(dag):
     ranks = {}

     for task in reversed(list(nx.topological_sort(dag))):
          duration = dag.nodes[task]["duration"]
          successors = list(dag.successors(task))
          if not successors:
               ranks[task] = duration
          else:
               ranks[task] = duration + max( 
                    dag.edges[task, successor]["communication"] + ranks[successor] for successor in successors
                    )

     return ranks

class CriticalPathStrategy(SchedulingHeuristicStrategy):
     def generate_schedule(self, dag):
          pu_num = self.pu_num

          ranks = calculate_cp_ranks(dag)

          remaining_predecessors = { task: dag.in_degree(task) for task in dag.nodes() }
          ready_tasks = [ task for task, count in remaining_predecessors.items() if count == 0]
          schedule = {}
          pu_free_times = [0] * pu_num

          while ready_tasks:
               current_task = max(ready_tasks, key = lambda task: ranks[task])
               ready_tasks.remove(current_task)

               best_pu = None
               best_start_time = None

               for pu in range(pu_num):
                    predecessors_ready_time = 0

                    for predecessor in dag.predecessors(current_task):
                         predecessor_end_time = schedule[predecessor]["end_time"]
                         predecessor_pu = schedule[predecessor]["pu"]

                         if predecessor_pu == pu:
                              arrival_time = predecessor_end_time
                         else:
                              communication_cost = dag.edges[predecessor, current_task]["communication"]
                              arrival_time = predecessor_end_time + communication_cost

                         predecessors_ready_time = max(predecessors_ready_time, arrival_time)

                    start_time = max(predecessors_ready_time, pu_free_times[pu])
                    if best_start_time is None or start_time < best_start_time:
                         best_start_time = start_time
                         best_pu = pu

               duration = dag.nodes[current_task]["duration"]
               end_time = best_start_time + duration

               schedule[current_task] = {
                    "start_time": best_start_time,
                    "end_time": end_time,
                    "pu": best_pu
               }

               pu_free_times[best_pu] = end_time

               for successor in dag.successors(current_task):
                    remaining_predecessors[successor] -= 1
                    if remaining_predecessors[successor] == 0:
                         ready_tasks.append(successor)

          return schedule


AVAILABLE_HEURISTICS = {
     "First Come First Serve": FirstComeFirstServeStrategy,
     "Longest Task First": LongestTaskFirstStrategy,
     "Critical Path": CriticalPathStrategy,
}



def calculate_metrics(dag, schedule, pu_num):
     makespan = max(task["end_time"] for task in schedule.values())


     total_communication_cost = 0
     for u, v, data in dag.edges(data=True):
          pu_u = schedule[u]["pu"]
          pu_v = schedule[v]["pu"]
          if pu_u != pu_v:
               total_communication_cost += data.get("communication", 0)


     longest = {}
     predecessors_on_path = {}
     for node in nx.topological_sort(dag):
          predecessors = list(dag.predecessors(node))

          if not predecessors:
               longest[node] = dag.nodes[node]["duration"]
               predecessors_on_path[node] = None
          else:
               best_predecessor = max(predecessors, key = lambda pred: longest[pred] + 
                                      (dag.edges[pred, node].get("communication", 0) if schedule[pred]["pu"] != schedule[node]["pu"] else 0) +
                                      dag.nodes[node].get("duration", 0))
               communication = dag.edges[best_predecessor, node].get("communication", 0) if schedule[best_predecessor]["pu"] != schedule[node]["pu"] else 0
               longest[node] = longest[best_predecessor] + communication + dag.nodes[node].get("duration", 0)
               predecessors_on_path[node] = best_predecessor

     end_node = list(longest.keys())[0]
     critical_path_length = longest[end_node]
     for node, distance in longest.items():
          if distance > critical_path_length:
               critical_path_length = distance
               end_node = node

     critical_path_nodes = []
     curr = end_node
     while curr and curr in predecessors_on_path:
          critical_path_nodes.append(curr)
          curr = predecessors_on_path[curr]
     critical_path_nodes.reverse() 


     loads = { pu: 0 for pu in range(pu_num) }
     for task, info in schedule.items():
          pu = info["pu"]
          loads[pu] += dag.nodes[task]["duration"]

     load_imbalance = max(loads.values()) - min(loads.values())

     metrics_res = {
          "makespan": makespan,
          "total_communication_cost": total_communication_cost,
          "critical_path_length": critical_path_length,
          "critical_path_nodes": critical_path_nodes,
          "load_imbalance": load_imbalance
     }
     for pu, load in loads.items():
          metrics_res[f"pu_{pu}_load"] = load

     return metrics_res
     

def calculate_cp_nodes(dag):
     ranks = calculate_cp_ranks(dag)
     start_node = max(dag.nodes(), key=lambda node: ranks[node])
     cp_nodes= [start_node]
     current_node = start_node

     while list(dag.successors(current_node)):
          successors = list(dag.successors(current_node))
          next_node = max(successors,key=lambda succ: dag.edges[current_node, succ]["communication"] + ranks[succ],)
          cp_nodes.append(next_node)
          current_node = next_node

     return cp_nodes
     