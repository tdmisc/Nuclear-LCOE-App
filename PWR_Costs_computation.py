"""
Simplified model of the Levelized Cost of Electricity (LCOE)
for a nuclear power plant with 4 VVER-type reactors in Serbia.

Educational objective: everything is gathered in a single script, with
a clear input section and separate functions for:
- CAPEX
- OPEX (excluding fuel)
- Fuel cycle cost
- LCOE

Default units:
- Power   : MWe
- Energy  : MWh
- Mass    : kgU / tU
- Currency: $ (US dollars)
"""

import math
import os
import sys
from dataclasses import dataclass, field

# Import of annex functions (conversion, energy, etc.)
CURRENT_DIR = os.path.dirname(__file__)
ANNEX_DIR = os.path.join(CURRENT_DIR, "Annex Functions")
if ANNEX_DIR not in sys.path:
    sys.path.append(ANNEX_DIR)

from Simple_Conversion_Functions import UO2_to_U
from Annex_Cost_Functions import (
    annual_energy_MWh,
    annual_fresh_fuel_mass_kg,
    annual_enriched_U_mass_kg,
    optimize_front_end_uranium_cost,
)


# ============================================================
# 1. INPUT PARAMETERS (EDIT ONLY HERE)
# ============================================================

@dataclass
class ProjectParameters:
    # --- Project / reactor parameters ---
    country: str = "Serbie"
    reactor_type: str = "VVER-1200"
    n_reactors: int = 4
    power_electric_per_reactor_MWe: float = 1200.0  # MWé
    net_capacity_factor: float = 0.80  # fraction (0-1)
    first_reactor_construction_time_years: float = 7.0  # Time to build the first reactor
    delay_between_reactors_years: float = 1.0  # Delay between starting construction of each subsequent reactor
    reactors_lifetime_years: int = 60

    # --- Natural uranium parameters ---
    distance_uranium_mine_to_enriching_factory_km: float = 5000.0
    distance_enriching_factory_to_fuel_factory_km: float = 63
    distance_fuel_factory_to_power_plant_km: float = 1600

    # --- Enrichment parameters ---
    x_U_nat: float = 0.00711   # U-235 fraction in natural uranium
    x_U_product: float = 0.048  # U-235 fraction in enriched product (4.8%)

    # --- Core and fuel parameters ---
    assemblies_per_core: int = 163              # number of fuel assemblies in core (typical VVER-1200)
    fuel_mass_per_assembly_kg: float = 534      # kgUO2 per assembly (oxide mass)

    # --- Derived parameters (computed automatically) ---
    # Uranium metal mass in one assembly (depends on fuel_mass_per_assembly_kg)
    U_mass_per_assembly_kg: float = field(init=False)

    batch_fraction: float = 1.0 / 3.0           # 1/3 of the core reloaded per cycle
    cycle_length_years: float = 18.0 / 12.0     # cycle length in years (for simplicity)

    spent_fuel_backend: str = "direct disposal"  # "direct disposal" or "reprocessing"

    # --- Transport distances (km) ---
    distance_U_nat_transport_km: float = 5000.0       # mine to conversion plant
    distance_U_converted_transport_km: float = 1200.0  # conversion plant to enrichment plant
    distance_U_enriched_transport_km: float = 100.0  # enrichment plant to fuel fabrication plant
    distance_fresh_fuel_transport_km: float = 1000.0  # fuel fabrication plant to reactor site
    distance_spent_fuel_transport_km: float = 500.0   # reactor site to disposal/reprocessing facility
    
    def __post_init__(self):
        # Convert UO2 mass per assembly to uranium metal mass
        self.U_mass_per_assembly_kg = UO2_to_U(self.fuel_mass_per_assembly_kg)


@dataclass
class CostParameters:
    real_discount_rate: float = 0.05  # 5% real, discount rate net of inflation
    # --- CAPEX ---
    cost_per_reactor_USD: float = 6e9  # $ per reactor (overnight, without interest during construction)

    # --- Dismantling (decommissioning) ---
    dismantling_cost_per_reactor_USD: float = 0.0  # $ per reactor (at end of lifetime)

    # --- OPEX excluding fuel ---
    exploitation_cost_per_year_per_reactor_USD: float = 200e6  # staff, maintenance, services, etc. (per year)

    # --- Front-end fuel cycle costs ---
    # Natural uranium
    price_U_nat_per_kg_USD: float = 190.0
    transport_U_nat_per_kg_per_km_USD: float = 0.04e-3  # $/kgU/km

    # Conversion
    conversion_per_kgU_USD: float = 15.0
    transport_U_converted_per_kgU_per_km_USD: float = 0.05e-3  # $/kgU/km

    # Enrichment (SWU)
    price_SWU_per_SWU_USD: float = 140.0
    transport_U_enriched_per_kgU_per_km_USD: float = 1.0e-3  # $/kgU/km

    # Fuel fabrication
    fabrication_per_kgFreshFuel_USD: float = 250.0
    transport_fuel_per_kgFreshFuel_per_km_USD: float = 5.0e-3  # $/kg fresh fuel/km

    # --- Back-end fuel cycle costs ---
    # Direct disposal of spent fuel (simplified)
    direct_disposal_per_kgSpentFuel_USD: float = 1300.0
    transport_spent_fuel_per_kg_per_km_USD: float = 6.0e-3  # $/kg spent fuel/km


# ============================================================
# 3. CAPEX
# ============================================================

def compute_capex_USD(project: ProjectParameters, costs: CostParameters) -> float:
    """Total CAPEX (overnight + interest during construction) in $."""
    total_capex_USD = project.n_reactors * costs.cost_per_reactor_USD
    return total_capex_USD

# ============================================================
# 4. OPEX EXCLUDING FUEL
# ============================================================

def compute_opex_total_USD_per_year(project: ProjectParameters, costs: CostParameters) -> float:
    """Non-fuel OPEX ($/year)."""
    # Here we use a single aggregate annual operating cost (already in USD/year).
    return costs.exploitation_cost_per_year_per_reactor_USD * project.n_reactors


# ============================================================
# 5. FUEL CYCLE
# ============================================================


def fuel_cycle_cost_USD_per_year(project: ProjectParameters, costs: CostParameters) -> float:
    """
    Annual fuel cycle cost ($/year):
    - Natural uranium
    - Natural uranium transport (mine to conversion)
    - Conversion
    - Converted uranium transport (conversion to enrichment)
    - Enrichment (SWU)
    - Enriched uranium transport (enrichment to fabrication)
    - Fuel fabrication
    - Fresh fuel transport (fabrication to reactor)
    - Back-end of the cycle (spent fuel)
    - Spent fuel transport (reactor to disposal)
    """
    # Product mass (enriched uranium) per year
    product_mass_kg = annual_enriched_U_mass_kg(project)

    # Optimize front-end (natural U + natural U transport + conversion + converted U transport + enrichment)
    front_end = optimize_front_end_uranium_cost(
        product_mass_kg=product_mass_kg,
        x_U_nat=project.x_U_nat,
        x_U_product=project.x_U_product,
        price_U_nat_per_kg_USD=costs.price_U_nat_per_kg_USD,
        conversion_per_kgU_USD=costs.conversion_per_kgU_USD,
        price_SWU_per_SWU_USD=costs.price_SWU_per_SWU_USD,
        transport_U_nat_per_kg_per_km_USD=costs.transport_U_nat_per_kg_per_km_USD,
        distance_U_nat_transport_km=project.distance_U_nat_transport_km,
        transport_U_converted_per_kgU_per_km_USD=costs.transport_U_converted_per_kgU_per_km_USD,
        distance_U_converted_transport_km=project.distance_U_converted_transport_km,
    )

    cost_U_nat = front_end["cost_U_nat_USD"]
    cost_transport_nat = front_end["cost_transport_U_nat_USD"]
    cost_conversion = front_end["cost_conversion_USD"]
    cost_transport_converted = front_end["cost_transport_U_converted_USD"]
    cost_swu = front_end["cost_enrichment_USD"]
    
    # Enriched uranium transport (enrichment to fabrication)
    cost_transport_enriched = (
        product_mass_kg
        * costs.transport_U_enriched_per_kgU_per_km_USD
        * project.distance_U_enriched_transport_km
    )

    # Fuel fabrication and transport (USD/year)
    fresh_fuel_mass_UO2_kg = annual_fresh_fuel_mass_kg(project)
    cost_fabrication = fresh_fuel_mass_UO2_kg * costs.fabrication_per_kgFreshFuel_USD
    cost_transport_fresh_fuel = (
        fresh_fuel_mass_UO2_kg
        * costs.transport_fuel_per_kgFreshFuel_per_km_USD
        * project.distance_fresh_fuel_transport_km
    )

    # Back-end cycle (assume discharged mass ≈ fresh fuel mass)
    kg_spent_fuel = fresh_fuel_mass_UO2_kg
    cost_backend = kg_spent_fuel * costs.direct_disposal_per_kgSpentFuel_USD
    
    # Spent fuel transport (reactor to disposal)
    cost_transport_spent_fuel = (
        kg_spent_fuel
        * costs.transport_spent_fuel_per_kg_per_km_USD
        * project.distance_spent_fuel_transport_km
    )

    total_fuel_cycle_USD = (
        cost_U_nat
        + cost_transport_nat
        + cost_conversion
        + cost_transport_converted
        + cost_swu
        + cost_transport_enriched
        + cost_fabrication
        + cost_transport_fresh_fuel
        + cost_backend
        + cost_transport_spent_fuel
    )

    return total_fuel_cycle_USD


def detailed_fuel_cycle_breakdown_USD_per_year(project: ProjectParameters, costs: CostParameters) -> dict:
    """Same as fuel_cycle_cost_USD_per_year but with a detailed breakdown ($/year)."""
    product_mass_kg = annual_enriched_U_mass_kg(project)
    front_end = optimize_front_end_uranium_cost(
        product_mass_kg=product_mass_kg,
        x_U_nat=project.x_U_nat,
        x_U_product=project.x_U_product,
        price_U_nat_per_kg_USD=costs.price_U_nat_per_kg_USD,
        conversion_per_kgU_USD=costs.conversion_per_kgU_USD,
        price_SWU_per_SWU_USD=costs.price_SWU_per_SWU_USD,
        transport_U_nat_per_kg_per_km_USD=costs.transport_U_nat_per_kg_per_km_USD,
        distance_U_nat_transport_km=project.distance_U_nat_transport_km,
        transport_U_converted_per_kgU_per_km_USD=costs.transport_U_converted_per_kgU_per_km_USD,
        distance_U_converted_transport_km=project.distance_U_converted_transport_km,
    )

    fresh_fuel_mass_UO2_kg = annual_fresh_fuel_mass_kg(project)

    cost_U_nat = front_end["cost_U_nat_USD"]
    cost_transport_nat = front_end["cost_transport_U_nat_USD"]
    cost_conversion = front_end["cost_conversion_USD"]
    cost_transport_converted = front_end["cost_transport_U_converted_USD"]
    
    cost_enrichment = front_end["cost_enrichment_USD"]
    cost_transport_enriched = (
        product_mass_kg
        * costs.transport_U_enriched_per_kgU_per_km_USD
        * project.distance_U_enriched_transport_km
    )

    cost_fabrication = fresh_fuel_mass_UO2_kg * costs.fabrication_per_kgFreshFuel_USD
    cost_transport_fresh_fuel = (
        fresh_fuel_mass_UO2_kg
        * costs.transport_fuel_per_kgFreshFuel_per_km_USD
        * project.distance_fresh_fuel_transport_km
    )

    cost_back_end = fresh_fuel_mass_UO2_kg * costs.direct_disposal_per_kgSpentFuel_USD
    
    # Spent fuel transport (reactor to disposal)
    cost_transport_spent_fuel = (
        fresh_fuel_mass_UO2_kg
        * costs.transport_spent_fuel_per_kg_per_km_USD
        * project.distance_spent_fuel_transport_km
    )

    return {
        "U_nat": cost_U_nat,
        "transport_U_nat": cost_transport_nat,
        "conversion": cost_conversion,
        "transport_U_converted": cost_transport_converted,
        "SWU": cost_enrichment,
        "transport_U_enriched": cost_transport_enriched,
        "fabrication": cost_fabrication,
        "transport_fresh_fuel": cost_transport_fresh_fuel,
        "back_end": cost_back_end,
        "transport_spent_fuel": cost_transport_spent_fuel,
    }


# ============================================================
# 6. LCOE
# ============================================================

def _get_reactor_construction_schedule(project: ProjectParameters) -> list:
    """
    Calculate construction schedule for each reactor.
    
    Returns a list of tuples: (reactor_index, construction_start_year, construction_end_year, operation_end_year)
    where years are 1-indexed (year 1 is the first year).
    """
    schedule = []
    first_construct = int(round(project.first_reactor_construction_time_years))
    delay = project.delay_between_reactors_years
    
    for i in range(project.n_reactors):
        construction_start = int(round(i * delay)) + 1  # Year when construction starts (1-indexed)
        construction_end = construction_start + first_construct - 1  # Year when construction ends (1-indexed)
        operation_end = construction_end + project.reactors_lifetime_years  # Year when reactor shuts down
        
        schedule.append((i, construction_start, construction_end, operation_end))
    
    return schedule


def _get_reactors_operational_in_year(project: ProjectParameters, year: int) -> int:
    """
    Get the number of reactors operational in a given year (1-indexed).
    """
    schedule = _get_reactor_construction_schedule(project)
    count = 0
    for _, construction_start, construction_end, operation_end in schedule:
        if construction_end < year <= operation_end:
            count += 1
    return count


def _get_capex_spending_in_year(project: ProjectParameters, costs: CostParameters, year: int) -> float:
    """
    Get CAPEX spending in a given year (1-indexed).
    Each reactor's CAPEX is spread evenly over its construction period.
    """
    schedule = _get_reactor_construction_schedule(project)
    cost_per_reactor = costs.cost_per_reactor_USD
    first_construct = project.first_reactor_construction_time_years
    
    total_spending = 0.0
    for _, construction_start, construction_end, _ in schedule:
        if construction_start <= year <= construction_end:
            # This reactor is being constructed this year
            # Spread its cost evenly over construction period
            annual_spend = cost_per_reactor / first_construct
            total_spending += annual_spend
    
    return total_spending


def compute_lcoe_USD_per_MWh(project: ProjectParameters, costs: CostParameters) -> float:
    """
    LCOE in $/MWh using a discounted cash-flow formulation with staggered construction.
    Here we use costs computed with their present values today. Therefore we use the real discount rate and not the nominal discount rate.

    We compute:

        LCOE = sum_t [ C_t / (1 + r)^t ]  /  sum_t [ E_t / (1 + r)^t ]

    where:
        - C_t is the net cost in year t
        - E_t is the electricity produced in year t (MWh)
        - r   is the real discount rate

    Assumptions:
        - Reactors are built with staggered construction:
          - First reactor: first_reactor_construction_time_years
          - Subsequent reactors: start with delay_between_reactors_years between them
        - Each reactor's CAPEX is spread evenly over its own construction period
        - Energy production starts gradually as each reactor comes online
        - OPEX and fuel costs scale with number of operational reactors
        - Each reactor operates for reactors_lifetime_years after its construction ends
    """
    r = costs.real_discount_rate
    
    # Get construction schedule
    schedule = _get_reactor_construction_schedule(project)
    if not schedule:
        raise ValueError("No reactors in project")
    
    # Find the last year any reactor is operational
    last_operation_year = max(operation_end for _, _, _, operation_end in schedule)
    
    # Per-reactor annual values
    annual_opex_per_reactor = costs.exploitation_cost_per_year_per_reactor_USD
    annual_fuel_per_reactor = fuel_cycle_cost_USD_per_year(project, costs) / project.n_reactors
    annual_energy_per_reactor = annual_energy_MWh(project) / project.n_reactors  # MWh/year per reactor
    
    # Total dismantling cost
    total_dismantling = project.n_reactors * costs.dismantling_cost_per_reactor_USD
    
    discounted_costs = 0.0
    discounted_energy = 0.0
    
    # Iterate over all years from 1 to last_operation_year
    for year in range(1, last_operation_year + 1):
        discount_factor = (1.0 + r) ** (-year)
        
        # CAPEX spending this year
        year_capex = _get_capex_spending_in_year(project, costs, year)
        
        # Number of operational reactors this year
        n_operational = _get_reactors_operational_in_year(project, year)
        
        # OPEX and fuel costs (only for operational reactors)
        year_opex = n_operational * annual_opex_per_reactor
        year_fuel = n_operational * annual_fuel_per_reactor
        
        # Energy production (only from operational reactors)
        year_energy = n_operational * annual_energy_per_reactor
        
        # Total cost this year
        year_cost = year_capex + year_opex + year_fuel
        
        discounted_costs += year_cost * discount_factor
        discounted_energy += year_energy * discount_factor
    
    # Add dismantling costs (each reactor at end of its lifetime)
    for _, _, construction_end, operation_end in schedule:
        if total_dismantling > 0:
            dismantling_year = operation_end
            dismantling_discount_factor = (1.0 + r) ** (-dismantling_year)
            dismantling_per_reactor = costs.dismantling_cost_per_reactor_USD
            discounted_costs += dismantling_per_reactor * dismantling_discount_factor
    
    if discounted_energy <= 0:
        raise ValueError("Discounted energy is zero or negative in compute_lcoe_USD_per_MWh().")
    
    return discounted_costs / discounted_energy


def compute_discounted_costs_breakdown(project: ProjectParameters, costs: CostParameters) -> dict:
    """
    Compute discounted costs separately for CAPEX, OPEX, Fuel Cycle, and Dismantling.
    Handles staggered construction and gradual energy production.
    
    Returns a dictionary with:
    - "discounted_capex_USD": total discounted CAPEX
    - "discounted_opex_USD": total discounted OPEX
    - "discounted_fuel_USD": total discounted fuel cycle cost
    - "discounted_dismantling_USD": total discounted dismantling cost
    - "discounted_energy_MWh": total discounted energy production
    """
    r = costs.real_discount_rate
    
    # Get construction schedule
    schedule = _get_reactor_construction_schedule(project)
    if not schedule:
        raise ValueError("No reactors in project")
    
    # Find the last year any reactor is operational
    last_operation_year = max(operation_end for _, _, _, operation_end in schedule)
    
    # Per-reactor annual values
    annual_opex_per_reactor = costs.exploitation_cost_per_year_per_reactor_USD
    annual_fuel_per_reactor = fuel_cycle_cost_USD_per_year(project, costs) / project.n_reactors
    annual_energy_per_reactor = annual_energy_MWh(project) / project.n_reactors  # MWh/year per reactor
    
    discounted_capex = 0.0
    discounted_opex = 0.0
    discounted_fuel = 0.0
    discounted_energy = 0.0
    
    # Iterate over all years from 1 to last_operation_year
    for year in range(1, last_operation_year + 1):
        discount_factor = (1.0 + r) ** (-year)
        
        # CAPEX spending this year
        year_capex = _get_capex_spending_in_year(project, costs, year)
        discounted_capex += year_capex * discount_factor
        
        # Number of operational reactors this year
        n_operational = _get_reactors_operational_in_year(project, year)
        
        # OPEX and fuel costs (only for operational reactors)
        year_opex = n_operational * annual_opex_per_reactor
        year_fuel = n_operational * annual_fuel_per_reactor
        discounted_opex += year_opex * discount_factor
        discounted_fuel += year_fuel * discount_factor
        
        # Energy production (only from operational reactors)
        year_energy = n_operational * annual_energy_per_reactor
        discounted_energy += year_energy * discount_factor
    
    # Add dismantling costs (each reactor at end of its lifetime)
    discounted_dismantling = 0.0
    for _, _, _, operation_end in schedule:
        dismantling_per_reactor = costs.dismantling_cost_per_reactor_USD
        if dismantling_per_reactor > 0:
            dismantling_year = operation_end
            dismantling_discount_factor = (1.0 + r) ** (-dismantling_year)
            discounted_dismantling += dismantling_per_reactor * dismantling_discount_factor
    
    return {
        "discounted_capex_USD": discounted_capex,
        "discounted_opex_USD": discounted_opex,
        "discounted_fuel_USD": discounted_fuel,
        "discounted_dismantling_USD": discounted_dismantling,
        "discounted_energy_MWh": discounted_energy,
    }


def compute_discounted_fuel_cycle_breakdown(project: ProjectParameters, costs: CostParameters) -> dict:
    """
    Compute discounted fuel cycle costs broken down by each step.
    Handles staggered construction - fuel costs scale with number of operational reactors.
    
    Returns a dictionary with discounted costs for each fuel cycle component:
    - "U_nat": natural uranium
    - "transport_U_nat": natural uranium transport (mine to conversion)
    - "conversion": conversion
    - "transport_U_converted": converted uranium transport (conversion to enrichment)
    - "SWU": enrichment
    - "transport_U_enriched": enriched uranium transport (enrichment to fabrication)
    - "fabrication": fuel fabrication
    - "transport_fresh_fuel": fresh fuel transport (fabrication to reactor)
    - "back_end": back-end disposal
    - "transport_spent_fuel": spent fuel transport (reactor to disposal)
    """
    r = costs.real_discount_rate
    
    # Get construction schedule
    schedule = _get_reactor_construction_schedule(project)
    if not schedule:
        raise ValueError("No reactors in project")
    
    # Find the last year any reactor is operational
    last_operation_year = max(operation_end for _, _, _, operation_end in schedule)
    
    # Get annual fuel cycle breakdown (for full plant - we'll scale per reactor)
    annual_breakdown_full = detailed_fuel_cycle_breakdown_USD_per_year(project, costs)
    
    # Convert to per-reactor costs
    annual_breakdown_per_reactor = {
        key: value / project.n_reactors 
        for key, value in annual_breakdown_full.items()
    }
    
    # Discount each component over the operational years, scaling by number of operational reactors
    discounted_breakdown = {}
    for key, annual_cost_per_reactor in annual_breakdown_per_reactor.items():
        discounted_total = 0.0
        for year in range(1, last_operation_year + 1):
            n_operational = _get_reactors_operational_in_year(project, year)
            if n_operational > 0:
                discount_factor = (1.0 + r) ** (-year)
                year_cost = n_operational * annual_cost_per_reactor
                discounted_total += year_cost * discount_factor
        discounted_breakdown[key] = discounted_total
    
    return discounted_breakdown


# ============================================================
# 7. MAIN ENTRY POINT (EXAMPLE CALCULATION)
# ============================================================

def main():
    project = ProjectParameters()
    costs = CostParameters()

    energy = annual_energy_MWh(project)
    product_mass_kg = annual_enriched_U_mass_kg(project)
    front_end = optimize_front_end_uranium_cost(
        product_mass_kg=product_mass_kg,
        x_U_nat=project.x_U_nat,
        x_U_product=project.x_U_product,
        price_U_nat_per_kg_USD=costs.price_U_nat_per_kg_USD,
        conversion_per_kgU_USD=costs.conversion_per_kgU_USD,
        price_SWU_per_SWU_USD=costs.price_SWU_per_SWU_USD,
        transport_U_nat_per_kg_per_km_USD=costs.transport_U_nat_per_kg_per_km_USD,
        distance_U_nat_transport_km=project.distance_U_nat_transport_km,
        transport_U_converted_per_kgU_per_km_USD=costs.transport_U_converted_per_kgU_per_km_USD,
        distance_U_converted_transport_km=project.distance_U_converted_transport_km,
    )
    fresh_fuel_mass_UO2_kg = annual_fresh_fuel_mass_kg(project)

    capex_total = compute_capex_USD(project, costs)
    dismantling_total = project.n_reactors * costs.dismantling_cost_per_reactor_USD
    opex_annual = compute_opex_total_USD_per_year(project, costs)
    fuel_annual = fuel_cycle_cost_USD_per_year(project, costs)
    fuel_breakdown = detailed_fuel_cycle_breakdown_USD_per_year(project, costs)
    lcoe = compute_lcoe_USD_per_MWh(project, costs)

    # ------------------------------------------------------------
    # 1) INPUT PARAMETERS - PROJECT
    # ------------------------------------------------------------
    print("=== Nuclear project – VVER in Serbia (simplified model) ===")
    print(">> Input parameters - Project")
    print(f"  country                           : {project.country}")
    print(f"  reactor_type                      : {project.reactor_type}")
    print(f"  n_reactors                        : {project.n_reactors}")
    print(f"  power_electric_per_reactor_MWe     : {project.power_electric_per_reactor_MWe:.0f} MWe")
    print(f"  net_capacity_factor               : {project.net_capacity_factor:.3f}")
    print(f"  first_reactor_construction_time_years: {project.first_reactor_construction_time_years:.1f} years")
    print(f"  delay_between_reactors_years         : {project.delay_between_reactors_years:.1f} years")
    print(f"  reactors_lifetime_years           : {project.reactors_lifetime_years} years")
    print(f"  x_U_nat                           : {project.x_U_nat:.5f}")
    print(f"  x_U_product                       : {project.x_U_product:.5f}")
    print(f"  assemblies_per_core               : {project.assemblies_per_core}")
    print(f"  fuel_mass_per_assembly_kg         : {project.fuel_mass_per_assembly_kg:.1f} kgUO2")
    print(f"  batch_fraction                    : {project.batch_fraction:.3f}")
    print(f"  cycle_length_years                : {project.cycle_length_years:.3f} years")
    print(f"  spent_fuel_backend                : {project.spent_fuel_backend}")
    print(f"  distance_U_nat_transport_km        : {project.distance_U_nat_transport_km:.0f} km")
    print(f"  distance_U_converted_transport_km  : {project.distance_U_converted_transport_km:.0f} km")
    print(f"  distance_U_enriched_transport_km  : {project.distance_U_enriched_transport_km:.0f} km")
    print(f"  distance_fresh_fuel_transport_km   : {project.distance_fresh_fuel_transport_km:.0f} km")
    print(f"  distance_spent_fuel_transport_km   : {project.distance_spent_fuel_transport_km:.0f} km")
    print()

    # ------------------------------------------------------------
    # 2) INPUT PARAMETERS - COSTS
    # ------------------------------------------------------------
    print(">> Input parameters - Costs")
    print(f"  real_discount_rate                : {costs.real_discount_rate:.3f}")
    print(f"  cost_per_reactor_USD              : {costs.cost_per_reactor_USD/1e9:.3f} B$ ({costs.cost_per_reactor_USD:,.0f} $)")
    print(f"  dismantling_cost_per_reactor_USD   : {costs.dismantling_cost_per_reactor_USD/1e9:.3f} B$ ({costs.dismantling_cost_per_reactor_USD:,.0f} $)")
    print(f"  exploitation_cost_per_year_per_reactor_USD : {costs.exploitation_cost_per_year_per_reactor_USD/1e6:.2f} M$/year ({costs.exploitation_cost_per_year_per_reactor_USD:,.0f} $/year)")
    print(f"  price_U_nat_per_kg_USD            : {costs.price_U_nat_per_kg_USD:.1f} $/kgU")
    print(f"  conversion_per_kgU_USD            : {costs.conversion_per_kgU_USD:.1f} $/kgU")
    print(f"  price_SWU_per_SWU_USD             : {costs.price_SWU_per_SWU_USD:.1f} $/SWU")
    print(f"  fabrication_per_kgFreshFuel_USD   : {costs.fabrication_per_kgFreshFuel_USD:.1f} $/kg fresh fuel")
    print(f"  direct_disposal_per_kgSpentFuel_USD : {costs.direct_disposal_per_kgSpentFuel_USD:.1f} $/kg spent fuel")
    print(f"  transport_U_nat_per_kg_per_km_USD : {costs.transport_U_nat_per_kg_per_km_USD:.3e} $/kgU/km")
    print(f"  transport_U_converted_per_kgU_per_km_USD : {costs.transport_U_converted_per_kgU_per_km_USD:.3e} $/kgU/km")
    print(f"  transport_U_enriched_per_kgU_per_km_USD : {costs.transport_U_enriched_per_kgU_per_km_USD:.3e} $/kgU/km")
    print(f"  transport_fuel_per_kgFreshFuel_per_km_USD : {costs.transport_fuel_per_kgFreshFuel_per_km_USD:.3e} $/kg/km")
    print(f"  transport_spent_fuel_per_kg_per_km_USD : {costs.transport_spent_fuel_per_kg_per_km_USD:.3e} $/kg/km")
    print()

    # ------------------------------------------------------------
    # 3) OUTPUT PARAMETERS - PROJECT
    # ------------------------------------------------------------
    print(">> Output parameters - Project")
    print(f"  Net annual production              : {energy/1e6:.3f} TWh/year")
    print(f"  Optimal x_tails                    : {front_end['x_tails_opt']:.5f}")
    print(f"  Annual fresh fuel (UO2)           : {fresh_fuel_mass_UO2_kg/1e3:.3f} tUO2/year")
    print(f"  Annual enriched U (U)              : {product_mass_kg/1e3:.3f} tU/year")
    print(f"  Optimal natural U feed             : {front_end['M_U_nat_kg']/1e3:.3f} tU/year")
    print()

    # ------------------------------------------------------------
    # 4) OUTPUT PARAMETERS - COSTS
    # ------------------------------------------------------------
    print(">> Output parameters - Costs")
    print(f"  Total CAPEX                        : {capex_total/1e9:.3f} B$ ({capex_total:,.0f} $)")
    print(f"  Total dismantling cost              : {dismantling_total/1e9:.3f} B$ ({dismantling_total:,.0f} $)")
    print(f"  OPEX (excl. fuel)                  : {opex_annual/1e6:.2f} M$/year ({opex_annual:,.0f} $/year)")
    print(f"  Fuel cycle cost (total)             : {fuel_annual/1e6:.2f} M$/year ({fuel_annual:,.0f} $/year)")
    print("  Fuel cycle breakdown:")
    for k, v in fuel_breakdown.items():
        print(f"    - {k:20s}: {v/1e6:.3f} M$/year ({v:,.0f} $/year)")
    print()

    # ------------------------------------------------------------
    # 5) RESULTING LCOE
    # ------------------------------------------------------------
    print(">> Resulting LCOE")
    print(f"  LCOE ≈ {lcoe:.1f} $/MWh")


if __name__ == "__main__":
    main()


