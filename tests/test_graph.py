"""Test the state graph engine (nodes + edges)."""
from src.graph import END, StateGraph, START
from src.state import AgentState, RunStatus


def test_graph_linear_flow():
    """Test a simple linear graph: A -> B -> C -> END."""

    def node_a(state: AgentState) -> AgentState:
        state.log("a", "running")
        state.raw_query = "a was here"
        return state

    def node_b(state: AgentState) -> AgentState:
        state.log("b", "running")
        state.raw_query += " -> b"
        return state

    def node_c(state: AgentState) -> AgentState:
        state.log("c", "running")
        state.raw_query += " -> c"
        return state

    graph = StateGraph()
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_node("c", node_c)
    graph.set_entry("a")
    graph.add_fixed_edge("a", "b")
    graph.add_fixed_edge("b", "c")
    graph.add_fixed_edge("c", END)

    state = AgentState()
    result = graph.run(state)

    assert result.raw_query == "a was here -> b -> c"
    assert result.trace == ["a: running", "b: running", "c: running"]


def test_graph_conditional_routing():
    """Test conditional edges based on state."""

    def set_flag(state: AgentState) -> AgentState:
        if not hasattr(state, "go_b"):
            state.go_b = True  # type: ignore
        state.log("start", "setting flag")
        return state

    def node_b(state: AgentState) -> AgentState:
        state.log("b", "took path B")
        state.raw_query = "B"
        return state

    def node_c(state: AgentState) -> AgentState:
        state.log("c", "took path C")
        state.raw_query = "C"
        return state

    def router(state: AgentState) -> str:
        return "b" if state.go_b else "c"  # type: ignore

    graph = StateGraph()
    graph.add_node("start", set_flag)
    graph.add_node("b", node_b)
    graph.add_node("c", node_c)
    graph.set_entry("start")
    graph.add_edge("start", router)
    graph.add_fixed_edge("b", END)
    graph.add_fixed_edge("c", END)

    state = AgentState()
    state.go_b = True  # type: ignore
    result = graph.run(state)

    assert result.raw_query == "B"
    assert "b" in str(result.trace)


def test_graph_failure_halts_execution():
    """Test that a node setting state.status=FAILED halts the graph."""

    def node_a(state: AgentState) -> AgentState:
        state.log("a", "running")
        return state

    def node_b(state: AgentState) -> AgentState:
        state.log("b", "failing")
        state.fail("node b error")
        return state

    def node_c(state: AgentState) -> AgentState:
        state.log("c", "should not run")
        return state

    graph = StateGraph()
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_node("c", node_c)
    graph.set_entry("a")
    graph.add_fixed_edge("a", "b")
    graph.add_fixed_edge("b", "c")
    graph.add_fixed_edge("c", END)

    state = AgentState()
    result = graph.run(state)

    assert result.status == RunStatus.FAILED
    assert "node b error" in result.errors
    # Node C should not have run
    assert "c" not in str(result.trace)


def test_graph_continue_on_failure():
    """Test continue_on_failure flag allows graph to keep going."""

    def node_a(state: AgentState) -> AgentState:
        state.log("a", "OK")
        return state

    def node_b(state: AgentState) -> AgentState:
        state.log("b", "failing but continue_on_failure=True")
        state.fail("node b error")
        return state

    def node_c(state: AgentState) -> AgentState:
        state.log("c", "should still run")
        return state

    graph = StateGraph()
    graph.add_node("a", node_a)
    graph.add_node("b", node_b, continue_on_failure=True)
    graph.add_node("c", node_c)
    graph.set_entry("a")
    graph.add_fixed_edge("a", "b")
    graph.add_fixed_edge("b", "c")
    graph.add_fixed_edge("c", END)

    state = AgentState()
    result = graph.run(state)

    assert result.status == RunStatus.FAILED
    assert "node b error" in result.errors
    # Node C SHOULD have run (continue_on_failure=True)
    assert "c" in str(result.trace)
