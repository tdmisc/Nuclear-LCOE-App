
import math
from Simple_Conversion_Functions import UO2_to_U


### Energy production ###
def annual_energy_MWh(params) -> float:
    """
    Net annual electricity production in MWh.

    `params` must provide the attributes:
    - n_reactors
    - power_electric_per_reactor_MWe
    - net_capacity_factor
    """
    total_power_MW = params.n_reactors * params.power_electric_per_reactor_MWe
    hours_year = 8760.0
    return total_power_MW * hours_year * params.net_capacity_factor

### Fuel in reactors ###
def fuel_mass_per_reactorkg(project) -> float:
    """Fuel mass in core (kgU)."""
    return project.assemblies_per_core * project.fuel_mass_per_assembly_kg


def fresh_fuel_mass_per_cycle_per_reactor_kg(project) -> float:
    """Fresh fuel mass loaded per cycle (kgU)."""
    return fuel_mass_per_reactorkg(project) * project.batch_fraction


def annual_fresh_fuel_mass_kg(project) -> float:
    """Annual fresh fuel mass (kgU/year)."""
    return fresh_fuel_mass_per_cycle_per_reactor_kg(project) * project.n_reactors / project.cycle_length_years

def annual_enriched_U_mass_kg(project) -> float:
    """Annual Enriched Uranium mass (kgU/year)."""
    return UO2_to_U(annual_fresh_fuel_mass_kg(project))


### Front-end uranium and enrichment optimization ###

def _V_swu(x: float) -> float:
    """
    Value function used in SWU calculations.

    Same mathematical form as in the main script:
        V(x) = (1 - 2x) * ln((1 - x) / x)
    """
    return (1.0 - 2.0 * x) * math.log((1.0 - x) / x)


def optimize_front_end_uranium_cost(
    product_mass_kg: float,
    x_U_nat: float,
    x_U_product: float,
    price_U_nat_per_kg_USD: float,
    conversion_per_kgU_USD: float,
    price_SWU_per_SWU_USD: float,
    transport_U_nat_per_kg_per_km_USD: float = 0.0,
    distance_U_nat_transport_km: float = 0.0,
    tails_min: float = 0.0005,
    n_steps: int = 500,
    ) -> dict:
    """
    Optimize the front-end fuel cycle cost (natural U + transport + conversion + enrichment)
    for a given required product mass.

    Arguments
    ---------
    product_mass_kg : float
        Required mass of enriched uranium product (kgU).
    x_U_nat : float
        U-235 fraction in natural uranium (feed).
    x_U_product : float
        U-235 fraction in enriched product.
    price_U_nat_per_kg_USD : float
        Price of natural uranium ($/kgU).
    conversion_per_kgU_USD : float
        Conversion cost ($/kgU of feed).
    price_SWU_per_SWU_USD : float
        Enrichment cost ($/SWU).
    transport_U_nat_per_kg_per_km_USD : float
        Transport cost per kgU per km for natural uranium ($/kgU/km).
    distance_U_nat_transport_km : float
        Transport distance for natural uranium (km).
    tails_min : float
        Minimum tails assay to scan (U-235 fraction in tails).
    n_steps : int
        Number of steps in the search grid for the tails assay.

    Returns
    -------
    dict with keys:
        - "M_U_nat_kg"          : optimal natural uranium mass (kg)
        - "x_tails_opt"         : optimal tails U-235 fraction
        - "cost_U_nat_USD"      : cost of natural uranium ($)
        - "cost_transport_U_nat_USD" : cost of natural uranium transport ($)
        - "cost_conversion_USD" : cost of conversion ($)
        - "cost_enrichment_USD" : cost of enrichment ($)
    """
    if product_mass_kg <= 0:
        raise ValueError(
            "Product mass must be strictly positive in optimize_front_end_uranium_cost()."
        )

    best_cost = float("inf")
    best_results = None

    # Simple grid search on tails assay between tails_min and x_U_nat
    step = (x_U_nat - tails_min) / n_steps
    for i in range(n_steps):
        x_tails = tails_min + i * step

        # Avoid degenerate cases where denominator would vanish
        if abs(x_U_nat - x_tails) < 1e-8:
            continue

        # Mass balance to compute feed (natural uranium) from product and tails assay
        feed_mass_kg = product_mass_kg * (x_U_product - x_tails) / (x_U_nat - x_tails)  # feed mass (kgU nat)
        if feed_mass_kg <= 0:
            continue

        tails_mass_kg = feed_mass_kg - product_mass_kg  # tails mass

        # SWU requirement
        swu_required = (
            product_mass_kg * _V_swu(x_U_product)
            + tails_mass_kg * _V_swu(x_tails)
            - feed_mass_kg * _V_swu(x_U_nat)
        )
        if swu_required <= 0:
            continue

        # Cost components
        cost_U_nat = feed_mass_kg * price_U_nat_per_kg_USD
        cost_transport_U_nat = feed_mass_kg * transport_U_nat_per_kg_per_km_USD * distance_U_nat_transport_km
        cost_conversion = feed_mass_kg * conversion_per_kgU_USD
        cost_enrichment = swu_required * price_SWU_per_SWU_USD

        total_cost = cost_U_nat + cost_transport_U_nat + cost_conversion + cost_enrichment

        if total_cost < best_cost:
            best_cost = total_cost
            best_results = {
                "M_U_nat_kg": feed_mass_kg,
                "x_tails_opt": x_tails,
                "cost_U_nat_USD": cost_U_nat,
                "cost_transport_U_nat_USD": cost_transport_U_nat,
                "cost_conversion_USD": cost_conversion,
                "cost_enrichment_USD": cost_enrichment,
            }

    # In case no valid point was found (should be rare), explicitly raise an error
    if best_results is None:
        raise ValueError(
            "No valid combination of tails assay and feed mass was found "
            "for the given inputs in optimize_front_end_uranium_cost()."
        )

    return best_results

