#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Functions to evolve nanowire networks over time.
# See: https://doi.org/10.1038/nature06932
# 
# Author: Marcus Kasdorf
# Date:   June 18, 2021

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from typing import Callable
from scipy.integrate import solve_ivp

from .calculations import solve_network


def resist_func(NWN: nx.Graph, w: np.ndarray) -> np.ndarray:
    """
    The HP group's resistance function in nondimensionalized form.

    Parameters
    ----------
    NWN : Graph
        Nanowire network.

    w : ndarray or scalar
        Nondimensionalized state variable of the memristor element(s).

    Returns
    -------
    R : ndarray or scalar
        Resistance of the memristor element(s).

    """
    Roff_Ron = NWN.graph["units"]["Roff_Ron"]
    R = w * (1 - Roff_Ron) + Roff_Ron
    return R


def deriv(
    t: float, 
    w: np.ndarray,
    NWN: nx.Graph,
    source_node: tuple, 
    drain_node: tuple,
    voltage_func: Callable,
    edge_list: list,
    solver: str = "spsolve",
    kwargs: dict = None
) -> np.ndarray:
    """
    Derivative of the nondimensionalized state variables `w`.

    """
    if kwargs is None:
        kwargs = dict()

    # Solve for and set resistances
    R = resist_func(NWN, w)
    attrs = {
        edge: {"conductance": 1 / R[i]} for i, edge in enumerate(edge_list)   
    }
    nx.set_edge_attributes(NWN, attrs)

    # Find applied voltage at the current time
    applied_V = voltage_func(t)

    # Solve for voltage at each node
    *V, I = solve_network(
        NWN, source_node, drain_node, applied_V, 
        "voltage", solver, **kwargs
    )
    V = np.array(V)

    # Find voltage differences
    v0, v1 = np.zeros_like(w), np.zeros_like(w)
    for i, edge in enumerate(edge_list):
        v0_indx = NWN.graph["node_indices"][edge[0]]
        v1_indx = NWN.graph["node_indices"][edge[1]]
        v0[i] = V[v0_indx] 
        v1[i] = V[v1_indx]
    V_delta = np.abs(v0 - v1) * np.sign(applied_V)
        
    # Find dw/dt
    dwdt = V_delta / R

    return dwdt


def solve_evolution(
    NWN: nx.Graph, 
    t_eval: np.ndarray,
    source_node: tuple, 
    drain_node: tuple, 
    voltage_func: Callable,
    solver: str = "spsolve",
    **kwargs
):
    """
    Solve parameters of the given nanowire network as various points in time.

    Parameters
    ----------
    NWN: Graph
        Nanowire network.

    t_eval : ndarray
        Time points to evaluate the nanowire network at. These should have
        units of `t0`.

    source_node : tuple
        Voltage/current source node.

    drain_node : tuple
        Grounded output node.

    voltage_func : Callable
        The applied voltage with the calling signature `func(t)`. The voltage 
        should have units of `v0`.

    solver : str, optional
        Name of sparse matrix solving algorithm to use. Default: "spsolve".

    **kwargs
        Keyword arguments passed to the solver.
    
    Returns
    -------
    sol : ndarray
        Output array containing the `w`, the state variable, of each edge in
        the same order given by `edge_list` which is also returned.

    edge_list : list of tuples
        List of the edges corresponding with each `w`.

    """
    # Get list of junction edges and the time bounds
    t_span = (t_eval[0], t_eval[-1])
    edge_list, w0 = map(list, zip(*[
        ((u, v), w) for u, v, w in NWN.edges.data("w") if w is not None]
    ))

    # Solve the system of ODEs
    sol = solve_ivp(
        deriv, t_span, w0, "DOP853", t_eval, 
        atol = 1e-12, 
        rtol = 1e-12,
        args = (NWN, source_node, drain_node, voltage_func, edge_list, solver, kwargs)
    )
    final_w = sol.y[:, -1]

    # Update the w value of each edge junction
    attrs = {edge: {"w": final_w[i]} for i, edge in enumerate(edge_list)}
    nx.set_edge_attributes(NWN, attrs)

    return sol, edge_list
