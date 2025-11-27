"""
Streamlit app for nuclear power plant LCOE calculation.

This app provides an interactive interface to input project and cost parameters
and compute the Levelized Cost of Electricity (LCOE) for a nuclear power plant.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import importlib.util
import matplotlib.pyplot as plt

# Get the absolute path to the app directory (where app.py is located)
current_file = Path(__file__).resolve()
app_dir = current_file.parent

# Add app directory to Python path
app_dir_str = str(app_dir)
if app_dir_str not in sys.path:
    sys.path.insert(0, app_dir_str)

# Add Annex Functions directory to Python path
annex_dir = str(app_dir / "Annex Functions")
if annex_dir not in sys.path:
    sys.path.insert(0, annex_dir)

import streamlit as st

# Import main computation module using importlib for more robust loading
pwr_module_path = app_dir / "PWR_Costs_computation.py"
if not pwr_module_path.exists():
    raise FileNotFoundError(
        f"Could not find PWR_Costs_computation.py at {pwr_module_path}. "
        f"Current working directory: {os.getcwd()}, App dir: {app_dir}"
    )

spec = importlib.util.spec_from_file_location("PWR_Costs_computation", pwr_module_path)
pwr_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pwr_module)

ProjectParameters = pwr_module.ProjectParameters
CostParameters = pwr_module.CostParameters
compute_capex_USD = pwr_module.compute_capex_USD
compute_opex_total_USD_per_year = pwr_module.compute_opex_total_USD_per_year
fuel_cycle_cost_USD_per_year = pwr_module.fuel_cycle_cost_USD_per_year
detailed_fuel_cycle_breakdown_USD_per_year = pwr_module.detailed_fuel_cycle_breakdown_USD_per_year
compute_lcoe_USD_per_MWh = pwr_module.compute_lcoe_USD_per_MWh
compute_discounted_costs_breakdown = pwr_module.compute_discounted_costs_breakdown
compute_discounted_fuel_cycle_breakdown = pwr_module.compute_discounted_fuel_cycle_breakdown

# Import annex functions
annex_module_path = app_dir / "Annex Functions" / "Annex_Cost_Functions.py"
if not annex_module_path.exists():
    raise FileNotFoundError(
        f"Could not find Annex_Cost_Functions.py at {annex_module_path}. "
        f"App dir: {app_dir}"
    )

spec = importlib.util.spec_from_file_location("Annex_Cost_Functions", annex_module_path)
annex_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(annex_module)

annual_energy_MWh = annex_module.annual_energy_MWh
annual_fresh_fuel_mass_kg = annex_module.annual_fresh_fuel_mass_kg
annual_enriched_U_mass_kg = annex_module.annual_enriched_U_mass_kg
optimize_front_end_uranium_cost = annex_module.optimize_front_end_uranium_cost

# Page configuration
st.set_page_config(
    page_title="Nuclear Power Plant LCOE Calculator",
    page_icon="🔋",
    layout="wide",
)

st.title("🔋 Nuclear Power Plant LCOE Calculator")
st.markdown("---")

# Initialize default parameters
default_project = ProjectParameters()
default_costs = CostParameters()

# Input form at the top of the page
st.header("📋 Input Parameters")

# Use tabs to organize the three main sections
tab1, tab2, tab3 = st.tabs(["⚙️ Reactor", "⛽ Fuel Cycle", "💰 Financing Scheme"])

with tab1:
    st.subheader("Reactor Characteristics & Costs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Basic Information**")
        country = st.text_input(
            "Country",
            value=default_project.country,
            help="Country where the plant is located"
        )
        reactor_type = st.text_input(
            "Reactor Type",
            value=default_project.reactor_type,
            help="Type of nuclear reactor"
        )
        n_reactors = st.number_input(
            "Number of Reactors",
            min_value=1,
            value=default_project.n_reactors,
            step=1,
            help="Total number of reactors in the plant"
        )
        power_electric_per_reactor_MWe = st.number_input(
            "Power per Reactor (MWe)",
            min_value=0.0,
            value=float(default_project.power_electric_per_reactor_MWe),
            step=100.0,
            format="%.0f",
            help="Net electrical power per reactor in MWe"
        )
        net_capacity_factor = st.number_input(
            "Net Capacity Factor",
            min_value=0.0,
            max_value=1.0,
            value=float(default_project.net_capacity_factor),
            step=0.01,
            format="%.3f",
            help="Fraction of time the plant operates at full capacity (0-1)"
        )
        first_reactor_construction_time_years = st.number_input(
            "First Reactor Construction Time (years)",
            min_value=0.0,
            value=float(default_project.first_reactor_construction_time_years),
            step=0.5,
            format="%.1f",
            help="Time to build the first reactor in years"
        )
        delay_between_reactors_years = st.number_input(
            "Delay Between Reactors Construction (years)",
            min_value=0.0,
            value=float(default_project.delay_between_reactors_years),
            step=0.5,
            format="%.1f",
            help="Delay between starting construction of each subsequent reactor"
        )
        reactors_lifetime_years = st.number_input(
            "Reactor Lifetime (years)",
            min_value=1,
            value=int(default_project.reactors_lifetime_years),
            step=1,
            help="Expected operational lifetime of reactors"
        )
    
    with col2:
        st.markdown("**Core & Fuel Configuration**")
        assemblies_per_core = st.number_input(
            "Assemblies per Core",
            min_value=1,
            value=default_project.assemblies_per_core,
            step=1,
            help="Number of fuel assemblies in the core"
        )
        fuel_mass_per_assembly_kg = st.number_input(
            "Fuel Mass per Assembly (kgUO2)",
            min_value=0.0,
            value=float(default_project.fuel_mass_per_assembly_kg),
            step=10.0,
            format="%.1f",
            help="Mass of UO2 per fuel assembly"
        )

        x_U_product = st.number_input(
            "Fuel Uranium U-235 Fraction (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_project.x_U_product * 100),
            step=0.1,
            format="%.2f",
            help="U-235 fraction in enriched product as percentage"
        )

        batch_fraction = st.number_input(
            "Refueling Cycle Batch Fraction",
            min_value=0.0,
            max_value=1.0,
            value=float(default_project.batch_fraction),
            step=0.01,
            format="%.3f",
            help="Fraction of core reloaded per cycle"
        )
        cycle_length_years = st.number_input(
            "Refueling Cycle Length (years)",
            min_value=0.0,
            value=float(default_project.cycle_length_years),
            step=0.1,
            format="%.3f",
            help="Duration of one fuel cycle in years"
        )
        spent_fuel_backend = st.selectbox(
            "Spent Fuel Backend",
            options=["direct disposal", "reprocessing"],
            index=0 if default_project.spent_fuel_backend == "direct disposal" else 1,
            help="Backend option for spent fuel management"
        )
        
        st.markdown("**Reactor Costs**")
        cost_per_reactor_BUSD = st.number_input(
            "Cost per Reactor (B$)",
            min_value=0.0,
            value=float(default_costs.cost_per_reactor_USD / 1e9),
            step=0.1,
            format="%.2f",
            help="Overnight cost per reactor in billion USD"
        )
        dismantling_cost_per_reactor_BUSD = st.number_input(
            "Dismantling Cost per Reactor (B$)",
            min_value=0.0,
            value=float(default_costs.dismantling_cost_per_reactor_USD / 1e9),
            step=0.1,
            format="%.2f",
            help="Decommissioning cost per reactor in billion USD"
        )
        exploitation_cost_per_year_per_reactor_MUSD = st.number_input(
            "Exploitation Cost per Reactor per Year (M$/year)",
            min_value=0.0,
            value=float(default_costs.exploitation_cost_per_year_per_reactor_USD / 1e6),
            step=10.0,
            format="%.1f",
            help="Annual operating cost per reactor (staff, maintenance, etc.) in million USD"
        )
        

with tab2:
    st.subheader("Fuel Cycle Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Fuel Cycle Unit Costs**")
        price_U_nat_per_kg_USD = st.number_input(
            "Natural Uranium Price ($/kgU)",
            min_value=0.0,
            value=float(default_costs.price_U_nat_per_kg_USD),
            step=10.0,
            format="%.1f",
            help="Price of natural uranium per kg"
        )
        conversion_per_kgU_USD = st.number_input(
            "Conversion Cost ($/kgU)",
            min_value=0.0,
            value=float(default_costs.conversion_per_kgU_USD),
            step=1.0,
            format="%.1f",
            help="Conversion cost per kg of uranium"
        )
        price_SWU_per_SWU_USD = st.number_input(
            "Enrichment Price ($/SWU)",
            min_value=0.0,
            value=float(default_costs.price_SWU_per_SWU_USD),
            step=10.0,
            format="%.1f",
            help="Enrichment cost per SWU"
        )
        fabrication_per_kgFreshFuel_USD = st.number_input(
            "Fuel Fabrication Cost ($/kg fresh fuel)",
            min_value=0.0,
            value=float(default_costs.fabrication_per_kgFreshFuel_USD),
            step=10.0,
            format="%.1f",
            help="Fuel fabrication cost per kg"
        )
        direct_disposal_per_kgSpentFuel_USD = st.number_input(
            "Direct Disposal Cost ($/kg spent fuel)",
            min_value=0.0,
            value=float(default_costs.direct_disposal_per_kgSpentFuel_USD),
            step=100.0,
            format="%.1f",
            help="Back-end disposal cost per kg of spent fuel"
        )
    
    with col2:
        st.markdown("**Transport Distances (km)**")
        distance_U_nat_transport_km = st.number_input(
            "Natural Uranium Transport Distance (km)",
            min_value=0.0,
            value=float(default_project.distance_U_nat_transport_km),
            step=100.0,
            format="%.0f",
            help="Distance for natural uranium transport"
        )
        distance_U_enriched_transport_km = st.number_input(
            "Enriched Uranium Transport Distance (km)",
            min_value=0.0,
            value=float(default_project.distance_U_enriched_transport_km),
            step=100.0,
            format="%.0f",
            help="Distance for enriched uranium transport"
        )
        distance_fresh_fuel_transport_km = st.number_input(
            "Fresh Fuel Transport Distance (km)",
            min_value=0.0,
            value=float(default_project.distance_fresh_fuel_transport_km),
            step=100.0,
            format="%.0f",
            help="Distance for fresh fuel transport"
        )
        
        st.markdown("**Transport Unit Costs**")
        transport_U_nat_per_kg_per_km_USD = st.number_input(
            "Natural Uranium Transport ($/kgU/km)",
            min_value=0.0,
            value=float(default_costs.transport_U_nat_per_kg_per_km_USD),
            step=1e-5,
            format="%.3e",
            help="Transport cost per kgU per km for natural uranium"
        )
        transport_U_enriched_per_kgU_per_km_USD = st.number_input(
            "Enriched Uranium Transport ($/kgU/km)",
            min_value=0.0,
            value=float(default_costs.transport_U_enriched_per_kgU_per_km_USD),
            step=1e-4,
            format="%.3e",
            help="Transport cost per kgU per km for enriched uranium"
        )
        transport_fuel_per_kgFreshFuel_per_km_USD = st.number_input(
            "Fresh Fuel Transport ($/kg/km)",
            min_value=0.0,
            value=float(default_costs.transport_fuel_per_kgFreshFuel_per_km_USD),
            step=1e-4,
            format="%.3e",
            help="Transport cost per kg per km for fresh fuel"
        )

with tab3:
    st.subheader("Financing Scheme")
    
    real_discount_rate = st.number_input(
        "Real Discount Rate",
        min_value=0.0,
        max_value=1.0,
        value=float(default_costs.real_discount_rate),
        step=0.001,
        format="%.3f",
        help="Real discount rate (net of inflation)"
    )

st.markdown("---")

# Compute button
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    compute_button = st.button("🚀 Compute LCOE", type="primary", use_container_width=True)

if compute_button:
    try:
        # Create parameter objects
        # Note: x_U_nat is kept as default value (0.00711), not from form input
        project = ProjectParameters(
            country=country,
            reactor_type=reactor_type,
            n_reactors=n_reactors,
            power_electric_per_reactor_MWe=power_electric_per_reactor_MWe,
            net_capacity_factor=net_capacity_factor,
            first_reactor_construction_time_years=first_reactor_construction_time_years,
            delay_between_reactors_years=delay_between_reactors_years,
            reactors_lifetime_years=reactors_lifetime_years,
            x_U_product=x_U_product / 100.0,  # Convert from percentage to fraction
            assemblies_per_core=assemblies_per_core,
            fuel_mass_per_assembly_kg=fuel_mass_per_assembly_kg,
            batch_fraction=batch_fraction,
            cycle_length_years=cycle_length_years,
            spent_fuel_backend=spent_fuel_backend,
            distance_U_nat_transport_km=distance_U_nat_transport_km,
            distance_U_enriched_transport_km=distance_U_enriched_transport_km,
            distance_fresh_fuel_transport_km=distance_fresh_fuel_transport_km,
        )
        
        costs = CostParameters(
            real_discount_rate=real_discount_rate,
            cost_per_reactor_USD=cost_per_reactor_BUSD * 1e9,  # Convert from B$ to USD
            dismantling_cost_per_reactor_USD=dismantling_cost_per_reactor_BUSD * 1e9,  # Convert from B$ to USD
            exploitation_cost_per_year_per_reactor_USD=exploitation_cost_per_year_per_reactor_MUSD * 1e6,  # Convert from M$/year to USD/year
            price_U_nat_per_kg_USD=price_U_nat_per_kg_USD,
            conversion_per_kgU_USD=conversion_per_kgU_USD,
            price_SWU_per_SWU_USD=price_SWU_per_SWU_USD,
            fabrication_per_kgFreshFuel_USD=fabrication_per_kgFreshFuel_USD,
            direct_disposal_per_kgSpentFuel_USD=direct_disposal_per_kgSpentFuel_USD,
            transport_U_nat_per_kg_per_km_USD=transport_U_nat_per_kg_per_km_USD,
            transport_U_enriched_per_kgU_per_km_USD=transport_U_enriched_per_kgU_per_km_USD,
            transport_fuel_per_kgFreshFuel_per_km_USD=transport_fuel_per_kgFreshFuel_per_km_USD,
        )
        
        # Run computations
        with st.spinner("Computing LCOE..."):
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
            )
            fresh_fuel_mass_UO2_kg = annual_fresh_fuel_mass_kg(project)
            
            capex_total = compute_capex_USD(project, costs)
            dismantling_total = project.n_reactors * costs.dismantling_cost_per_reactor_USD
            opex_annual = compute_opex_total_USD_per_year(project, costs)
            fuel_annual = fuel_cycle_cost_USD_per_year(project, costs)
            fuel_breakdown = detailed_fuel_cycle_breakdown_USD_per_year(project, costs)
            lcoe = compute_lcoe_USD_per_MWh(project, costs)
        
        # Display results
        st.success("✅ Computation completed successfully!")
        st.markdown("---")
        
        # 1. Electricity Production
        st.header("⚡ Electricity Production")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Net Annual Production", f"{energy/1e6:.3f} TWh/year")
        with col2:
            st.metric("Levelized Cost of Electricity (LCOE)", f"{lcoe:.1f} $/MWh")
        
        st.markdown("---")
        
        # 2. Resource Cycle
        st.header("🔄 Resource Cycle")
        col1, col2 = st.columns(2)
        
        # Calculate tail mass
        tail_mass_kg = front_end['M_U_nat_kg'] - product_mass_kg
        
        with col1:
            st.metric("Natural U-235 Fraction", f"{project.x_U_nat * 100:.3f}%")
            st.metric("Tail Fraction", f"{front_end['x_tails_opt'] * 100:.3f}%")
            st.metric("Enriched U-235 Fraction", f"{project.x_U_product * 100:.2f}%")
        
        with col2:
            st.metric("Natural Uranium", f"{front_end['M_U_nat_kg']/1e3:.3f} tU/year")
            st.metric("Depleted Uranium", f"{tail_mass_kg/1e3:.3f} tU/year")
            st.metric("Enriched Uranium", f"{product_mass_kg/1e3:.3f} tU/year")
        
        st.markdown("---")
        
        # 3. Total Cost Overview
        st.header("💰 Total Cost Overview")
        
        # Calculate annualized CAPEX for the table
        # We need to import the capital recovery factor function
        def capital_recovery_factor(r: float, n: int) -> float:
            return r * (1 + r) ** n / ((1 + r) ** n - 1)
        
        crf = capital_recovery_factor(costs.real_discount_rate, project.reactors_lifetime_years)
        annualized_capex = capex_total * crf
        annualized_dismantling = dismantling_total / project.reactors_lifetime_years  # Simplified: spread over lifetime
        
        # 3.1 Fixed Cost Overview
        st.subheader("📌 Fixed Cost Overview")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total CAPEX", f"${capex_total/1e9:.3f} B")
        with col2:
            st.metric("Total Dismantling", f"${dismantling_total/1e9:.3f} B")
        
        st.markdown("---")
        
        # 3.2 Annualized Total Costs Overview
        st.subheader("📅 Annualized Total Costs Overview")
        
        # Calculate total annual cost
        total_annual_cost = annualized_capex + annualized_dismantling + opex_annual + fuel_annual
        
        # Create comprehensive cost table
        cost_data = {
            "Cost Category": [
                "CAPEX (annualized)",
                "Dismantling (annualized)",
                "OPEX (excluding fuel)",
                "Fuel Cycle - Natural Uranium",
                "Fuel Cycle - U_nat Transport",
                "Fuel Cycle - Conversion",
                "Fuel Cycle - Enrichment (SWU)",
                "Fuel Cycle - U_enriched Transport",
                "Fuel Cycle - Fabrication",
                "Fuel Cycle - Fresh Fuel Transport",
                "Fuel Cycle - Back-end Disposal",
                "Fuel Cycle - Total",
                "**Total Annual Cost**",
            ],
            "Annual Cost (M$/year)": [
                annualized_capex / 1e6,
                annualized_dismantling / 1e6,
                opex_annual / 1e6,
                fuel_breakdown.get("U_nat", 0) / 1e6,
                fuel_breakdown.get("transport_U_nat", 0) / 1e6,
                fuel_breakdown.get("conversion", 0) / 1e6,
                fuel_breakdown.get("SWU", 0) / 1e6,
                fuel_breakdown.get("transport_U_enriched", 0) / 1e6,
                fuel_breakdown.get("fabrication", 0) / 1e6,
                fuel_breakdown.get("transport_fuel", 0) / 1e6,
                fuel_breakdown.get("back_end", 0) / 1e6,
                fuel_annual / 1e6,
                total_annual_cost / 1e6,
            ],
        }
        
        cost_df = pd.DataFrame(cost_data)
        st.dataframe(cost_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # 3.3 LCOE Cost Breakdown
        st.subheader("📊 LCOE Cost Breakdown")
        
        # Compute discounted costs breakdown
        discounted_breakdown = compute_discounted_costs_breakdown(project, costs)
        discounted_energy = discounted_breakdown["discounted_energy_MWh"]
        
        # Calculate LCOE contributions (each component divided by discounted energy)
        lcoe_capex = discounted_breakdown["discounted_capex_USD"] / discounted_energy
        lcoe_opex = discounted_breakdown["discounted_opex_USD"] / discounted_energy
        lcoe_fuel = discounted_breakdown["discounted_fuel_USD"] / discounted_energy
        lcoe_dismantling = discounted_breakdown["discounted_dismantling_USD"] / discounted_energy
        # Use the actual computed LCOE as the total for consistency
        lcoe_total = lcoe
        
        # Calculate percentages
        pct_capex = (lcoe_capex / lcoe_total) * 100 if lcoe_total > 0 else 0
        pct_opex = (lcoe_opex / lcoe_total) * 100 if lcoe_total > 0 else 0
        pct_fuel = (lcoe_fuel / lcoe_total) * 100 if lcoe_total > 0 else 0
        pct_dismantling = (lcoe_dismantling / lcoe_total) * 100 if lcoe_total > 0 else 0
        
        # Create LCOE breakdown pie chart
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("LCOE Breakdown by Cost Category")
            lcoe_data = {
                "Category": ["CAPEX", "OPEX", "Fuel Cycle", "Dismantling"],
                "Value": [lcoe_capex, lcoe_opex, lcoe_fuel, lcoe_dismantling],
                "Percentage": [pct_capex, pct_opex, pct_fuel, pct_dismantling]
            }
            lcoe_df = pd.DataFrame(lcoe_data)
            
            # Create matplotlib pie chart
            fig_lcoe, ax_lcoe = plt.subplots(figsize=(8, 8))
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
            wedges, texts, autotexts = ax_lcoe.pie(
                lcoe_df["Value"],
                labels=lcoe_df["Category"],
                autopct='%1.1f%%',
                startangle=90,
                colors=colors[:len(lcoe_df)]
            )
            ax_lcoe.set_title("LCOE Breakdown (%)", fontsize=14, fontweight='bold')
            plt.setp(autotexts, size=10, weight="bold")
            plt.setp(texts, size=10)
            plt.tight_layout()
            st.pyplot(fig_lcoe)
            plt.close(fig_lcoe)
            
            # Display table with values
            st.markdown("**Cost Contributions to LCOE:**")
            display_df = pd.DataFrame({
                "Category": ["CAPEX", "OPEX", "Fuel Cycle", "Dismantling", "**Total**"],
                "Cost ($/MWh)": [
                    f"{lcoe_capex:.2f}",
                    f"{lcoe_opex:.2f}",
                    f"{lcoe_fuel:.2f}",
                    f"{lcoe_dismantling:.2f}",
                    f"**{lcoe_total:.2f}**"
                ],
                "Percentage (%)": [
                    f"{pct_capex:.1f}",
                    f"{pct_opex:.1f}",
                    f"{pct_fuel:.1f}",
                    f"{pct_dismantling:.1f}",
                    "**100.0**"
                ]
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("Fuel Cycle Cost Breakdown")
            
            # Compute discounted fuel cycle breakdown
            fuel_breakdown_discounted = compute_discounted_fuel_cycle_breakdown(project, costs)
            total_fuel_discounted = sum(fuel_breakdown_discounted.values())
            
            # Prepare data for pie chart
            fuel_labels = {
                "U_nat": "Natural Uranium",
                "transport_U_nat": "Transport Natural U",
                "conversion": "Conversion",
                "SWU": "Enrichment (SWU)",
                "transport_U_enriched": "Transport Enriched U",
                "fabrication": "Fabrication",
                "transport_fuel": "Transport Fuel",
                "back_end": "Back-end Disposal"
            }
            
            fuel_data = []
            for key, value in fuel_breakdown_discounted.items():
                if total_fuel_discounted > 0:
                    pct = (value / total_fuel_discounted) * 100
                else:
                    pct = 0.0
                fuel_data.append({
                    "Category": fuel_labels.get(key, key),
                    "Value": value,
                    "Percentage": pct
                })
            
            fuel_df = pd.DataFrame(fuel_data)
            
            # Create matplotlib pie chart
            fig_fuel, ax_fuel = plt.subplots(figsize=(8, 8))
            colors_fuel = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#95E1D3', '#F38181', '#AA96DA', '#FCBAD3']
            wedges, texts, autotexts = ax_fuel.pie(
                fuel_df["Value"],
                labels=fuel_df["Category"],
                autopct='%1.1f%%',
                startangle=90,
                colors=colors_fuel[:len(fuel_df)]
            )
            ax_fuel.set_title("Fuel Cycle Breakdown (%)", fontsize=14, fontweight='bold')
            plt.setp(autotexts, size=9, weight="bold")
            plt.setp(texts, size=9)
            plt.tight_layout()
            st.pyplot(fig_fuel)
            plt.close(fig_fuel)
            
            # Display table with values
            st.markdown("**Fuel Cycle Cost Contributions:**")
            fuel_display_data = []
            for key, label in fuel_labels.items():
                value = fuel_breakdown_discounted.get(key, 0)
                if total_fuel_discounted > 0:
                    pct = (value / total_fuel_discounted) * 100
                else:
                    pct = 0.0
                fuel_display_data.append({
                    "Category": label,
                    "Discounted Cost (M$)": f"{value/1e6:.3f}",
                    "Percentage (%)": f"{pct:.1f}"
                })
            fuel_display_data.append({
                "Category": "**Total Fuel Cycle**",
                "Discounted Cost (M$)": f"**{total_fuel_discounted/1e6:.3f}**",
                "Percentage (%)": "**100.0**"
            })
            fuel_display_df = pd.DataFrame(fuel_display_data)
            st.dataframe(fuel_display_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"❌ Error during computation: {str(e)}")
        st.exception(e)

else:
    st.info("👈 Please fill in the parameters above and click 'Compute LCOE' to run the calculation.")

