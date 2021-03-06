import Queue
from AbortedDijkstra import aborted_dijkstra
from Map import Map
import numpy as np


# An implementation of multi-origin bidirectional_dijkstra
class DijkstrasAlgorithm:
    # Gives out sequential node_id numbers to the boundary nodes in this region
    # These values are used to index the node.forward_boundary_time array
    @staticmethod
    def init_boundary_node_ids(list_of_boundary_nodes):
        i = 0
        sorted_boundary_nodes = sorted(list_of_boundary_nodes,
                                       key=lambda x: x.node_id)
        for node in sorted_boundary_nodes:
            node.boundary_node_id = i
            i += 1

    # Sets up lists of "INF" for each nodes, excluding boundary nodes
    @staticmethod
    def initialize_nodes(boundary_nodes_list, nyc_map):
        if not boundary_nodes_list:
            return
        tmp_node = None
        for node in boundary_nodes_list:
            tmp_node = node
            break
        this_region_id = tmp_node.region_id

        for node in nyc_map.nodes:
            # Each node needs a distance from each boundary node
            # all starting at infinity
            node.forward_boundary_time = np.repeat(
                float("INF"), len(boundary_nodes_list))
            node.backward_boundary_time = np.repeat(
                float("INF"), len(boundary_nodes_list))

            if node.is_boundary_node and (
                    node.region_id == this_region_id):
                # All boundary nodes in this region are 0 distance away
                # from themselves
                index = node.boundary_node_id
                node.forward_boundary_time[index] = 0
                node.backward_boundary_time[index] = 0

            # Store a deep copy snapshot of forward_boundary_time for
            # future comparison
            # node.time_snapshot = np.copy(node.forward_boundary_time)
            node.forward_predecessors = (
                np.array([None] * len(boundary_nodes_list)))
            node.backward_predecessors = (
                np.array([None] * len(boundary_nodes_list)))

    # Computes the shortest path between all pairs of boundary nodes
    # If this node_id done before the main bidirectional_dijkstra() search,
    # performance should be much better
    @staticmethod
    def initialize_boundary_nodes(boundary_nodes_list, nyc_map,
                                  this_region_only, on_forward_graph):

        visited_nodes = set()
        for boundary_node in boundary_nodes_list:
            partial_visited_nodes, _, _ = aborted_dijkstra(
                boundary_node, boundary_nodes_list, this_region_only,
                on_forward_graph)
            visited_nodes.update(partial_visited_nodes)

        # Update the snapshots of the boundary nodes
        # for boundary_node in boundary_nodes_list:
        #    np.copyto(boundary_node.time_snapshot,
        #              boundary_node.forward_boundary_time)
        return visited_nodes

    # Every node in array nodes gets reset so it has no distance from anything,
    # no time from anything, and came from nothing (used to reset after making
    # the path)
    @staticmethod
    def reset_nodes(nyc_map):
        for node in nyc_map.nodes:
            if node is not None:
                # For multi-origin bidirectional dijkstra, storing the
                # time from each boundary node
                node.forward_boundary_time = np.array([])
                node.backward_boundary_time = np.array([])

                # A snapshot of the forward_boundary_time from the
                # last expansion
                # node.time_snapshot = np.array([])

                # For each boundary node path, shows where this
                # particular node came
                # from
                node.forward_predecessors = np.array([])
                node.backward_predecessors = np.array([])

    @staticmethod
    def directed_dijkstra(boundary_nodes, nyc_map, warm_start,
                          use_domination_value, on_forward_graph):
        # if on_forward_graph:
            # print("---Computing on the forward graph---")
        # else:
            # print("---Computing on the backward graph---")

        max_queue_size = 0  # debug
        expansion_count = 0  # debug

        # Compute pairwise distances between boundary nodes, so only good
        # information is propagated
        if warm_start:
            # print("Warmstarting...")
            touched_nodes = DijkstrasAlgorithm.initialize_boundary_nodes(
                boundary_nodes, nyc_map, False, on_forward_graph)
        else:
            touched_nodes = boundary_nodes

        # print("Running Dijkstra with " + str(len(boundary_nodes))         
              # + " boundary nodes.")
        # Nodes we intend to search (somehow connected to graph so far). We
        # treat this as a priority queue: the one that has the potential to be
        # closest (has best distance from the start_node/is closest to the
        # end_node) is treated next
        nodes_to_search = Queue.PriorityQueue()

        for node in touched_nodes:
            if not(node.region_id == boundary_nodes[0].region_id and node.is_boundary_node):
                if on_forward_graph:
                    node.forward_boundary_time = np.repeat(
                    float("INF"), len(boundary_nodes))
                    node.forward_predecessors = (
                    np.array([None] * len(boundary_nodes)))
                else:
                    node.backward_boundary_time = np.repeat(
                    float("INF"), len(boundary_nodes))
                    node.backward_predecessors = (
                    np.array([None] * len(boundary_nodes)))
        for add_node in boundary_nodes:
            nodes_to_search.put((
                # times updated since it was last expanded
                add_node.get_priority_key(
                    use_domination_value, on_forward_graph),
                # minimum time from boundary node
                add_node.get_min_boundary_time(on_forward_graph),
                # number of infinities in the list
                add_node.get_boundary_time_inf_count(
                    on_forward_graph),
                # sum of non infinities in the list
                add_node.get_boundary_time_sum(on_forward_graph),
                # the actual node itself
                add_node))
        while not nodes_to_search.empty():
            # Gets the node closest to the end node in the best case
            if (nodes_to_search.qsize() > max_queue_size):
                max_queue_size = nodes_to_search.qsize()

            queue_item = nodes_to_search.get()
            _, old_min_time, old_inf_count, old_sum = queue_item[0:4]
            curr_node = queue_item[4]

            # Skip if the item in queue is out-dated
            if(old_min_time > curr_node.get_min_boundary_time(
                on_forward_graph) or
               old_inf_count > curr_node.get_boundary_time_inf_count(
                on_forward_graph) or
               old_sum < curr_node.get_boundary_time_sum(on_forward_graph)):
                continue

            # Overwrite the snapshot with a copy of the current label
            # np.copyto(curr_node.time_snapshot,
            #          curr_node.forward_boundary_time)

            # expansion of curr_node starts here
            expansion_count += 1

            connecting_links = None
            if on_forward_graph:
                connecting_links = curr_node.backward_links
            else:
                connecting_links = curr_node.forward_links

            for connected_link in connecting_links:
                connected_node = None
                if on_forward_graph:
                    connected_node = connected_link.origin_node
                else:
                    connected_node = connected_link.connecting_node

                if connected_link.time <= 0:
                    continue

                time_from_boundary_node = None
                connected_node_time = None
                if on_forward_graph:
                    time_from_boundary_node = curr_node.forward_boundary_time
                    connected_node_time = connected_node.forward_boundary_time
                else:
                    time_from_boundary_node = curr_node.backward_boundary_time
                    connected_node_time = connected_node.backward_boundary_time

                # The proposed distances from all boundary nodes if you go
                # through curr_node i.e. curr_node's distances from the
                # boundary nodes + the length of this link
                proposed_label = (time_from_boundary_node
                                  + connected_link.time)

                # Only shorter paths are accepted - perform the element-wise
                # min against current values
                proposed_label = np.minimum(
                    proposed_label, connected_node_time)

                # If there were any changes, copy and note them
                if not np.array_equal(proposed_label, connected_node_time):
                    # Update the forward_predecessors for the connected nodes
                    # that has updates
                    updated = np.nonzero(connected_node_time
                                         - proposed_label)[0]
                    if on_forward_graph:
                        connected_node.forward_predecessors[updated] = (
                            curr_node)
                    else:
                        connected_node.backward_predecessors[updated] = (
                            curr_node)

                    np.copyto(connected_node_time, proposed_label)

                    # Put the new connected_node into the priority queue
                    nodes_to_search.put((
                        # times updated since it was last expanded
                        connected_node.get_priority_key(
                            use_domination_value, on_forward_graph),
                        # minimum time from boundary node
                        connected_node.get_min_boundary_time(on_forward_graph),
                        # number of infinities in the list
                        connected_node.get_boundary_time_inf_count(
                            on_forward_graph),
                        # sum of non infinities in the list
                        connected_node.get_boundary_time_sum(on_forward_graph),
                        # the actual node itself
                        connected_node))

        # print("Max Queue Size: " + str(max_queue_size))  # debug
        # print("Number of expansions: " + str(expansion_count))  # debug

    # Basically creates a tree rooted at the boundary node where every edge in
    # the tree is an arcflag
    @staticmethod
    def bidirectional_dijkstra(boundary_nodes, nyc_map, warm_start,
                               use_domination_value):

        # Assign sequential IDs to the boundary nodes of this region
        DijkstrasAlgorithm.init_boundary_node_ids(boundary_nodes)

        # print("Initializing...")
        # Gives each node a distance from the boundary nodes, which are
        # initially either INF(infinity) or 0
        DijkstrasAlgorithm.initialize_nodes(boundary_nodes, nyc_map)

        # print "processing forward graph"
        DijkstrasAlgorithm.directed_dijkstra(boundary_nodes, nyc_map,
                                             warm_start, use_domination_value,
                                             on_forward_graph=True)
        # print "processing backward graph"
        DijkstrasAlgorithm.directed_dijkstra(boundary_nodes, nyc_map,
                                             warm_start, use_domination_value,
                                             on_forward_graph=False)

        # DijkstrasAlgorithm.independent_dijkstra(boundary_nodes, nyc_map)

        DijkstrasAlgorithm.set_arc_flags(nyc_map, boundary_nodes[0].region_id)
        # print

    # Runs a Dijkstra search independently for each boundary node.
    @staticmethod
    def independent_dijkstra(boundary_nodes, nyc_map):
        # Assign each boundary node an i for distance
        DijkstrasAlgorithm.init_boundary_node_ids(boundary_nodes)

        print("initializing")
        # Gives each node a distance from the boundary nodes, which are
        # initially either INF(infinity) or 0
        DijkstrasAlgorithm.initialize_nodes(boundary_nodes, nyc_map)

        forward_total_expanded = 0
        forward_overall_max_pq_size = 0
        backward_total_expanded = 0
        backward_overall_max_pq_size = 0
        for boundary_node in boundary_nodes:
            _, forward_num_expanded, forward_max_pq_size = aborted_dijkstra(
                boundary_node, None, this_region_only=False,
                on_forward_graph=True)
            _, backward_num_expanded, backward_max_pq_size = aborted_dijkstra(
                boundary_node, None, this_region_only=False,
                on_forward_graph=False)
            forward_total_expanded += forward_num_expanded
            forward_overall_max_pq_size = max(forward_overall_max_pq_size,
                                              forward_max_pq_size)
            backward_total_expanded += backward_num_expanded
            backward_overall_max_pq_size = max(backward_overall_max_pq_size,
                                               backward_max_pq_size)

        max_pq = max(forward_overall_max_pq_size, backward_overall_max_pq_size)
        max_expand = max(forward_total_expanded, backward_total_expanded)
        print("Max Queue Size:", max_pq)  # debug
        print("Number of expansions:", max_expand)  # debug

        return max_expand, max_pq

    # Given where the nodes came from, rebuilds the path that was taken to the
    # final node
    @staticmethod
    def set_arc_flags(nyc_map, curr_region_id):
        for node in nyc_map.nodes:
            # Set forward arc flags
            for predecessor_node in node.forward_predecessors:
                if predecessor_node is not None:
                    assignLink = nyc_map.links_by_node_id[(node.node_id, predecessor_node.node_id)]
                    assignLink.forward_arc_flags_vector[curr_region_id] = True
            # Set backward arc flags
            for predecessor_node in node.backward_predecessors:
                if predecessor_node is not None:
                    assignLink = nyc_map.links_by_node_id[(predecessor_node.node_id, node.node_id)]
                    assignLink.backward_arc_flags_vector[curr_region_id] = True


        for link in nyc_map.links:
            connect_node = nyc_map.nodes_by_id[link.connecting_node_id]
            forward_region_id = connect_node.region_id
            link.forward_arc_flags_vector[forward_region_id] = True


            origin_node = nyc_map.nodes_by_id[link.origin_node_id]
            backward_region_id = origin_node.region_id
            link.backward_arc_flags_vector[backward_region_id] = True


            link.forward_arc_flags_vector[backward_region_id] = True
            link.backward_arc_flags_vector[forward_region_id] = True




########################################################################################
#   ArcFlags | graph      | Predecessor Directions
#
#   Forward  | Backward   | With Forward Graph
#   Backward | Forward    | against Forward Graph
#
########################################################################################

