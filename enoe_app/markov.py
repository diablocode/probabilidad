"""Estimación y diagnóstico de cadenas de Markov para pares ENOE enlazados."""

from collections.abc import Sequence
from dataclasses import dataclass
import math
from math import gcd

import pandas as pd


MARKOV_STATES = (
    "Subordinado",
    "Cuenta propia",
    "Empleador",
    "Sin pago",
    "No ocupado",
)


class MarkovDataError(ValueError):
    """Error legible al estimar o diagnosticar una cadena de Markov."""


@dataclass(frozen=True)
class CommunicatingClass:
    states: tuple[str, ...]
    closed: bool | None
    period: int | None


@dataclass(frozen=True)
class MarkovReport:
    transition_counts: pd.DataFrame
    transition_weight_totals: pd.DataFrame
    transition_probabilities: pd.DataFrame
    row_pair_counts: pd.Series
    row_weight_totals: pd.Series
    weighting: str
    total_transitions: int
    periods: tuple[int, ...]
    states_without_outgoing: tuple[str, ...]
    communicating_classes: tuple[CommunicatingClass, ...]
    irreducible: bool | None
    aperiodic: bool | None
    ergodic: bool | None
    stationary_distribution: pd.Series | None
    stationary_status: str
    mean_first_passage: pd.DataFrame | None
    first_passage_status: str


def _solve_linear_system(
    coefficients: Sequence[Sequence[float]],
    right_hand_side: Sequence[float],
) -> list[float]:
    size = len(right_hand_side)
    if size == 0:
        return []
    augmented = [
        [float(value) for value in coefficients[row]]
        + [float(right_hand_side[row])]
        for row in range(size)
    ]
    if any(len(row) != size + 1 for row in augmented):
        raise _LinearSystemError("El sistema no es cuadrado.")

    for column in range(size):
        pivot = max(
            range(column, size),
            key=lambda row: abs(augmented[row][column]),
        )
        if abs(augmented[pivot][column]) < 1e-12:
            raise _LinearSystemError("El sistema no tiene solución única.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]

        pivot_value = augmented[column][column]
        augmented[column] = [
            value / pivot_value for value in augmented[column]
        ]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    value - factor * pivot_entry
                    for value, pivot_entry in zip(
                        augmented[row], augmented[column]
                    )
                ]
    return [augmented[row][-1] for row in range(size)]


class _LinearSystemError(ArithmeticError):
    pass


def _reachable(
    start: int,
    adjacency: Sequence[Sequence[bool]],
    allowed: set[int] | None = None,
) -> set[int]:
    visited = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for neighbor, has_edge in enumerate(adjacency[current]):
            if (
                has_edge
                and neighbor not in visited
                and (allowed is None or neighbor in allowed)
            ):
                visited.add(neighbor)
                pending.append(neighbor)
    return visited


def _communicating_components(
    adjacency: Sequence[Sequence[bool]],
) -> list[tuple[int, ...]]:
    reachability = [
        _reachable(state, adjacency) for state in range(len(adjacency))
    ]
    remaining = set(range(len(adjacency)))
    components = []
    while remaining:
        state = min(remaining)
        component = tuple(
            other
            for other in range(len(adjacency))
            if other in reachability[state] and state in reachability[other]
        )
        components.append(component)
        remaining.difference_update(component)
    return components


def _class_period(
    component: Sequence[int],
    adjacency: Sequence[Sequence[bool]],
) -> int | None:
    if len(component) == 1 and not adjacency[component[0]][component[0]]:
        return None

    allowed = set(component)
    distances = {component[0]: 0}
    pending = [component[0]]
    while pending:
        current = pending.pop(0)
        for neighbor, has_edge in enumerate(adjacency[current]):
            if has_edge and neighbor in allowed and neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                pending.append(neighbor)

    period = 0
    for origin in component:
        for destination, has_edge in enumerate(adjacency[origin]):
            if has_edge and destination in allowed:
                period = gcd(
                    period,
                    abs(distances[origin] + 1 - distances[destination]),
                )
    return period or None


def _mean_first_passage_times(
    transition_matrix: Sequence[Sequence[float]],
    adjacency: Sequence[Sequence[bool]],
) -> list[list[float]]:
    size = len(transition_matrix)
    result = [[math.inf] * size for _ in range(size)]
    for target in range(size):
        reverse_adjacency = [
            [adjacency[origin][destination] for origin in range(size)]
            for destination in range(size)
        ]
        can_reach_target = _reachable(target, reverse_adjacency)
        candidate_states = sorted(can_reach_target.difference({target}))
        hitting_probability = [0.0] * size
        hitting_probability[target] = 1.0

        if candidate_states:
            coefficients = [
                [
                    (1.0 if origin == destination else 0.0)
                    - transition_matrix[origin][destination]
                    for destination in candidate_states
                ]
                for origin in candidate_states
            ]
            right_hand_side = [
                transition_matrix[origin][target]
                for origin in candidate_states
            ]
            probabilities = _solve_linear_system(
                coefficients, right_hand_side
            )
            for state, probability in zip(candidate_states, probabilities):
                if abs(probability - 1.0) < 1e-10:
                    probability = 1.0
                elif abs(probability) < 1e-10:
                    probability = 0.0
                hitting_probability[state] = min(1.0, max(0.0, probability))

        finite_states = [
            state
            for state in candidate_states
            if hitting_probability[state] == 1.0
        ]
        result[target][target] = 0.0
        if finite_states:
            coefficients = [
                [
                    (1.0 if origin == destination else 0.0)
                    - transition_matrix[origin][destination]
                    for destination in finite_states
                ]
                for origin in finite_states
            ]
            expected_steps = _solve_linear_system(
                coefficients, [1.0] * len(finite_states)
            )
            for state, steps in zip(finite_states, expected_steps):
                result[state][target] = max(0.0, steps)
    return result


def estimate_markov_chain(
    pairs: pd.DataFrame,
    *,
    weighting: str = "simple",
) -> MarkovReport:
    """Estima una matriz desde pares consecutivos con estados ya normalizados.

    La opción ponderada utiliza `fac_tri_origen` como peso de cada transición.
    """
    if weighting not in {"simple", "weighted"}:
        raise MarkovDataError(
            "La ponderación debe ser 'simple' o 'weighted'."
        )
    if pairs.empty:
        raise MarkovDataError("No hay pares longitudinales para estimar.")
    required = {
        "periodo_origen",
        "periodo_destino",
        "estado_origen",
        "estado_destino",
        "fac_tri_origen",
    }
    missing_columns = sorted(required.difference(pairs.columns))
    if missing_columns:
        raise MarkovDataError(
            "Faltan columnas requeridas: " + ", ".join(missing_columns)
        )
    origins = pairs["estado_origen"].astype("string").str.strip()
    destinations = pairs["estado_destino"].astype("string").str.strip()
    invalid_state = (
        origins.isna()
        | destinations.isna()
        | ~origins.isin(MARKOV_STATES)
        | ~destinations.isin(MARKOV_STATES)
    )
    if invalid_state.any():
        raise MarkovDataError(
            "Los pares contienen estados laborales faltantes o no canónicos."
        )

    origin_periods = pd.to_numeric(pairs["periodo_origen"], errors="coerce")
    destination_periods = pd.to_numeric(
        pairs["periodo_destino"], errors="coerce"
    )
    valid_periods = (
        origin_periods.notna()
        & destination_periods.notna()
        & origin_periods.mod(1).eq(0)
        & destination_periods.mod(1).eq(0)
        & destination_periods.eq(origin_periods + 1)
    )
    if not valid_periods.all():
        raise MarkovDataError(
            "Cada par debe corresponder a dos periodos enteros consecutivos."
        )

    weights = pd.to_numeric(pairs["fac_tri_origen"], errors="coerce")
    valid_weights = weights.map(
        lambda value: math.isfinite(value) and value > 0
        if pd.notna(value)
        else False
    )
    if not valid_weights.all():
        raise MarkovDataError(
            "fac_tri_origen debe ser positivo y finito en todos los pares."
        )

    state_indices = {state: index for index, state in enumerate(MARKOV_STATES)}
    size = len(MARKOV_STATES)
    counts = [[0] * size for _ in range(size)]
    weight_totals = [[0.0] * size for _ in range(size)]
    for origin, destination, weight in zip(origins, destinations, weights):
        origin_index = state_indices[str(origin)]
        destination_index = state_indices[str(destination)]
        counts[origin_index][destination_index] += 1
        weight_totals[origin_index][destination_index] += float(weight)

    row_pair_counts = [sum(row) for row in counts]
    row_weight_totals = [sum(row) for row in weight_totals]
    denominators = (
        row_weight_totals if weighting == "weighted" else row_pair_counts
    )
    numerators = weight_totals if weighting == "weighted" else counts
    probabilities = [
        [
            float(numerators[origin][destination]) / denominators[origin]
            if denominators[origin]
            else math.nan
            for destination in range(size)
        ]
        for origin in range(size)
    ]
    adjacency = [
        [counts[origin][destination] > 0 for destination in range(size)]
        for origin in range(size)
    ]
    complete = all(count > 0 for count in row_pair_counts)
    states_without_outgoing = tuple(
        state
        for state, count in zip(MARKOV_STATES, row_pair_counts)
        if count == 0
    )

    components = _communicating_components(adjacency)
    classes = []
    for component in components:
        component_states = tuple(MARKOV_STATES[index] for index in component)
        component_complete = all(row_pair_counts[index] > 0 for index in component)
        closed = (
            all(
                not adjacency[origin][destination]
                for origin in component
                for destination in range(size)
                if destination not in component
            )
            if component_complete
            else None
        )
        classes.append(
            CommunicatingClass(
                states=component_states,
                closed=closed,
                period=(
                    _class_period(component, adjacency)
                    if component_complete
                    else None
                ),
            )
        )

    irreducible = (
        len(components) == 1 if complete else None
    )
    aperiodic = (
        classes[0].period == 1 if irreducible and classes else None
    )
    ergodic = (
        bool(irreducible and aperiodic) if complete else None
    )

    stationary_distribution = None
    if not complete:
        stationary_status = (
            "No disponible: faltan transiciones salientes para "
            + ", ".join(states_without_outgoing)
            + "."
        )
    elif sum(item.closed is True for item in classes) != 1:
        stationary_status = (
            "No hay una distribución estacionaria única: la cadena tiene "
            "más de una clase cerrada."
        )
    else:
        coefficients = [
            [
                probabilities[origin][destination]
                - (1.0 if origin == destination else 0.0)
                for origin in range(size)
            ]
            for destination in range(size)
        ]
        coefficients[-1] = [1.0] * size
        right_hand_side = [0.0] * size
        right_hand_side[-1] = 1.0
        try:
            stationary_values = _solve_linear_system(
                coefficients, right_hand_side
            )
        except _LinearSystemError as error:
            stationary_status = (
                "No se pudo resolver numéricamente la distribución "
                f"estacionaria: {error}"
            )
        else:
            residual = max(
                abs(
                    sum(
                        stationary_values[origin]
                        * probabilities[origin][destination]
                        for origin in range(size)
                    )
                    - stationary_values[destination]
                )
                for destination in range(size)
            )
            if (
                min(stationary_values) < -1e-8
                or residual > 1e-8
            ):
                stationary_status = (
                    "No se obtuvo una solución estacionaria dentro de la "
                    "tolerancia numérica 1e-8."
                )
            else:
                stationary_values = [
                    max(0.0, value) for value in stationary_values
                ]
                total_probability = sum(stationary_values)
                stationary_distribution = pd.Series(
                    [
                        value / total_probability
                        for value in stationary_values
                    ],
                    index=MARKOV_STATES,
                    name="probabilidad_estacionaria",
                )
                stationary_status = (
                    "Distribución estacionaria única; residuo máximo "
                    f"{residual:.2e} (tolerancia 1e-8)."
                )

    first_passage = None
    if not complete:
        first_passage_status = (
            "No disponible: la matriz no es estocástica porque hay estados "
            "sin transiciones salientes observadas."
        )
    else:
        try:
            first_passage_values = _mean_first_passage_times(
                probabilities, adjacency
            )
        except _LinearSystemError as error:
            first_passage_status = (
                f"No se pudieron resolver los tiempos de primer paso: {error}"
            )
        else:
            first_passage = pd.DataFrame(
                first_passage_values,
                index=MARKOV_STATES,
                columns=MARKOV_STATES,
            )
            first_passage_status = (
                "Esperanza de pasos consecutivos hasta alcanzar por primera "
                "vez el estado destino; ∞ indica probabilidad de llegada menor "
                "que 1. La diagonal vale 0 (tiempo inicial)."
            )

    periods = tuple(
        sorted(
            {
                int(value)
                for value in pd.concat(
                    [origin_periods, destination_periods], ignore_index=True
                )
            }
        )
    )
    return MarkovReport(
        transition_counts=pd.DataFrame(
            counts, index=MARKOV_STATES, columns=MARKOV_STATES
        ),
        transition_weight_totals=pd.DataFrame(
            weight_totals, index=MARKOV_STATES, columns=MARKOV_STATES
        ),
        transition_probabilities=pd.DataFrame(
            probabilities, index=MARKOV_STATES, columns=MARKOV_STATES
        ),
        row_pair_counts=pd.Series(
            row_pair_counts, index=MARKOV_STATES, name="pares"
        ),
        row_weight_totals=pd.Series(
            row_weight_totals, index=MARKOV_STATES, name="fac_tri_origen"
        ),
        weighting=weighting,
        total_transitions=len(pairs),
        periods=periods,
        states_without_outgoing=states_without_outgoing,
        communicating_classes=tuple(classes),
        irreducible=irreducible,
        aperiodic=aperiodic,
        ergodic=ergodic,
        stationary_distribution=stationary_distribution,
        stationary_status=stationary_status,
        mean_first_passage=first_passage,
        first_passage_status=first_passage_status,
    )
